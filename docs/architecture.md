# Architecture

## 1. System Overview

```mermaid
graph TB
  subgraph BE ["Backend  (FastAPI · :8000)"]
    API["REST API\n/api/reset · /api/run · /api/state\n/api/metrics · /api/runs\n/api/promptagent/*"]
    ENGINE["HyperAgentEngine"]
    PROMPTENGINE["PromptEngine"]
    OAI["OpenAI Service\n(optional)"]
  end

  subgraph CORE ["Core Engines"]
    HA["HyperAgent\ntask_policy + meta_policy"]
    PA["PromptAgent\nprompt text + meta_notes"]
    ARCHIVE["Archive\nall variants + lineage"]
    DS["Dataset\n20 train · 10 test repos"]
  end

  subgraph PERSIST ["Persistence"]
    DB[("SQLite\nhyperagents.db")]
    CSV["results/raw_metrics.csv"]
  end

  SCRIPTS["scripts/\nrun_experiment.py\nplot_results.py"]

  API       --> ENGINE
  API       --> PROMPTENGINE
  ENGINE    --> HA
  ENGINE    --> ARCHIVE
  ENGINE    --> DS
  PROMPTENGINE --> PA
  PROMPTENGINE --> ARCHIVE
  ENGINE    -.->|"optional"| OAI
  PROMPTENGINE -.->|"optional"| OAI
  ENGINE    -->|"persist"| DB
  SCRIPTS   -->|"direct import"| ENGINE
  SCRIPTS   --> CSV
```

No frontend is included. All interaction is via the REST API or the CLI scripts.

---

## 2. HyperAgent Structure

```mermaid
classDiagram
  class HyperAgent {
    +agent_id : str
    +parent_id : str
    +generation : int
    +task_policy : TaskPolicy
    +meta_policy : MetaPolicy
    +lineage_notes : list[str]
  }

  class TaskPolicy {
    +weights : dict[str, float]
    +threshold : float
    +review_style : str
    +score(repo) float
    +classify(repo) int
  }

  class MetaPolicy {
    +focus_metric : str
    +weight_step : float
    +threshold_step : float
    +exploration_scale : float
    +memory : list[str]
  }

  class Evaluation {
    +fitness : float
    +train_accuracy : float
    +test_accuracy : float
    +false_positive_count : int
    +false_negative_count : int
    +false_positive_feature_avgs : dict
    +false_negative_feature_avgs : dict
  }

  class ArchiveEntry {
    +agent : HyperAgent
    +evaluation : Evaluation
    +created_iteration : int
  }

  HyperAgent *-- TaskPolicy
  HyperAgent *-- MetaPolicy
  ArchiveEntry *-- HyperAgent
  ArchiveEntry *-- Evaluation
```

The key structural property from the paper (arXiv:2603.19461v1): **both policies reside
in the same mutable record** — the procedure that produces future variants is itself
an editable artefact.

---

## 3. PromptAgent Structure

```mermaid
classDiagram
  class PromptAgent {
    +agent_id : str
    +parent_id : str
    +generation : int
    +prompt : str
    +meta_notes : list[str]
  }

  class PromptEvaluation {
    +fitness : float
    +rating : int
    +strengths : list[str]
    +gaps : list[str]
    +review_excerpt : str
    +codebase_ref : str
    +summary : str
  }

  class PromptArchiveEntry {
    +agent : PromptAgent
    +evaluation : PromptEvaluation
    +created_iteration : int
  }

  PromptArchiveEntry *-- PromptAgent
  PromptArchiveEntry *-- PromptEvaluation
```

The `PromptEngine` applies the same archive + mutation pattern as `HyperAgentEngine`,
but the evolvable artefact is a natural-language code-reviewer prompt rather than
a set of numeric weights. Fitness is the normalised human rating: `(rating − 1) / 4.0`.

---

## 4. Evolutionary Loop

```mermaid
flowchart TD
  SEED["Seed HyperAgent\nweights · threshold · style\nfocus · steps · exploration"]
  SEED --> ARC

  ARC["Archive\nall variants + scores + parent links"]

  ARC -->|"weighted selection\nfitness × exploration × novelty"| PARENT["Parent Agent"]

  PARENT -->|"meta_policy drives"| MUT

  MUT["Mutation\n① error-pressure weight update\n② stochastic noise\n③ threshold adjustment\n④ meta-param update"]

  MUT --> CHILD["Child HyperAgent"]
  CHILD --> EVAL

  EVAL["Evaluation\ntrain accuracy  ·  test accuracy\nFP count  ·  FN count"]

  EVAL -->|"improved?\nyes → shrink exploration\nplateau (5+ iters) → restart nudge\nno  → grow exploration"| ADJUST["Meta Adjustment"]
  ADJUST --> ARC

  EVAL -->|"record"| LOG["Progress Log\nSQLite + CSV"]
```

### Loop Steps

| # | Step | Key action |
|---|------|------------|
| 1 | Parent selection | Weighted sample: `P ∝ fitness × exploration_scale × weight_space_novelty` |
| 2 | Mutation | Error-pressure drives weight direction; `exploration_scale` sets noise amplitude |
| 3 | Evaluation | Score child on all 20 train + 10 test repos |
| 4 | Post-eval meta-adjust | `exploration_scale ↓` on improvement; plateau restart nudge after 5 stuck iterations |
| 5 | Archive update | Child unconditionally added (stepping-stones property) |
| 6 | Progress record | Metrics written to SQLite and CSV |

### Weight-Space Novelty

Parent selection uses k=3 nearest-neighbour mean Euclidean distance in the 5D weight
space as a novelty signal, normalised to [0, 1]:

```
novelty_score = 1.0 + normalised_knn_distance × 0.30
```

This replaces the old generation-depth proxy, grounding diversity pressure in the
actual parameter space rather than tree depth.

### Plateau Detection

If no fitness improvement occurs for 5 consecutive iterations, the post-evaluation
meta-adjustment fires a stronger restart nudge:
- `exploration_scale += 0.10` (vs normal +0.05)
- `weight_step` reset to mid-range `0.13`

---

## 5. Ablation Conditions

```mermaid
graph LR
  subgraph HA ["hyperagent  (full system)"]
    direction TB
    HA1["Weighted archive\nparent selection"]
    HA2["Adaptive meta policy\n(self-modifying)"]
    HA1 --> HA2
  end

  subgraph BL ["baseline  (frozen meta)"]
    direction TB
    BL1["Weighted archive\nparent selection"]
    BL2["Fixed meta policy\n(seed values only)"]
    BL1 --> BL2
  end

  subgraph NA ["no_archive  (greedy)"]
    direction TB
    NA1["Always current\nbest agent only"]
    NA2["Adaptive meta policy\n(self-modifying)"]
    NA1 --> NA2
  end
```

| Condition | Archive selection | Meta-policy update | Isolates |
|---|---|---|---|
| `hyperagent` | Weighted full archive | Adaptive | — (full system) |
| `baseline` | Weighted full archive | Frozen at seed | Meta-policy contribution |
| `no_archive` | Always current best | Adaptive | Archive contribution |

---

## 6. Database Schema

```mermaid
erDiagram
  Run {
    int    id PK
    string run_uuid
    string mode
    int    seed
    int    iterations_completed
    float  best_fitness
    float  best_test_accuracy
    string created_at
  }

  AgentRecord {
    int    id PK
    int    run_id FK
    string agent_id
    string parent_id
    int    generation
    int    created_iteration
    string task_policy_json
    string meta_policy_json
    string lineage_notes_json
    float  fitness
    float  train_accuracy
    float  test_accuracy
    int    false_positive_count
    int    false_negative_count
    string false_positive_feature_avgs_json
    string false_negative_feature_avgs_json
    string evaluation_summary
  }

  ProgressRecord {
    int    id PK
    int    run_id FK
    int    iteration
    float  best_fitness
    float  best_test_accuracy
    float  child_train_accuracy
    float  child_test_accuracy
    int    archive_size
    string meta_focus_metric
    float  meta_weight_step
    float  meta_threshold_step
    float  meta_exploration_scale
    string mutation_source
  }

  EventRecord {
    int    id PK
    int    run_id FK
    int    iteration
    string parent_agent_id
    string child_agent_id
    float  fitness_delta
    string summary
  }

  Account {
    int    id PK
    string name
    string platform
    string profile
    string created_at
  }

  AccountRepo {
    int    id PK
    int    account_id FK
    string repo_ref
    string name
    float  maintainability
    float  security
    float  test_coverage
    float  documentation
    float  simplicity
    int    label
  }

  Run ||--o{ AgentRecord    : "contains"
  Run ||--o{ ProgressRecord : "tracks"
  Run ||--o{ EventRecord    : "logs"
  Account ||--o{ AccountRepo : "has"
```

---

## 7. API Endpoints

### Engine

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/state` | Current engine state |
| `POST` | `/api/reset` | Start a new run; body: `{"mode": "hyperagent\|baseline\|no_archive"}` |
| `POST` | `/api/run` | Execute N iterations; body: `{"iterations": N}` |
| `GET` | `/api/metrics/json` | Per-iteration metrics as JSON |
| `GET` | `/api/metrics/csv` | Per-iteration metrics as CSV download |

### Run management

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/runs` | List all saved runs |
| `GET` | `/api/runs/{id}` | Single run snapshot |
| `POST` | `/api/runs/{id}/load` | Restore a saved run into engine |
| `DELETE` | `/api/runs/{id}` | Delete a saved run |

### Self-improving prompt engine

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/promptagent/state` | Active prompt, archive, iteration count |
| `POST` | `/api/promptagent/reset` | Start fresh; body: `{"seed_prompt": "..."}` optional |
| `POST` | `/api/promptagent/submit` | Record a review result; returns improved prompt |
| `GET` | `/api/promptagent/export` | Best prompt found so far |

### Accounts

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/accounts` | Add a synthetic or GitHub account |
| `GET` | `/api/accounts` | List accounts |
| `GET` | `/api/accounts/{id}/repos` | Repos for one account |
| `DELETE` | `/api/accounts/{id}` | Delete account |
| `POST` | `/api/accounts/apply-all` | Push all account repos into the engine dataset |

### Live review (requires OpenAI)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/review-repo` | Score a GitHub repo with the best agent + LLM |

---

## 8. Directory Layout

```text
hyperagents/
├── backend/
│   ├── app/
│   │   ├── engine.py                   # HyperAgentEngine — core evolutionary loop
│   │   ├── datasets.py                 # 20 train + 10 test repo fixtures
│   │   ├── database.py                 # SQLModel tables + Database class
│   │   ├── main.py                     # FastAPI app + route handlers
│   │   ├── openai_service.py           # Optional LLM mutation planner
│   │   ├── account_service.py          # Synthetic + GitHub repo generation
│   │   ├── github_service.py           # GitHub API wrapper
│   │   ├── settings.py                 # Env-driven config (reads .env.local)
│   │   ├── prompts/
│   │   │   ├── propose_mutation.md     # LLM prompt: weight mutation
│   │   │   └── review_repository.md   # LLM prompt: live repo review
│   │   └── selfimprovingprompt/
│   │       ├── engine.py               # PromptEngine — evolves text prompts
│   │       └── prompts/
│   │           └── mutate_agent_prompt.md  # LLM prompt: prompt mutation
│   └── pyproject.toml
├── scripts/
│   ├── run_experiment.py               # 3 conditions × 5 seeds × N iters → CSV
│   └── plot_results.py                 # Learning curves + meta drift figures
├── docs/
│   ├── GUIDE.md                        # Start here
│   ├── architecture.md                 # This file
│   └── methods.md                      # Methods section draft
├── results/                            # Auto-created at runtime; gitignored
├── experiments/                        # Cleaned CSVs committed for the paper
└── figures/                            # Paper-ready output figures
```
