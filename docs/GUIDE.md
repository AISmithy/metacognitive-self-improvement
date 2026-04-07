# Hyperagents — Guide

> This guide assumes you are new to the project. No prior knowledge of AI research or the codebase is needed.

---

## What Is This Project?

Imagine a hiring manager whose job is to look at job applications and decide: **accept** or **reject**.

Over time, a good hiring manager does not just get better at reviewing applications — they also get better at *how they improve their own reviewing process*. They learn better ways to learn.

That is exactly what this project does, but for **code repositories** instead of job applications.

A **HyperAgent** is an AI reviewer that:
1. Looks at a code repository and scores it on 5 qualities
2. Decides: is this repo good enough to accept or not?
3. After each decision, **updates its own scoring rules** to do better next time
4. Also **updates the rules that control how it updates** — this is the "hyper" part

The project is a proof-of-concept implementation of the ideas from the research paper `arXiv:2603.19461`.

---

## The Core Idea in Plain English

Most AI systems improve their **answers**.

This system also improves its **improvement strategy**.

Think of it in layers:

| Layer | What it does | Called |
|---|---|---|
| Layer 1 | Scores and classifies a repo | **Task Policy** |
| Layer 2 | Controls how Layer 1 changes | **Meta Policy** |

Both layers live inside one agent and both can be changed by the system — that is what makes it a HyperAgent.

---

## What Does It Actually Do?

The system works with a dataset of **30 synthetic code repositories**:
- 20 are used for **training** (the agent learns from these)
- 10 are used for **testing** (we check if the learning generalised)

Each repository has 5 scores between 0 and 1:

| Feature | What it measures |
|---|---|
| **Maintainability** | Is the code easy to maintain? |
| **Security** | Does it have security vulnerabilities? |
| **Test Coverage** | Does it have tests? |
| **Documentation** | Is it well documented? |
| **Simplicity** | Is the code simple and clean? |

Each repo also has a label: **accept (1)** or **reject (0)**.

The agent learns to predict the label correctly by adjusting how much weight it gives to each feature.

---

## How the Agent Improves — Step by Step

This is the core loop that runs each time you call `/api/run` or `run_experiment.py`:

```
Step 1 — Pick a parent
         Choose an existing agent from the archive.
         Better agents are more likely to be chosen, but agents that are
         far from their neighbours in weight space get a novelty bonus —
         keeping the population diverse.

Step 2 — Mutate
         Create a child agent by tweaking the parent's weights.
         The meta policy decides HOW MUCH to tweak and in WHICH direction.
         Direction is guided by past mistakes:
           - Too many false positives? Raise the bar.
           - Too many false negatives? Lower the bar.

Step 3 — Evaluate
         Run the child agent over all 30 repos and measure accuracy.
         Count how many mistakes it makes and what kind.

Step 4 — Adjust the meta policy
         If the child improved → reduce exploration (consolidate gains).
         If no improvement in 5+ iterations → plateau restart nudge
           (boost exploration scale, reset weight step to mid-range).
         Otherwise → small exploration increase.

Step 5 — Save to archive
         Every child is saved, even bad ones.
         This lets the system revisit earlier paths that might lead somewhere.

Step 6 — Log results
         Write all scores to SQLite database and CSV file.
```

Then repeat from Step 1.

---

## The Three Experiment Modes

You can run the system in three different modes. These exist to prove which parts of the design actually matter.

| Mode | What changes | What it proves |
|---|---|---|
| `hyperagent` (full) | Both task and meta policy evolve | The complete system |
| `baseline` (frozen meta) | Meta policy is locked; only task policy evolves | That meta-improvement adds value |
| `no_archive` (greedy) | Always mutates from the single best agent | That keeping old variants adds value |

Key finding: both archive conditions outperform no_archive — keeping stepping-stone variants matters.

---

## The Self-Improving Prompt Engine

Beyond numeric weights, this project also evolves **text prompts** for code review.

The idea: you have a prompt you use with an LLM to review codebases. After each review you rate the output and note what it got right and wrong. The system uses that feedback to produce a better prompt for the next cycle.

```
Step 1 — Use the active prompt to review a codebase with your LLM.
Step 2 — Read the output. Rate it 1–5. Note strengths and gaps.
Step 3 — POST to /api/promptagent/submit with your feedback.
Step 4 — The system archives the current prompt + evaluation.
Step 5 — Mutation produces an improved prompt (LLM or heuristic).
Step 6 — The improved prompt becomes active.
```

Fitness for this engine is the normalised rating: `(rating − 1) / 4.0`.

---

## Prerequisites

You need:
- **Python 3.11 or newer** — [python.org/downloads](https://python.org/downloads)

Check you have it:
```bash
python --version   # should say 3.11+
```

No Node.js or browser is required. There is no frontend.

---

## Step 1 — Get the code

```bash
git clone https://github.com/AISmithy/hyperagents.git
cd hyperagents
```

---

## Step 2 — Install the backend

```bash
cd backend
pip install -e .
```

---

## Step 3 — Start the API server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

You should see:
```
Application startup complete.
```

Leave this running in one terminal. Or skip the server entirely and use the CLI (see below).

---

## Using the API

### Check the engine state

```bash
curl http://localhost:8000/api/state | python -m json.tool
```

### Run an experiment

```bash
# Reset to hyperagent mode
curl -X POST http://localhost:8000/api/reset \
     -H "Content-Type: application/json" \
     -d '{"mode": "hyperagent"}'

# Run 10 iterations
curl -X POST http://localhost:8000/api/run \
     -H "Content-Type: application/json" \
     -d '{"iterations": 10}'

# Download metrics as CSV
curl http://localhost:8000/api/metrics/csv -o metrics.csv
```

### Compare all three modes

Repeat the reset + run cycle for each mode, then compare the `best_test_accuracy` values:

```bash
for mode in hyperagent baseline no_archive; do
  curl -s -X POST http://localhost:8000/api/reset \
       -H "Content-Type: application/json" \
       -d "{\"mode\": \"$mode\"}" > /dev/null
  curl -s -X POST http://localhost:8000/api/run \
       -H "Content-Type: application/json" \
       -d '{"iterations": 30}' \
  | python -m json.tool | grep best_test_accuracy
done
```

### Use the self-improving prompt engine

```bash
# Get the seed prompt
curl http://localhost:8000/api/promptagent/state | python -m json.tool

# Submit a review result
curl -X POST http://localhost:8000/api/promptagent/submit \
     -H "Content-Type: application/json" \
     -d '{
       "review_text": "The code lacks documentation and has no tests.",
       "rating": 2,
       "strengths": ["Security checks are thorough"],
       "gaps": ["No documentation analysis", "Missed test coverage"],
       "codebase_ref": "my-repo @ main"
     }' | python -m json.tool

# Export the best prompt
curl http://localhost:8000/api/promptagent/export | python -c "import sys,json; print(json.load(sys.stdin)['prompt'])"
```

---

## Using the CLI (no server needed)

Run the full ablation experiment directly without starting the API:

```bash
# from repo root
python scripts/run_experiment.py --iterations 30 --seeds 5
```

This runs 3 conditions × 5 seeds × 30 iterations and saves everything to `results/raw_metrics.csv`.

Generate the figures:
```bash
python scripts/plot_results.py
```

Outputs:
- `results/learning_curves.png` — accuracy over iterations for all 3 conditions
- `results/meta_policy_drift.png` — how the meta-policy parameters evolve

---

## Common Questions

**Q: What is "fitness"?**
The agent's accuracy on the training set. Higher is better. Starts around 65% and typically reaches 85%+.

**Q: Why does the archive keep bad agents?**
Bad agents are stepping stones. A suboptimal agent at generation 5 might lead to an excellent agent at generation 10 via a path the greedy approach would never find.

**Q: What is train vs test accuracy?**
Train accuracy = how well the agent does on the 20 repos it learned from.
Test accuracy = how well it does on the 10 repos it has never seen. Test accuracy tells you if the learning generalised or just memorised.

**Q: What is the plateau restart nudge?**
If no fitness improvement occurs for 5 consecutive iterations, the engine boosts the exploration scale more aggressively and resets the weight step to mid-range. This helps escape local optima without discarding the archive.

**Q: What is weight-space novelty?**
For each archive entry, the engine computes the mean Euclidean distance to its 3 nearest neighbours in the 5D weight space. Entries that are far from their neighbours get a selection bonus, keeping the archive diverse.

**Q: What is the self-improving prompt engine?**
A second evolvable artefact. Instead of numeric weights, the "task policy" is a text prompt for LLM-based code review. Fitness is the normalised human rating. Each cycle the prompt mutates based on your feedback.

**Q: Can I run without an OpenAI key?**
Yes. The heuristic engine runs fully offline. LLM mutation is optional for both the weight-mutation planner and the prompt-mutation engine.

---

## Key Files to Read First

If you want to understand the code, read these in order:

1. [backend/app/datasets.py](../backend/app/datasets.py) — the 30 repos (short, no dependencies)
2. [backend/app/engine.py](../backend/app/engine.py) — the full evolutionary loop
3. [backend/app/selfimprovingprompt/engine.py](../backend/app/selfimprovingprompt/engine.py) — the prompt evolution loop
4. [backend/app/main.py](../backend/app/main.py) — the API that connects everything
5. [scripts/run_experiment.py](../scripts/run_experiment.py) — how experiments are run in batch
