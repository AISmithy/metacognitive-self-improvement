from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from .account_service import (
    VALID_PROFILES,
    generate_synthetic_repos,
    infer_features_from_github,
    oracle_label,
)
from .database import Database
from .engine import HyperAgentEngine
from .github_service import GitHubService
from .openai_service import OpenAIHyperAgentService
from .selfimprovingprompt import PromptEngine
from .settings import get_settings

# ── Tag definitions (appear as sections in /docs) ────────────────────────────

TAGS_METADATA = [
    {
        "name": "engine",
        "description": "Control the HyperAgent evolutionary loop: reset, run iterations, "
                       "inspect state and metrics.",
    },
    {
        "name": "runs",
        "description": "Persist and restore named experiment runs. Load a past run back "
                       "into the engine to continue or compare.",
    },
    {
        "name": "prompt-agent",
        "description": "Self-improving code-reviewer prompt engine. Submit a human-rated "
                       "review to receive an evolved prompt for the next cycle.",
    },
    {
        "name": "accounts",
        "description": "Expand the training dataset with synthetic or GitHub-backed "
                       "accounts. Apply all repos to the live engine dataset.",
    },
    {
        "name": "review",
        "description": "Live repository review. Requires OpenAI to be configured.",
    },
    {
        "name": "health",
        "description": "Service health and root discovery.",
    },
]

app = FastAPI(
    title="Hyperagents API",
    version="0.1.0",
    description=(
        "Proof-of-concept backend for a HyperAgents-inspired metacognitive "
        "self-improvement framework.\n\n"
        "- **engine** — run the evolutionary loop and inspect results\n"
        "- **runs** — save, load, and compare experiment runs\n"
        "- **prompt-agent** — evolve a code-reviewer prompt via human feedback\n"
        "- **accounts** — expand the training dataset\n"
        "- **review** — live repo scoring (requires OpenAI)\n"
    ),
    openapi_tags=TAGS_METADATA,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = get_settings()
llm_service = OpenAIHyperAgentService(settings)
db = Database(settings.db_path)
engine = HyperAgentEngine(llm_service=llm_service, db=db)
github_service = GitHubService(token=settings.github_token)
prompt_engine = PromptEngine(
    llm_service=llm_service,
    write_back_path=settings.reviewer_prompt_path,
)


# ── Request / response models ─────────────────────────────────────────────────

class RunRequest(BaseModel):
    iterations: int = Field(default=5, ge=1, le=100)


class ResetRequest(BaseModel):
    mode: str = Field(default="hyperagent", pattern="^(hyperagent|baseline|no_archive)$")


class RepoReviewRequest(BaseModel):
    repo_url: str = Field(min_length=10, max_length=500)


class AddAccountRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    platform: str = Field(default="synthetic", pattern="^(synthetic|github)$")
    profile: str = Field(default="mixed")
    n_repos: int = Field(default=10, ge=1, le=50)


class PromptResetRequest(BaseModel):
    seed_prompt: str = Field(
        default="",
        description="Initial prompt text. Leave empty to use the built-in default.",
    )


class SubmitReviewRequest(BaseModel):
    review_text: str = Field(
        min_length=10,
        description="The full output of the review that was just run.",
    )
    rating: int = Field(
        ge=1, le=5,
        description="Your rating of the review quality: 1 (poor) to 5 (excellent).",
    )
    strengths: list[str] = Field(
        default_factory=list,
        description="What the review got right (used to guide mutation).",
    )
    gaps: list[str] = Field(
        default_factory=list,
        description="What the review missed or got wrong (used to guide mutation).",
    )
    codebase_ref: str = Field(
        default="",
        description="Free-text reference to the reviewed codebase, e.g. 'my-repo @ main'.",
    )


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/", tags=["health"], summary="Root — service discovery")
def read_root() -> dict[str, str]:
    return {
        "message": "Hyperagents backend is running.",
        "state_endpoint": "/api/state",
        "docs": "/docs",
    }


@app.get("/api/health", tags=["health"], summary="Health check")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ── Engine ────────────────────────────────────────────────────────────────────

@app.get(
    "/api/state",
    tags=["engine"],
    summary="Get engine state",
    description="Returns the full snapshot: mode, best agent, archive, progress log, "
                "recent mutation events, and dataset sizes.",
)
def get_state() -> dict:
    return engine.snapshot()


@app.post(
    "/api/reset",
    tags=["engine"],
    summary="Reset the engine",
    description=(
        "Initialise a fresh run with the selected ablation condition.\n\n"
        "| mode | behaviour |\n"
        "|---|---|\n"
        "| `hyperagent` | Full system — both task and meta policy evolve |\n"
        "| `baseline` | Meta policy frozen at seed; only task policy evolves |\n"
        "| `no_archive` | Greedy parent selection; always mutate from the current best |\n"
    ),
)
def reset(request: ResetRequest = ResetRequest()) -> dict:
    engine.reset(mode=request.mode)
    return engine.snapshot()


@app.post(
    "/api/run",
    tags=["engine"],
    summary="Run iterations",
    description="Execute N evolutionary iterations. Each iteration selects a parent, "
                "mutates it, evaluates the child, and updates the archive.",
)
def run_iterations(request: RunRequest) -> dict:
    engine.run(request.iterations)
    return engine.snapshot()


@app.get(
    "/api/metrics/json",
    tags=["engine"],
    summary="Per-iteration metrics (JSON)",
    description="Returns every progress row: best fitness, test accuracy, child scores, "
                "archive size, and meta-policy parameters at each iteration.",
)
def metrics_json() -> list:
    return engine.metrics_json()


@app.get(
    "/api/metrics/csv",
    tags=["engine"],
    summary="Per-iteration metrics (CSV download)",
    response_class=PlainTextResponse,
)
def metrics_csv() -> str:
    return engine.metrics_csv()


# ── Runs ──────────────────────────────────────────────────────────────────────

@app.get(
    "/api/runs",
    tags=["runs"],
    summary="List saved runs",
    description="Returns all runs stored in the database, newest first.",
)
def list_runs() -> list:
    return db.list_runs()


@app.get(
    "/api/runs/{run_id}",
    tags=["runs"],
    summary="Get a saved run",
    description="Returns the full snapshot for a single run: archive, progress, "
                "and recent events.",
)
def get_run(run_id: int) -> dict:
    snapshot = db.load_run(run_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    return snapshot


@app.post(
    "/api/runs/{run_id}/load",
    tags=["runs"],
    summary="Load a saved run into the engine",
    description="Restores a past run into the active engine. Further calls to "
                "`POST /api/run` will append to the same database record.",
)
def load_run(run_id: int) -> dict:
    snapshot = db.load_run(run_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    engine.load_run_snapshot(snapshot)
    return engine.snapshot()


@app.delete(
    "/api/runs/{run_id}",
    tags=["runs"],
    summary="Delete a saved run",
)
def delete_run(run_id: int) -> dict:
    if not db.delete_run(run_id):
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    return {"deleted": run_id}


# ── Prompt Agent ──────────────────────────────────────────────────────────────

@app.get(
    "/api/promptagent/state",
    tags=["prompt-agent"],
    summary="Get prompt engine state",
    description="Returns the active prompt, iteration count, archive of all evaluated "
                "prompts, and the best prompt found so far.",
)
def promptagent_state() -> dict:
    return prompt_engine.snapshot()


@app.post(
    "/api/promptagent/reset",
    tags=["prompt-agent"],
    summary="Reset the prompt engine",
    description="Start a fresh run. Pass the contents of your `code-reviewer.md` as "
                "`seed_prompt` to begin from your own baseline, or leave it empty to "
                "use the built-in default.",
)
def promptagent_reset(request: PromptResetRequest = PromptResetRequest()) -> dict:
    prompt_engine.reset(seed_prompt=request.seed_prompt or None)
    return prompt_engine.snapshot()


@app.post(
    "/api/promptagent/submit",
    tags=["prompt-agent"],
    summary="Submit a review result",
    description=(
        "Record the outcome of one real review cycle and receive an improved prompt.\n\n"
        "**Workflow:**\n"
        "1. Run the active prompt against your codebase with your LLM.\n"
        "2. Read the review output.\n"
        "3. Rate it 1–5 and note what it got right (`strengths`) and missed (`gaps`).\n"
        "4. POST to this endpoint.\n"
        "5. Use `new_prompt` from the response for the next review cycle.\n"
        "6. Repeat until the prompt converges to a rating of 4–5.\n\n"
        "If OpenAI is configured, mutation is LLM-guided; otherwise the heuristic "
        "fallback applies gap-driven instructions to the prompt text."
    ),
)
def promptagent_submit(request: SubmitReviewRequest) -> dict:
    try:
        result = prompt_engine.submit_review(
            review_text=request.review_text,
            rating=request.rating,
            strengths=request.strengths,
            gaps=request.gaps,
            codebase_ref=request.codebase_ref,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@app.get(
    "/api/promptagent/export",
    tags=["prompt-agent"],
    summary="Export the best prompt",
    description=(
        "Returns the best-rated prompt found so far as plain text.\n\n"
        "Write it to your reviewer file:\n"
        "```bash\n"
        "curl .../api/promptagent/export | jq -r .prompt > code-reviewer.md\n"
        "```"
    ),
)
def promptagent_export() -> dict:
    best = prompt_engine.best_entry
    if best is None:
        active = prompt_engine.active_prompt
        return {"prompt": active, "source": "active (no reviews submitted yet)", "fitness": None}
    return {
        "prompt": best.agent.prompt,
        "agent_id": best.agent.agent_id,
        "generation": best.agent.generation,
        "fitness": best.evaluation.fitness,
        "rating": best.evaluation.rating,
        "source": "best archived agent",
    }


# ── Accounts ──────────────────────────────────────────────────────────────────

@app.post(
    "/api/accounts",
    tags=["accounts"],
    summary="Add an account",
    description=(
        "Add a synthetic or GitHub account and generate/fetch its repositories.\n\n"
        "**platform = `synthetic`:** generates `n_repos` fake repos using the selected "
        "profile (`high_quality`, `low_quality`, `mixed`, `security_focused`, "
        "`well_tested`).\n\n"
        "**platform = `github`:** fetches real repos via the GitHub API and infers "
        "feature scores from metadata (stars, open issues, language, etc.). "
        "Requires `GITHUB_TOKEN` to be configured."
    ),
)
def add_account(request: AddAccountRequest) -> dict:
    if request.platform == "synthetic":
        if request.profile not in VALID_PROFILES:
            raise HTTPException(status_code=400, detail=f"profile must be one of {VALID_PROFILES}")
        repos = generate_synthetic_repos(request.name, request.profile, request.n_repos)
    else:
        try:
            repo_metas = github_service.list_user_repos(request.name, max_repos=request.n_repos)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        repos = []
        for meta in repo_metas:
            features = infer_features_from_github(meta)
            repos.append({
                "id": f"gh-{request.name}-{meta['name']}",
                "name": meta["name"],
                **features,
                "label": oracle_label(features),
            })

    account_id = db.create_account(request.name, request.platform, request.profile)
    for repo in repos:
        db.save_account_repo(account_id, repo)

    return {
        "id": account_id,
        "name": request.name,
        "platform": request.platform,
        "profile": request.profile,
        "repo_count": len(repos),
        "repos": repos,
    }


@app.get(
    "/api/accounts",
    tags=["accounts"],
    summary="List accounts",
)
def list_accounts() -> list:
    return db.list_accounts()


@app.get(
    "/api/accounts/{account_id}/repos",
    tags=["accounts"],
    summary="Get repos for an account",
)
def get_account_repos(account_id: int) -> list:
    repos = db.get_account_repos(account_id)
    if repos is None:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found.")
    return repos


@app.delete(
    "/api/accounts/{account_id}",
    tags=["accounts"],
    summary="Delete an account",
    description="Deletes the account and all its associated repos from the database.",
)
def delete_account(account_id: int) -> dict:
    if not db.delete_account(account_id):
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found.")
    return {"deleted": account_id}


@app.post(
    "/api/accounts/apply-all",
    tags=["accounts"],
    summary="Apply all account repos to the engine dataset",
    description=(
        "Pushes every saved account repo into the engine's live dataset (80 % train / "
        "20 % test split). Call `POST /api/reset` afterwards to re-seed the evolutionary "
        "loop with the updated dataset sizes reflected in the initial agent's evaluation."
    ),
)
def apply_all_account_repos() -> dict:
    repos = db.list_all_account_repos()
    engine.set_account_repos(repos)
    return engine.snapshot()


# ── Review ────────────────────────────────────────────────────────────────────

@app.post(
    "/api/review-repo",
    tags=["review"],
    summary="Live repository review",
    description=(
        "Fetches repository metadata from GitHub and scores it using the best agent "
        "and the LLM reviewer.\n\n"
        "**Requires:** `OPENAI_API_KEY` and `HYPERAGENTS_USE_OPENAI=1` in `.env.local`."
    ),
)
def review_repo(request: RepoReviewRequest) -> dict:
    try:
        repo_data = github_service.fetch_repo_summary(request.repo_url)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return engine.review_repository(request.repo_url, repo_data)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
