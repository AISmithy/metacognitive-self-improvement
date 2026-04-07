# hyperagents — backend

FastAPI + SQLite backend for the HyperAgents proof-of-concept.

---

## Install

```bash
pip install -e .
```

Requires Python 3.11+. Dependencies: `fastapi`, `uvicorn`, `sqlmodel`, `openai`.

---

## Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API docs: `http://localhost:8000/docs`

---

## Environment Variables

Create `.env.local` in this directory (never committed):

```
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
HYPERAGENTS_USE_OPENAI=1
GITHUB_TOKEN=your_token_here
HYPERAGENTS_DB_PATH=../hyperagents.db
REVIEWER_PROMPT_PATH=../code-reviewer.md
```

All variables are optional. Without `OPENAI_API_KEY` + `HYPERAGENTS_USE_OPENAI=1` the system runs fully offline using the deterministic heuristic engine.

---

## API Reference

### Engine

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/state` | Current engine state (best agent, archive, progress) |
| `POST` | `/api/reset` | Start a new run — body: `{"mode": "hyperagent\|baseline\|no_archive"}` |
| `POST` | `/api/run` | Run N iterations — body: `{"iterations": 10}` |
| `GET` | `/api/metrics/json` | Per-iteration metrics as JSON |
| `GET` | `/api/metrics/csv` | Per-iteration metrics as CSV download |

### Run management

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/runs` | List all saved runs |
| `GET` | `/api/runs/{id}` | Single run snapshot |
| `POST` | `/api/runs/{id}/load` | Restore a saved run into the active engine |
| `DELETE` | `/api/runs/{id}` | Delete a saved run |

### Self-improving prompt engine

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/promptagent/state` | Active prompt, archive, iteration count |
| `POST` | `/api/promptagent/reset` | Start fresh — body: `{"seed_prompt": "..."}` (optional) |
| `POST` | `/api/promptagent/submit` | Submit a review result and receive an improved prompt |
| `GET` | `/api/promptagent/export` | Export the best prompt found so far |

`/api/promptagent/submit` body:

```json
{
  "review_text": "full review output here",
  "rating": 3,
  "strengths": ["good security coverage"],
  "gaps": ["no line-level citations"],
  "codebase_ref": "my-repo @ main"
}
```

### Accounts (synthetic + GitHub dataset expansion)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/accounts` | Add an account (synthetic or GitHub) |
| `GET` | `/api/accounts` | List accounts |
| `GET` | `/api/accounts/{id}/repos` | Repos for one account |
| `DELETE` | `/api/accounts/{id}` | Delete account and its repos |
| `POST` | `/api/accounts/apply-all` | Push all account repos into the engine dataset |

### Live repo review (requires OpenAI)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/review-repo` | Score a GitHub repo with the best agent + LLM |

---

## Package Layout

```text
app/
├── engine.py                   # Core evolutionary loop
├── datasets.py                 # 20 train + 10 test synthetic repo fixtures
├── database.py                 # SQLModel tables + Database class
├── main.py                     # FastAPI app + route handlers
├── openai_service.py           # LLM mutation planner + repo reviewer
├── account_service.py          # Synthetic and GitHub repo generation
├── github_service.py           # GitHub API wrapper
├── settings.py                 # Env-driven config (reads .env.local)
├── prompts/
│   ├── propose_mutation.md     # LLM system prompt: agent weight mutation
│   └── review_repository.md   # LLM system prompt: live repo review
└── selfimprovingprompt/
    ├── engine.py               # PromptEngine — evolves a text prompt
    └── prompts/
        └── mutate_agent_prompt.md  # LLM system prompt: prompt mutation
```

---

## Ablation Conditions

| Mode | Flag | What it tests |
|---|---|---|
| Full system | `hyperagent` | Both task and meta policy evolve |
| Frozen meta | `baseline` | Only task policy evolves; isolates meta-policy contribution |
| No archive | `no_archive` | Greedy parent selection; isolates archive contribution |

Select via `POST /api/reset` with `{"mode": "..."}` or via `scripts/run_experiment.py`.
