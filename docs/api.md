# API Reference

Base URL: `http://127.0.0.1:8000`  
Interactive docs (Swagger UI): `http://127.0.0.1:8000/docs`  
OpenAPI schema: `http://127.0.0.1:8000/openapi.json`

All request and response bodies are JSON unless noted otherwise.

---

## Categories

| Category | Prefix | Purpose |
|---|---|---|
| [Health](#health) | — | Service discovery and liveness |
| [Engine](#engine) | `/api` | Run the evolutionary loop, inspect state and metrics |
| [Runs](#runs) | `/api/runs` | Persist, restore, and delete experiment runs |
| [Prompt Agent](#prompt-agent) | `/api/promptagent` | Evolve a code-reviewer prompt via human feedback |
| [Accounts](#accounts) | `/api/accounts` | Expand the training dataset with synthetic or GitHub repos |
| [Review](#review) | `/api` | Live repository scoring (requires OpenAI) |

---

## Health

### `GET /`

Root endpoint. Returns service status and key URLs.

**Response**
```json
{
  "message": "Hyperagents backend is running.",
  "state_endpoint": "/api/state",
  "docs": "/docs"
}
```

---

### `GET /api/health`

Liveness check. Returns `200 OK` when the server is up.

**Response**
```json
{ "status": "ok" }
```

---

## Engine

The engine runs the HyperAgent evolutionary loop. State is held in memory and persisted to SQLite after each iteration.

### `GET /api/state`

Returns the full engine snapshot.

**Response fields**

| Field | Type | Description |
|---|---|---|
| `mode` | string | Active ablation condition (`hyperagent`, `baseline`, `no_archive`) |
| `run_id` | int \| null | Database ID of the current run |
| `iterations_completed` | int | Number of iterations run so far |
| `dataset.train_size` | int | Total training repos (base + accounts) |
| `dataset.test_size` | int | Total test repos |
| `best_agent` | object | Best agent found so far (see [Agent object](#agent-object)) |
| `archive` | array | All discovered agent variants |
| `progress` | array | Per-iteration metrics (see [Progress row](#progress-row)) |
| `recent_events` | array | Last 12 mutation events (newest first) |
| `provider` | object | OpenAI integration status |

**Example**
```bash
curl http://localhost:8000/api/state | jq '{mode, iterations_completed, best_fitness: .best_agent.evaluation.fitness}'
```

---

### `POST /api/reset`

Initialise a fresh run with the selected ablation condition. Clears the in-memory archive and creates a new database run record.

**Request body**

| Field | Type | Default | Description |
|---|---|---|---|
| `mode` | string | `"hyperagent"` | Ablation condition |

**Modes**

| Value | Task policy | Meta policy | Use case |
|---|---|---|---|
| `hyperagent` | Evolves | Evolves | Full system |
| `baseline` | Evolves | Frozen at seed | Isolate meta-policy contribution |
| `no_archive` | Evolves | Evolves | Greedy (no stepping stones) |

**Example**
```bash
curl -X POST http://localhost:8000/api/reset \
     -H "Content-Type: application/json" \
     -d '{"mode": "hyperagent"}'
```

**Response:** full engine snapshot (same as `GET /api/state`).

---

### `POST /api/run`

Execute N evolutionary iterations. Each iteration:
1. Selects a parent from the archive (weighted by fitness × exploration × weight-space novelty)
2. Mutates it to produce a child
3. Evaluates the child on all train and test repos
4. Adjusts the meta policy (or fires a plateau restart nudge)
5. Appends the child to the archive and persists to SQLite

**Request body**

| Field | Type | Default | Constraints |
|---|---|---|---|
| `iterations` | int | `5` | 1 – 100 |

**Example**
```bash
curl -X POST http://localhost:8000/api/run \
     -H "Content-Type: application/json" \
     -d '{"iterations": 30}'
```

**Response:** full engine snapshot.

---

### `GET /api/metrics/json`

Returns every progress row as a JSON array. Useful for programmatic analysis.

**Response** — array of [Progress row](#progress-row) objects.

**Example**
```bash
curl http://localhost:8000/api/metrics/json | jq '[.[] | {iteration, best_fitness, best_test_accuracy}]'
```

---

### `GET /api/metrics/csv`

Returns the same data as a CSV download. Content-Type is `text/plain`.

**Example**
```bash
curl http://localhost:8000/api/metrics/csv -o metrics.csv
```

---

## Runs

Runs are saved to SQLite automatically during each reset. Use these endpoints to list, inspect, restore, or delete them.

### `GET /api/runs`

List all saved runs, newest first.

**Response** — array of run summaries:

| Field | Type | Description |
|---|---|---|
| `run_id` | int | Database primary key |
| `run_uuid` | string | Short hex identifier |
| `mode` | string | Ablation condition |
| `created_at` | string | ISO-8601 UTC timestamp |
| `iterations_completed` | int | Total iterations recorded |
| `best_fitness` | float | Best train accuracy achieved |
| `best_test_accuracy` | float | Corresponding test accuracy |

**Example**
```bash
curl http://localhost:8000/api/runs | jq '.[] | {run_id, mode, best_fitness}'
```

---

### `GET /api/runs/{run_id}`

Returns the full snapshot for a single saved run: archive, progress log, and recent events.

**Path parameter:** `run_id` — integer database ID from `GET /api/runs`.

**Response:** same structure as `GET /api/state`.

**Example**
```bash
curl http://localhost:8000/api/runs/3 | jq .iterations_completed
```

---

### `POST /api/runs/{run_id}/load`

Restores a past run into the active engine. The in-memory archive and progress are replaced with the saved run's data. Further calls to `POST /api/run` will append to the same database record.

**Example**
```bash
curl -X POST http://localhost:8000/api/runs/3/load
```

**Response:** full engine snapshot reflecting the loaded run.

---

### `DELETE /api/runs/{run_id}`

Permanently deletes a run and all its associated agents, progress rows, and events from the database.

**Example**
```bash
curl -X DELETE http://localhost:8000/api/runs/3
```

**Response**
```json
{ "deleted": 3 }
```

---

## Prompt Agent

The prompt agent evolves a natural-language code-reviewer prompt. Each iteration consists of one human review cycle: run the prompt, rate the output, submit feedback, receive an improved prompt.

### `GET /api/promptagent/state`

Returns the current state of the prompt engine.

**Response fields**

| Field | Type | Description |
|---|---|---|
| `active_prompt` | string | The prompt to use for the next review |
| `active_agent_id` | string | ID of the current unevaluated prompt agent |
| `active_generation` | int | Generation number of the active prompt |
| `iterations_completed` | int | Number of review cycles completed |
| `archive_size` | int | Number of evaluated prompts in the archive |
| `best` | object \| null | Best-rated prompt found so far |
| `archive` | array | All evaluated prompt variants |

**Example**
```bash
curl http://localhost:8000/api/promptagent/state | jq .active_prompt
```

---

### `POST /api/promptagent/reset`

Start a fresh prompt engine run.

**Request body**

| Field | Type | Default | Description |
|---|---|---|---|
| `seed_prompt` | string | `""` | Starting prompt text. Leave empty to use the built-in default. |

**Example — use built-in default**
```bash
curl -X POST http://localhost:8000/api/promptagent/reset \
     -H "Content-Type: application/json" \
     -d '{}'
```

**Example — seed from your own file**
```bash
PROMPT=$(cat code-reviewer.md)
curl -X POST http://localhost:8000/api/promptagent/reset \
     -H "Content-Type: application/json" \
     -d "{\"seed_prompt\": $(echo "$PROMPT" | python -c 'import json,sys; print(json.dumps(sys.stdin.read()))')}"
```

**Response:** prompt engine state snapshot.

---

### `POST /api/promptagent/submit`

Record the result of one real review cycle. Archives the current prompt with the supplied rating, mutates it, and returns the improved prompt ready for the next cycle.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `review_text` | string | Yes | Full output of the review that was run (min 10 chars) |
| `rating` | int | Yes | Quality rating: 1 (poor) → 5 (excellent) |
| `strengths` | array[string] | No | What the review got right |
| `gaps` | array[string] | No | What the review missed or got wrong |
| `codebase_ref` | string | No | Free-text reference, e.g. `"my-repo @ main"` |

**Mutation logic**

| Rating | Mutation strategy |
|---|---|
| 1–2 | Prepend a specificity directive + address top 2 gaps |
| 3 | Append gap-derived focus areas |
| 4–5 | Reinforce primary strength; minor refinement only |

If OpenAI is configured (`HYPERAGENTS_USE_OPENAI=1`), the LLM produces the mutation; otherwise the heuristic above applies.

**Response fields**

| Field | Type | Description |
|---|---|---|
| `new_prompt` | string | Improved prompt — use this for the next review |
| `new_agent_id` | string | ID of the newly created prompt agent |
| `generation` | int | Generation number of the new prompt |
| `iteration` | int | Current iteration count |
| `fitness` | float | Normalised rating of the archived prompt: `(rating − 1) / 4.0` |
| `mutation_source` | string | `"llm"` or `"heuristic"` |
| `rationale` | string | One-sentence explanation of the key change |
| `archive_size` | int | Total evaluated prompts in the archive |

**Example**
```bash
curl -X POST http://localhost:8000/api/promptagent/submit \
     -H "Content-Type: application/json" \
     -d '{
       "review_text": "The code has poor test coverage and no README.",
       "rating": 2,
       "strengths": ["Good security analysis"],
       "gaps": ["No documentation review", "Missing test coverage analysis"],
       "codebase_ref": "my-repo @ main"
     }' | jq .new_prompt
```

---

### `GET /api/promptagent/export`

Returns the best-rated prompt found so far. If no reviews have been submitted yet, returns the active seed prompt.

**Response**

| Field | Type | Description |
|---|---|---|
| `prompt` | string | The prompt text |
| `agent_id` | string | ID of the source prompt agent (if from archive) |
| `generation` | int | Generation number (if from archive) |
| `fitness` | float \| null | Normalised fitness (null if seed) |
| `rating` | int \| null | Raw rating (null if seed) |
| `source` | string | `"best archived agent"` or `"active (no reviews submitted yet)"` |

**Example — write best prompt to file**
```bash
curl http://localhost:8000/api/promptagent/export | jq -r .prompt > code-reviewer.md
```

---

## Accounts

Accounts expand the engine's training dataset beyond the 30 built-in fixtures. After adding accounts, call `POST /api/accounts/apply-all` then `POST /api/reset` to use the expanded dataset.

### `POST /api/accounts`

Add an account and generate or fetch its repositories.

**Request body**

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | string | — | Account or GitHub username |
| `platform` | string | `"synthetic"` | `"synthetic"` or `"github"` |
| `profile` | string | `"mixed"` | Synthetic profile (ignored for GitHub) |
| `n_repos` | int | `10` | Number of repos to generate/fetch (1–50) |

**Synthetic profiles**

| Profile | Description |
|---|---|
| `high_quality` | Mostly accept-labelled repos |
| `low_quality` | Mostly reject-labelled repos |
| `mixed` | Balanced mix |
| `security_focused` | High security scores |
| `well_tested` | High test-coverage scores |

**Example — synthetic**
```bash
curl -X POST http://localhost:8000/api/accounts \
     -H "Content-Type: application/json" \
     -d '{"name": "acme-corp", "platform": "synthetic", "profile": "high_quality", "n_repos": 20}'
```

**Example — GitHub** (requires `GITHUB_TOKEN`)
```bash
curl -X POST http://localhost:8000/api/accounts \
     -H "Content-Type: application/json" \
     -d '{"name": "torvalds", "platform": "github", "n_repos": 15}'
```

**Response**

| Field | Type | Description |
|---|---|---|
| `id` | int | Account database ID |
| `name` | string | Account name |
| `platform` | string | `"synthetic"` or `"github"` |
| `profile` | string | Profile used |
| `repo_count` | int | Number of repos added |
| `repos` | array | Full repo objects with feature scores and labels |

---

### `GET /api/accounts`

List all accounts with repo counts.

**Example**
```bash
curl http://localhost:8000/api/accounts | jq '.[] | {id, name, platform, repo_count}'
```

---

### `GET /api/accounts/{account_id}/repos`

Returns all repos for a single account.

**Example**
```bash
curl http://localhost:8000/api/accounts/1/repos | jq '.[0]'
```

---

### `DELETE /api/accounts/{account_id}`

Deletes the account and all its repos from the database. Does not affect the engine's live dataset until the next `apply-all` + `reset`.

**Example**
```bash
curl -X DELETE http://localhost:8000/api/accounts/1
```

**Response**
```json
{ "deleted": 1 }
```

---

### `POST /api/accounts/apply-all`

Pushes every saved account repo into the engine's live dataset. The split is 80 % train / 20 % test.

Call `POST /api/reset` after this to re-seed the evolutionary loop with the expanded dataset.

**Example**
```bash
curl -X POST http://localhost:8000/api/accounts/apply-all
curl -X POST http://localhost:8000/api/reset -H "Content-Type: application/json" -d '{"mode": "hyperagent"}'
```

**Response:** full engine snapshot showing updated `dataset.train_size` and `dataset.test_size`.

---

## Review

Live repository scoring using the best agent and the LLM reviewer.

### `POST /api/review-repo`

Fetches repository metadata from GitHub and scores it.

**Requires:**
- `GITHUB_TOKEN` (for repo metadata fetch)
- `OPENAI_API_KEY` + `HYPERAGENTS_USE_OPENAI=1` (for LLM scoring)

**Request body**

| Field | Type | Description |
|---|---|---|
| `repo_url` | string | GitHub repository URL (e.g. `https://github.com/owner/repo`) |

**Example**
```bash
curl -X POST http://localhost:8000/api/review-repo \
     -H "Content-Type: application/json" \
     -d '{"repo_url": "https://github.com/AISmithy/hyperagents"}'
```

**Response:** LLM-generated review object (structure depends on `review_repository.md` prompt).

---

## Data Objects

### Agent object

```json
{
  "agent": {
    "agent_id": "agent-007",
    "parent_id": "agent-004",
    "generation": 3,
    "task_policy": {
      "weights": {
        "maintainability": 0.92,
        "security": 0.88,
        "test_coverage": 0.91,
        "documentation": 0.74,
        "simplicity": 0.80
      },
      "threshold": 3.12,
      "review_style": "strict"
    },
    "meta_policy": {
      "focus_metric": "security",
      "weight_step": 0.11,
      "threshold_step": 0.07,
      "exploration_scale": 0.15,
      "memory": [
        "Raise bar on security; weak repos are slipping through.",
        "Positive update. Tighten exploration and consolidate gains."
      ]
    },
    "lineage_notes": ["Seed agent ...", "Raise bar on security ..."]
  },
  "evaluation": {
    "fitness": 0.85,
    "train_accuracy": 0.85,
    "test_accuracy": 0.90,
    "false_positive_count": 2,
    "false_negative_count": 1,
    "false_positive_feature_avgs": { "maintainability": 0.61, "security": 0.42, "..." : "..." },
    "false_negative_feature_avgs": { "maintainability": 0.81, "security": 0.79, "..." : "..." },
    "summary": "2 false positives, usually weak on security. 1 false negative, often strong on maintainability."
  },
  "created_iteration": 7
}
```

### Progress row

```json
{
  "iteration": 7,
  "best_fitness": 0.85,
  "best_test_accuracy": 0.90,
  "child_train_accuracy": 0.80,
  "child_test_accuracy": 0.80,
  "archive_size": 8,
  "meta_focus_metric": "security",
  "meta_weight_step": 0.11,
  "meta_threshold_step": 0.07,
  "meta_exploration_scale": 0.15,
  "mutation_source": "heuristic",
  "mode": "hyperagent"
}
```

### Prompt archive entry

```json
{
  "agent_id": "prompt-002",
  "parent_id": "prompt-001",
  "generation": 2,
  "prompt": "You are an expert code reviewer...",
  "meta_notes": [
    "Rating 2/5: prepended specificity directive and top 2 gap(s)."
  ],
  "created_iteration": 1,
  "evaluation": {
    "fitness": 0.25,
    "rating": 2,
    "strengths": ["Good security analysis"],
    "gaps": ["No documentation review", "Missing test coverage"],
    "review_excerpt": "The code has poor test coverage...",
    "codebase_ref": "my-repo @ main",
    "summary": "Rating 2/5. Strength: Good security analysis. Gap: No documentation review."
  }
}
```

---

## Error Responses

All errors follow the standard FastAPI format:

```json
{ "detail": "Run 99 not found." }
```

| Status | Meaning |
|---|---|
| `400` | Bad request — invalid parameters or unavailable integration |
| `404` | Resource not found |
| `422` | Validation error — request body does not match schema |
