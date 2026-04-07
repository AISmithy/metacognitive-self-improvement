"""Self-improving code-reviewer prompt engine.

The core loop (one iteration = one human review cycle):

1. The active prompt is run against a codebase by the user.
2. The user reads the review output, rates it 1–5, and records
   what it got right (strengths) and what it missed (gaps).
3. The user calls submit_review() with that data.
4. The engine archives the current prompt + evaluation.
5. The engine mutates: LLM-guided if available, heuristic otherwise.
6. The new prompt becomes active (and is optionally written to disk).
7. submit_review() returns the new prompt so the next review cycle
   can start immediately.

Fitness is the normalised rating: (rating - 1) / 4.0, giving [0.0, 1.0].
"""
from __future__ import annotations

import pathlib
import random
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.openai_service import OpenAIHyperAgentService


# ── Seed prompt ───────────────────────────────────────────────────────────────

DEFAULT_SEED_PROMPT = """\
You are an expert code reviewer. Your job is to analyse a code repository \
and provide structured, actionable feedback.

For every review, cover the following five dimensions:

1. **Maintainability** — Is the code organised, readable, and easy to extend?
2. **Security** — Are there obvious vulnerabilities, exposed secrets, or unsafe patterns?
3. **Test coverage** — Are there meaningful tests? Are edge cases handled?
4. **Documentation** — Are public interfaces documented? Is there a README?
5. **Simplicity** — Is the code concise and free of unnecessary complexity?

Structure your output as follows:
- Overall verdict: ACCEPT or REJECT (one line)
- Score: X/10
- Strengths: 3 bullet points
- Critical issues: 3 bullet points
- Specific recommendations: numbered list

Be specific. Cite file names, function names, or line numbers where relevant. \
Avoid vague generalisations.\
"""


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class PromptAgent:
    agent_id: str
    parent_id: str | None
    generation: int
    prompt: str
    meta_notes: list[str] = field(default_factory=list)


@dataclass
class PromptEvaluation:
    fitness: float          # normalised: (rating - 1) / 4.0
    rating: int             # raw human rating 1–5
    strengths: list[str]
    gaps: list[str]
    review_excerpt: str     # first 500 chars of the review that was run
    codebase_ref: str
    summary: str


@dataclass
class PromptArchiveEntry:
    agent: PromptAgent
    evaluation: PromptEvaluation
    created_iteration: int


# ── Engine ────────────────────────────────────────────────────────────────────

class PromptEngine:
    def __init__(
        self,
        llm_service: OpenAIHyperAgentService | None = None,
        write_back_path: str = "",
        seed: int = 7,
    ) -> None:
        self._llm_service = llm_service
        self._write_back_path = pathlib.Path(write_back_path) if write_back_path else None
        self._seed = seed
        self._rng = random.Random(seed)
        self._next_id = 0
        self.archive: list[PromptArchiveEntry] = []
        self.iterations_completed = 0
        self._active_agent = self._build_initial_agent()

    # ── Public interface ──────────────────────────────────────────────────────

    @property
    def active_prompt(self) -> str:
        return self._active_agent.prompt

    @property
    def best_entry(self) -> PromptArchiveEntry | None:
        if not self.archive:
            return None
        return max(
            self.archive,
            key=lambda e: (e.evaluation.fitness, e.created_iteration),
        )

    def reset(self, seed_prompt: str | None = None) -> None:
        self._rng = random.Random(self._seed)
        self._next_id = 0
        self.archive = []
        self.iterations_completed = 0
        self._active_agent = self._build_initial_agent(seed_prompt)

    def submit_review(
        self,
        review_text: str,
        rating: int,
        strengths: list[str],
        gaps: list[str],
        codebase_ref: str = "",
    ) -> dict[str, Any]:
        """Record the outcome of one real review cycle and return an improved prompt.

        The returned dict always includes ``new_prompt`` — the prompt to use
        for the next cycle.
        """
        fitness = round((rating - 1) / 4.0, 3)
        summary = self._build_summary(rating, strengths, gaps)

        current_eval = PromptEvaluation(
            fitness=fitness,
            rating=rating,
            strengths=list(strengths),
            gaps=list(gaps),
            review_excerpt=review_text[:500],
            codebase_ref=codebase_ref,
            summary=summary,
        )
        current_entry = PromptArchiveEntry(
            agent=self._active_agent,
            evaluation=current_eval,
            created_iteration=self.iterations_completed,
        )
        self.archive.append(current_entry)

        # Mutate to produce the next prompt
        child_agent, mutation_source, rationale = self._mutate(current_entry)
        self._active_agent = child_agent
        self.iterations_completed += 1

        # Optionally write the new prompt to disk
        if self._write_back_path:
            try:
                self._write_back_path.parent.mkdir(parents=True, exist_ok=True)
                self._write_back_path.write_text(child_agent.prompt, encoding="utf-8")
            except OSError:
                pass  # bad path — do not crash the endpoint

        return {
            "iteration": self.iterations_completed,
            "archived_agent_id": current_entry.agent.agent_id,
            "fitness": current_eval.fitness,
            "rating": rating,
            "summary": summary,
            "mutation_source": mutation_source,
            "rationale": rationale,
            "new_prompt": child_agent.prompt,
            "new_agent_id": child_agent.agent_id,
            "generation": child_agent.generation,
            "archive_size": len(self.archive),
        }

    def snapshot(self) -> dict[str, Any]:
        best = self.best_entry
        return {
            "active_prompt": self._active_agent.prompt,
            "active_agent_id": self._active_agent.agent_id,
            "active_generation": self._active_agent.generation,
            "iterations_completed": self.iterations_completed,
            "archive_size": len(self.archive),
            "best": self._serialize_entry(best) if best else None,
            "archive": [self._serialize_entry(e) for e in self.archive],
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _build_initial_agent(self, seed_prompt: str | None = None) -> PromptAgent:
        prompt = (seed_prompt or DEFAULT_SEED_PROMPT).strip()
        return PromptAgent(
            agent_id=self._new_agent_id(),
            parent_id=None,
            generation=0,
            prompt=prompt,
            meta_notes=["Seed prompt — no evaluation yet."],
        )

    def _new_agent_id(self) -> str:
        agent_id = f"prompt-{self._next_id:03d}"
        self._next_id += 1
        return agent_id

    def _mutate(
        self, parent_entry: PromptArchiveEntry
    ) -> tuple[PromptAgent, str, str]:
        """Return (child_agent, mutation_source, rationale)."""
        # Try LLM mutation first
        if self._llm_service is not None and self._llm_service.is_enabled:
            result = self._llm_service.mutate_reviewer_prompt(parent_entry)
            if result and "prompt" in result and result["prompt"].strip():
                rationale = result.get("rationale", "LLM-guided mutation.")
                notes = (parent_entry.agent.meta_notes + [rationale])[-4:]
                child = PromptAgent(
                    agent_id=self._new_agent_id(),
                    parent_id=parent_entry.agent.agent_id,
                    generation=parent_entry.agent.generation + 1,
                    prompt=result["prompt"].strip(),
                    meta_notes=notes,
                )
                return child, "llm", rationale

        # Heuristic fallback
        new_prompt, rationale = self._heuristic_mutate(
            parent_entry.agent.prompt,
            parent_entry.evaluation.rating,
            parent_entry.evaluation.strengths,
            parent_entry.evaluation.gaps,
        )
        notes = (parent_entry.agent.meta_notes + [rationale])[-4:]
        child = PromptAgent(
            agent_id=self._new_agent_id(),
            parent_id=parent_entry.agent.agent_id,
            generation=parent_entry.agent.generation + 1,
            prompt=new_prompt,
            meta_notes=notes,
        )
        return child, "heuristic", rationale

    def _heuristic_mutate(
        self,
        prompt: str,
        rating: int,
        strengths: list[str],
        gaps: list[str],
    ) -> tuple[str, str]:
        """Produce an improved prompt without an LLM."""
        additions: list[str] = []
        rationale_parts: list[str] = []

        if rating <= 2:
            # Low quality — prepend a strong directive and address top gaps
            header_lines = [
                "IMPORTANT: Be highly specific. Cite file names, function names, "
                "or line numbers for every claim you make. Avoid vague summaries."
            ]
            for gap in gaps[:2]:
                header_lines.append(f"- Ensure you address: {gap}")
            new_prompt = "\n".join(header_lines) + "\n\n" + prompt
            rationale_parts.append(
                f"Rating {rating}/5: prepended specificity directive and top {len(gaps[:2])} gap(s)."
            )
            return new_prompt, " ".join(rationale_parts)

        if rating == 3:
            # Acceptable — append gap-derived focus areas
            if gaps:
                focus_lines = ["", "Additional focus areas for this codebase:"]
                for gap in gaps[:3]:
                    focus_lines.append(f"- {gap}")
                additions.extend(focus_lines)
                rationale_parts.append(
                    f"Rating {rating}/5: appended {len(gaps[:3])} gap-derived focus area(s)."
                )
            else:
                rationale_parts.append(f"Rating {rating}/5: no gaps provided; minor pass.")

        else:
            # rating >= 4 — good; reinforce primary strength, minor addition only
            if strengths:
                additions.append(
                    f"\nContinue to prioritise: {strengths[0]}"
                )
                rationale_parts.append(
                    f"Rating {rating}/5: reinforced primary strength."
                )
            else:
                rationale_parts.append(f"Rating {rating}/5: high rating; no change needed.")

        new_prompt = prompt + "\n".join(additions) if additions else prompt
        return new_prompt.strip(), " ".join(rationale_parts)

    def _build_summary(
        self, rating: int, strengths: list[str], gaps: list[str]
    ) -> str:
        parts = [f"Rating {rating}/5."]
        if strengths:
            parts.append(f"Strength: {strengths[0][:80]}")
        if gaps:
            parts.append(f"Gap: {gaps[0][:80]}")
        return " ".join(parts)

    def _serialize_entry(self, entry: PromptArchiveEntry) -> dict[str, Any]:
        ev = entry.evaluation
        return {
            "agent_id": entry.agent.agent_id,
            "parent_id": entry.agent.parent_id,
            "generation": entry.agent.generation,
            "prompt": entry.agent.prompt,
            "meta_notes": entry.agent.meta_notes,
            "created_iteration": entry.created_iteration,
            "evaluation": {
                "fitness": ev.fitness,
                "rating": ev.rating,
                "strengths": ev.strengths,
                "gaps": ev.gaps,
                "review_excerpt": ev.review_excerpt,
                "codebase_ref": ev.codebase_ref,
                "summary": ev.summary,
            },
        }
