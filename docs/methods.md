# 3  Methods

## 3.1  Problem Setting

We study whether a self-modifying meta-policy improves the efficiency of an
evolutionary agent optimisation loop.  The task domain is a simulated
code-repository quality classifier: given a five-dimensional feature vector
for a repository (maintainability, security, test coverage, documentation,
simplicity, each in [0, 1]) the agent must decide whether to accept or reject
the repository.  The ground-truth labels are fixed, making the evaluation
fully deterministic and enabling clean controlled comparisons across
conditions.

The train split contains 20 repositories (8 accepted, 12 rejected); the
held-out test split contains 10 repositories (4 accepted, 6 rejected).
Ten of the training examples and six of the test examples are clearly
separated; the remaining examples are deliberately borderline—with feature
profiles that fall near the decision boundary—so that the initial seed agent
achieves approximately 65 % train accuracy, leaving meaningful room for
improvement.

## 3.2  HyperAgent Architecture

Each agent is a self-contained record containing two co-evolving policies.

**Task policy** π_task controls how a repository is scored and classified:

| Parameter | Role |
|---|---|
| `weights` (5 floats, [0.25, 1.8]) | Per-feature importance multipliers |
| `threshold` (float, [2.4, 4.2]) | Accept/reject decision boundary |
| `review_style` ∈ {balanced, strict, lenient} | Offset applied to threshold (0, +0.09, −0.09) |

The predicted label is:

    score = Σ_f  weights[f] × repo[f]
            + rule_adjustments(repo)
    label = 1  iff  score ≥ threshold + style_offset

where `rule_adjustments` applies small fixed penalties for critically low
security (< 0.35) or test coverage (< 0.30) and a bonus for repos strong
on both maintainability and security.

**Meta policy** π_meta controls how future mutations are proposed:

| Parameter | Role |
|---|---|
| `focus_metric` | Feature to prioritise during the next mutation |
| `weight_step` | Step size for weight adjustments |
| `threshold_step` | Step size for threshold adjustments |
| `exploration_scale` | Noise amplitude added to weight updates |
| `memory` (list[str]) | Natural-language notes from prior iterations |

Both policies reside in the same mutable agent record—the hyperagent—and
both can be modified during a run.  This is the key structural property
highlighted by the HyperAgents paper (arXiv:2603.19461v1): the procedure
that generates future variants is itself an editable artefact.

## 3.3  Evolutionary Loop

Each iteration proceeds as follows:

1. **Parent selection.**  A parent is sampled from the archive using a
   weighted distribution combining exploitation (fitness), exploration
   (meta-policy exploration scale), and weight-space novelty.  Novelty is
   the mean Euclidean distance to the k=3 nearest neighbours in the 5D
   weight space, normalised to [0, 1] across the archive and scaled by 0.30:
   `novelty = 1.0 + normalised_knn_distance × 0.30`.  This grounds diversity
   pressure in the actual parameter space rather than a generation-depth proxy.
2. **Mutation.**  The parent's meta policy is applied to produce a child:
   error-pressure signals (false-positive and false-negative feature
   averages relative to the training distribution) drive directional weight
   updates; stochastic noise scaled by `exploration_scale` is added; the
   threshold is adjusted in the direction that reduces the dominant error
   type.  All meta-policy parameters are updated in the same step.
3. **Evaluation.**  The child is scored on the full train set and the
   held-out test set.
4. **Post-evaluation meta-adjustment.**  If the child improves over the
   parent, `exploration_scale` decreases (exploit the direction); otherwise
   it increases (diversify).  If no fitness improvement has occurred for
   5 or more consecutive iterations, a stronger plateau restart nudge is
   applied: `exploration_scale += 0.10` (vs normal +0.05) and `weight_step`
   is reset to mid-range (0.13) to escape the local optimum.
5. **Archive update.**  The child is unconditionally added to the archive.
6. **Progress recording.**  Per-iteration metrics—child train/test
   accuracy, meta-policy parameters, mutation source—are appended to the
   run log and persisted to SQLite.

## 3.4  Archive Mechanism

The archive stores every discovered agent variant together with its
evaluation scores and parent link.  Parent selection is weighted, not
greedy, so lower-fitness variants with high exploration scale or high
weight-space novelty can still be selected.  This "stepping stones"
property allows the population to escape local optima that would trap a
purely greedy hill-climber.

## 3.5  Ablation Conditions

Three conditions are compared in the experiments (Section 4).

| Condition | Archive selection | Meta-policy update |
|---|---|---|
| `hyperagent` (full system) | Weighted from full archive | Adaptive each iteration |
| `baseline` (frozen meta) | Weighted from full archive | Fixed at seed values |
| `no_archive` (greedy) | Always current best only | Adaptive each iteration |

In the `baseline` condition all meta-policy parameters (focus metric,
weight step, threshold step, exploration scale) are frozen at the values of
the seed agent for the duration of the run.  Only the task policy (weights,
threshold, review style) is allowed to evolve.  This condition isolates the
contribution of meta-policy self-modification.

In the `no_archive` condition the parent is always the single current best
agent, removing the stepping-stones mechanism.  This condition isolates the
contribution of archive-based diversity.

## 3.6  Evaluation Protocol

Each condition is run with five random seeds (seed ∈ {42, 123, 456, 789, 1011})
for 40 iterations.  All results report the mean best train fitness and mean
best test accuracy across seeds.  Because the domain is deterministic, seed
variance arises entirely from the stochastic parent-selection and noise
terms in the mutation operator.

Primary metrics:

- **Best train fitness** (monotonically non-decreasing): accuracy of the
  best-ever agent on the 20-example training set, recorded after each
  iteration.
- **Best test accuracy**: accuracy of the same best-ever agent on the
  10-example held-out test set.
- **Child train accuracy**: raw accuracy of the freshly mutated child
  (before archive selection), showing per-step mutation quality.
- **Meta-policy parameter trajectories**: weight step, threshold step, and
  exploration scale over iterations, used to verify that the meta policy is
  adapting in the `hyperagent` condition and frozen in the `baseline`
  condition.

All per-iteration metrics are written to `results/raw_metrics.csv` by
`scripts/run_experiment.py` and plotted by `scripts/plot_results.py`.
Figures are saved to `results/learning_curves.png` (primary learning curves)
and `results/meta_policy_drift.png` (meta-policy parameter trajectories).

## 3.7  Self-Improving Prompt Engine

As an extension of the hyperagent framework to natural language, we implement
a `PromptEngine` that treats a text prompt as the evolvable artefact.  The
task policy is a code-reviewer prompt; the meta policy is the mutation
strategy (gap-driven heuristic or LLM-guided).  Fitness is the normalised
human rating: `(rating − 1) / 4.0`, mapping the 1–5 scale to [0.0, 1.0].

Each iteration proceeds as follows:

1. The active prompt is run against a codebase by the user.
2. The user rates the output 1–5 and records strengths and gaps.
3. `submit_review()` archives the current prompt + evaluation.
4. Mutation produces an improved prompt via LLM (if configured) or the
   heuristic fallback (prepend specificity directives for rating ≤ 2;
   append gap-derived focus areas for rating = 3; reinforce primary
   strength for rating ≥ 4).
5. The improved prompt becomes active and is optionally written to disk.

This demonstrates that the core hyperagent mechanism—evolving both the
artefact and the strategy that improves it—generalises beyond numeric
parameter spaces to natural-language artefacts with human-in-the-loop
feedback.

## 3.8  Implementation Details

The backend is implemented in Python 3.11 with FastAPI (REST API) and
SQLModel (SQLite persistence).  Each run is assigned a unique identifier;
the full agent lineage, per-iteration metrics, and mutation events are
persisted immediately so that experiments survive process restarts and can
be resumed or exported at any point.  There is no frontend; all interaction
is via the REST API (`uvicorn app.main:app`) or the CLI scripts
(`scripts/run_experiment.py`).  Source code is available at
https://github.com/AISmithy/hyperagents.
