"""
generate_user_manual.py
=======================
Generates docs/user_manual.pdf -- a complete user manual for the HyperAgents
backend: installation, running experiments, getting output, plotting results,
and interpreting findings.

Usage:
    python scripts/generate_user_manual.py
"""
from __future__ import annotations
from pathlib import Path
from fpdf import FPDF

OUT = Path(__file__).resolve().parents[1] / "docs" / "user_manual.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)

# Windows system fonts (Unicode-safe)
FONT_DIR  = Path("C:/Windows/Fonts")
FONT_REG  = str(FONT_DIR / "arial.ttf")
FONT_BOLD = str(FONT_DIR / "arialbd.ttf")
FONT_ITA  = str(FONT_DIR / "ariali.ttf")
FONT_MONO = str(FONT_DIR / "cour.ttf")       # Courier New for code blocks

# Colour palette (R, G, B)
BROWN    = (184,  88,  47)
TEAL     = ( 26, 125, 121)
DARK     = ( 30,  25,  18)
MUTED    = (100,  85,  65)
CREAM    = (255, 252, 246)
LIGHT_BG = (245, 238, 228)
CODE_BG  = (235, 240, 245)
LINE     = (210, 195, 175)
GREEN    = ( 40, 140,  80)
RED      = (180,  50,  40)


class Manual(FPDF):
    def __init__(self):
        super().__init__("P", "mm", "A4")
        self.add_font("Arial",   "",  FONT_REG)
        self.add_font("Arial",   "B", FONT_BOLD)
        self.add_font("Arial",   "I", FONT_ITA)
        self.add_font("Mono",    "",  FONT_MONO)
        self.set_auto_page_break(auto=True, margin=24)
        self.set_margins(22, 20, 22)
        self._current_section = ""

    # ── Chrome ────────────────────────────────────────────────────────────────

    def header(self):
        if self.page == 1:
            return
        self.set_font("Arial", "B", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 6, "HyperAgents  |  User Manual", align="L", new_x="RIGHT", new_y="TOP")
        self.cell(0, 6, f"Page {self.page}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*LINE)
        self.set_line_width(0.25)
        self.line(22, self.get_y(), 190, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-14)
        self.set_font("Arial", "I", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 6, "github.com/AISmithy/hyperagents  |  arXiv:2603.19461", align="C")

    # ── Typography helpers ────────────────────────────────────────────────────

    def _hrule(self, color=BROWN, weight=0.6):
        self.set_draw_color(*color)
        self.set_line_width(weight)
        self.line(22, self.get_y(), 190, self.get_y())
        self.ln(4)

    def h1(self, text: str):
        self.ln(4)
        self.set_x(self.l_margin)
        self.set_font("Arial", "B", 15)
        self.set_text_color(*BROWN)
        self.multi_cell(self.epw, 8, text, new_x="LMARGIN", new_y="NEXT")
        self._hrule()

    def h2(self, text: str):
        self.ln(3)
        self.set_x(self.l_margin)
        self.set_font("Arial", "B", 11)
        self.set_text_color(*TEAL)
        self.multi_cell(self.epw, 6, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def h3(self, text: str):
        self.ln(2)
        self.set_x(self.l_margin)
        self.set_font("Arial", "B", 10)
        self.set_text_color(*DARK)
        self.multi_cell(self.epw, 5.5, text, new_x="LMARGIN", new_y="NEXT")

    def body(self, text: str, spacing: float = 3):
        self.set_x(self.l_margin)
        self.set_font("Arial", "", 10.5)
        self.set_text_color(*DARK)
        self.multi_cell(self.epw, 5.8, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(spacing)

    def bullet(self, items: list[str], indent: int = 5):
        self.set_font("Arial", "", 10.5)
        self.set_text_color(*DARK)
        for item in items:
            self.set_x(self.l_margin)
            self.cell(indent, 5.8, "\u2022", new_x="RIGHT", new_y="TOP")
            self.multi_cell(self.epw - indent, 5.8, item, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def numbered(self, items: list[str]):
        self.set_font("Arial", "", 10.5)
        self.set_text_color(*DARK)
        for i, item in enumerate(items, 1):
            self.set_x(self.l_margin)
            self.cell(7, 5.8, f"{i}.", new_x="RIGHT", new_y="TOP")
            self.multi_cell(self.epw - 7, 5.8, item, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def code(self, lines: list[str] | str):
        """Monospaced code block with shaded background."""
        if isinstance(lines, str):
            lines = [lines]
        text = "\n".join(lines)
        # estimate height
        line_h = 5.2
        n_lines = text.count("\n") + 1
        bh = n_lines * line_h + 6
        bx, bw = self.l_margin, self.epw
        by = self.get_y()
        self.set_fill_color(*CODE_BG)
        self.set_draw_color(*LINE)
        self.set_line_width(0.2)
        self.rect(bx, by, bw, bh, "FD")
        self.set_xy(bx + 3, by + 3)
        self.set_font("Mono", "", 9)
        self.set_text_color(*DARK)
        self.multi_cell(bw - 6, line_h, text, new_x="LMARGIN", new_y="NEXT")
        self.set_x(self.l_margin)
        self.ln(4)

    def callout(self, heading: str, text: str, color=TEAL):
        bx, bw = self.l_margin, self.epw
        by = self.get_y()
        n = max(2, len(text) // 80 + 2)
        bh = 7 + n * 5.5 + 4
        self.set_fill_color(*LIGHT_BG)
        self.set_draw_color(*color)
        self.set_line_width(0.8)
        # left accent bar
        self.rect(bx, by, 1.5, bh, "F")
        # background
        self.set_line_width(0.2)
        self.set_draw_color(*LINE)
        self.rect(bx + 1.5, by, bw - 1.5, bh, "FD")
        self.set_xy(bx + 5, by + 3)
        self.set_font("Arial", "B", 9.5)
        self.set_text_color(*color)
        self.cell(0, 5, heading, new_x="LMARGIN", new_y="NEXT")
        self.set_x(bx + 5)
        self.set_font("Arial", "", 10)
        self.set_text_color(*DARK)
        self.multi_cell(bw - 8, 5.5, text)
        self.ln(5)

    def table(self, headers: list[str], rows: list[list[str]], col_widths: list[int] | None = None):
        n = len(headers)
        if col_widths is None:
            col_widths = [int(self.epw / n)] * n
        # Header row
        self.set_font("Arial", "B", 9.5)
        self.set_fill_color(*TEAL)
        self.set_text_color(255, 255, 255)
        self.set_x(self.l_margin)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 6.5, h, border=0, fill=True,
                      new_x="RIGHT" if i < n - 1 else "LMARGIN",
                      new_y="TOP" if i < n - 1 else "NEXT")
        # Data rows
        self.set_font("Arial", "", 9.5)
        self.set_text_color(*DARK)
        for ri, row in enumerate(rows):
            fill_color = LIGHT_BG if ri % 2 == 0 else (255, 255, 255)
            self.set_fill_color(*fill_color)
            self.set_x(self.l_margin)
            # measure max height for this row
            row_h = 6
            for i, cell in enumerate(row):
                self.set_xy(self.l_margin + sum(col_widths[:i]), self.get_y())
                self.multi_cell(col_widths[i], row_h, cell, border="B",
                                fill=True, new_x="RIGHT", new_y="TOP")
            self.set_x(self.l_margin)
            self.ln(row_h)
        self.set_x(self.l_margin)
        self.ln(4)

    def kv_table(self, rows: list[tuple[str, str]], col1: int = 55):
        col2 = int(self.epw) - col1
        for ri, (k, v) in enumerate(rows):
            fill = LIGHT_BG if ri % 2 == 0 else (255, 255, 255)
            self.set_fill_color(*fill)
            self.set_x(self.l_margin)
            self.set_font("Arial", "B", 9.5)
            self.set_text_color(*BROWN)
            self.cell(col1, 6.5, k, border="B", fill=True, new_x="RIGHT", new_y="TOP")
            self.set_font("Arial", "", 9.5)
            self.set_text_color(*DARK)
            self.multi_cell(col2, 6.5, v, border="B", fill=True, new_x="LMARGIN", new_y="NEXT")
        self.set_x(self.l_margin)
        self.ln(4)


# ── Sections ──────────────────────────────────────────────────────────────────

def cover(doc: Manual):
    doc.add_page()
    doc.set_fill_color(*CREAM)
    doc.rect(0, 0, 210, 297, "F")

    # accent bar
    doc.set_fill_color(*BROWN)
    doc.rect(0, 0, 210, 6, "F")

    doc.ln(40)
    doc.set_x(doc.l_margin)
    doc.set_font("Arial", "B", 36)
    doc.set_text_color(*BROWN)
    doc.multi_cell(doc.epw, 14, "HyperAgents", align="C", new_x="LMARGIN", new_y="NEXT")

    doc.ln(1)
    doc.set_x(doc.l_margin)
    doc.set_font("Arial", "", 15)
    doc.set_text_color(*TEAL)
    doc.multi_cell(doc.epw, 7, "User Manual", align="C", new_x="LMARGIN", new_y="NEXT")

    doc.ln(2)
    doc.set_draw_color(*MUTED)
    doc.set_line_width(0.5)
    doc.line(55, doc.get_y(), 155, doc.get_y())

    doc.ln(8)
    doc.set_x(doc.l_margin)
    doc.set_font("Arial", "I", 10.5)
    doc.set_text_color(*MUTED)
    doc.multi_cell(doc.epw, 6,
        "Installation  \u00b7  Running Experiments  \u00b7  Reading Output\n"
        "Plotting Results  \u00b7  Interpreting Findings  \u00b7  API Reference",
        align="C", new_x="LMARGIN", new_y="NEXT")

    doc.ln(14)
    doc.callout(
        "Who is this manual for?",
        "Anyone who wants to run HyperAgents experiments, understand "
        "the output, and draw conclusions from the results. No prior "
        "knowledge of machine learning is required. Basic familiarity "
        "with a terminal (command prompt) is helpful for the CLI sections.",
    )

    doc.ln(4)
    doc.set_x(doc.l_margin)
    doc.set_font("Arial", "", 10)
    doc.set_text_color(*MUTED)
    doc.multi_cell(doc.epw, 5.5,
        "Research prototype  \u00b7  Based on arXiv:2603.19461v1\n"
        "github.com/AISmithy/hyperagents",
        align="C", new_x="LMARGIN", new_y="NEXT")

    # bottom bar
    doc.set_fill_color(*TEAL)
    doc.rect(0, 291, 210, 6, "F")


def toc(doc: Manual):
    doc.add_page()
    doc.h1("Contents")
    entries = [
        ("1", "What HyperAgents Does",              "3"),
        ("2", "Installation",                         "4"),
        ("3", "Running Your First Experiment",        "5"),
        ("4", "Getting Output",                       "7"),
        ("5", "Plotting Results",                     "9"),
        ("6", "Interpreting the Plots",               "11"),
        ("7", "The Three Ablation Modes",             "13"),
        ("8", "The Self-Improving Prompt Engine",     "14"),
        ("9", "API Quick Reference",                  "16"),
        ("10", "Glossary",                            "17"),
    ]
    doc.set_font("Arial", "", 10.5)
    doc.set_text_color(*DARK)
    for num, title, page in entries:
        doc.set_x(doc.l_margin)
        doc.set_font("Arial", "B", 10.5)
        doc.set_text_color(*TEAL)
        doc.cell(8, 7, num, new_x="RIGHT", new_y="TOP")
        doc.set_font("Arial", "", 10.5)
        doc.set_text_color(*DARK)
        avail = doc.epw - 8 - 12
        doc.cell(avail, 7, title, new_x="RIGHT", new_y="TOP")
        doc.set_font("Arial", "", 10.5)
        doc.set_text_color(*MUTED)
        doc.cell(12, 7, page, align="R", new_x="LMARGIN", new_y="NEXT")
        doc.set_draw_color(*LINE)
        doc.set_line_width(0.15)
        doc.line(doc.l_margin, doc.get_y(), 190, doc.get_y())


def section_what(doc: Manual):
    doc.add_page()
    doc.h1("1.  What HyperAgents Does")

    doc.body(
        "HyperAgents is a research tool that builds an AI agent capable of "
        "improving not just its own decisions, but also the method it uses "
        "to improve those decisions. The technical term is metacognitive "
        "self-modification."
    )

    doc.h2("The task")
    doc.body(
        "The agent's job is to classify software repositories as ACCEPT or REJECT "
        "based on five quality dimensions:"
    )
    doc.kv_table([
        ("Maintainability", "How readable and easy to change is the code?"),
        ("Security",        "Are there known vulnerability patterns?"),
        ("Test Coverage",   "Does the codebase include meaningful tests?"),
        ("Documentation",   "Are interfaces and usage well documented?"),
        ("Simplicity",      "Is the code free of unnecessary complexity?"),
    ])
    doc.body(
        "Each dimension is scored 0.0 to 1.0. The agent combines these five "
        "scores using a weighted sum and compares the result to a threshold. "
        "If the sum clears the threshold, the repo is accepted."
    )

    doc.h2("The two policies")
    doc.kv_table([
        ("Task Policy",
         "The five feature weights, decision threshold, and review style "
         "(balanced / strict / lenient). This directly controls ACCEPT vs REJECT."),
        ("Meta Policy",
         "Controls HOW the task policy mutates: which feature to focus on, "
         "how large each step is, and how much random noise to add. This is "
         "the self-improvement strategy."),
    ])
    doc.body(
        "Both policies live inside the same agent record and both evolve during a run. "
        "That is what makes it a HyperAgent rather than a plain evolutionary optimizer."
    )

    doc.h2("The archive")
    doc.body(
        "Every agent variant ever produced is kept in an archive -- even ones "
        "that performed worse than their parent. This 'stepping-stones' property "
        "allows the system to backtrack through dead ends and find paths that a "
        "greedy optimizer would miss."
    )

    doc.callout(
        "Key metric: test accuracy",
        "Train accuracy measures how well the agent does on repos it learned from. "
        "Test accuracy measures how well it does on repos it has NEVER seen. "
        "Test accuracy is the true measure of learning -- it cannot be faked by "
        "memorisation. A good run reaches 85-95% test accuracy.",
    )


def section_install(doc: Manual):
    doc.add_page()
    doc.h1("2.  Installation")

    doc.h2("Requirements")
    doc.bullet([
        "Python 3.11 or newer  (python.org/downloads)",
        "Git  (git-scm.com)",
        "4 MB disk space for the virtual environment",
    ])
    doc.callout(
        "Check your Python version",
        "Open a terminal and run:   python --version\n"
        "You should see Python 3.11.x or higher.",
    )

    doc.h2("Step 1 -- Get the code")
    doc.code([
        "git clone https://github.com/AISmithy/hyperagents.git",
        "cd hyperagents",
    ])

    doc.h2("Step 2 -- Create and activate a virtual environment")
    doc.body("On Windows (PowerShell):")
    doc.code([
        "python -m venv .venv",
        ".venv\\Scripts\\Activate.ps1",
    ])
    doc.body("On macOS / Linux:")
    doc.code([
        "python3 -m venv .venv",
        "source .venv/bin/activate",
    ])

    doc.h2("Step 3 -- Install the backend")
    doc.code([
        "cd backend",
        "pip install -e .",
        "cd ..",
    ])
    doc.body(
        "This installs FastAPI, uvicorn, SQLModel, and the OpenAI SDK. "
        "The process takes 30-60 seconds on a typical connection."
    )

    doc.h2("Step 4 -- Install optional analysis packages")
    doc.body("Only needed if you want to generate figures from the CLI:")
    doc.code(["pip install matplotlib"])

    doc.h2("Step 5 -- Start the API server")
    doc.body("On Windows, use the provided script:")
    doc.code(["powershell -ExecutionPolicy Bypass -File run.ps1"])
    doc.body("Or start manually:")
    doc.code([
        "cd backend",
        "uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload",
    ])
    doc.body("You should see:")
    doc.code(["Application startup complete."])
    doc.body(
        "The API is now available at http://127.0.0.1:8000\n"
        "Interactive docs (Swagger UI) are at http://127.0.0.1:8000/docs"
    )

    doc.h2("Optional: OpenAI integration")
    doc.body("Create backend/.env.local (never committed to git):")
    doc.code([
        "OPENAI_API_KEY=your_key_here",
        "OPENAI_MODEL=gpt-4o-mini",
        "HYPERAGENTS_USE_OPENAI=1",
    ])
    doc.body(
        "Without these settings the system runs fully offline. The heuristic "
        "engine produces equally valid research results."
    )


def section_first_run(doc: Manual):
    doc.add_page()
    doc.h1("3.  Running Your First Experiment")

    doc.h2("Option A -- Command line (recommended for research)")
    doc.body(
        "The CLI runner executes the full ablation matrix without any server "
        "interaction. Results are written directly to a CSV file."
    )
    doc.code([
        "# from the repo root, with .venv active",
        "python scripts/run_experiment.py --iterations 30 --seeds 5",
    ])
    doc.body("This runs:")
    doc.kv_table([
        ("3 conditions",   "hyperagent, baseline, no_archive"),
        ("5 seeds each",   "42, 123, 456, 789, 1011"),
        ("30 iterations",  "per run"),
        ("= 15 runs",      "450 data points total"),
        ("Output",         "results/raw_metrics.csv"),
    ])
    doc.body("You should see progress like this:")
    doc.code([
        "Running 15 experiments (3 conditions x 5 seeds x 30 iterations)",
        "",
        "  [ 1/15] hyperagent  seed=42   best_train=0.850  best_test=0.900  (0.12s)",
        "  [ 2/15] hyperagent  seed=123  best_train=0.850  best_test=0.900  (0.11s)",
        "  ...",
        "  [15/15] no_archive  seed=1011 best_train=0.800  best_test=0.800  (0.10s)",
        "",
        "Saved 450 rows -> results/raw_metrics.csv",
    ])
    doc.callout(
        "Quick test run",
        "To get a fast result during development, use fewer iterations and seeds:\n"
        "python scripts/run_experiment.py --iterations 10 --seeds 2\n"
        "This runs in under 5 seconds and produces a smaller CSV.",
    )

    doc.h2("Option B -- REST API (good for inspection and step-by-step control)")
    doc.body("Make sure the server is running (Step 5 in Installation), then:")
    doc.h3("1. Reset the engine to a mode")
    doc.code([
        'curl -X POST http://localhost:8000/api/reset \\',
        '     -H "Content-Type: application/json" \\',
        '     -d \'{"mode": "hyperagent"}\'',
    ])
    doc.h3("2. Run iterations")
    doc.code([
        'curl -X POST http://localhost:8000/api/run \\',
        '     -H "Content-Type: application/json" \\',
        '     -d \'{"iterations": 30}\'',
    ])
    doc.h3("3. Inspect the best agent found")
    doc.code([
        "curl http://localhost:8000/api/state | python -m json.tool",
    ])
    doc.h3("4. Run all three modes in sequence")
    doc.code([
        "for mode in hyperagent baseline no_archive; do",
        '  curl -s -X POST localhost:8000/api/reset \\',
        '       -H "Content-Type: application/json" \\',
        '       -d "{\\\"mode\\\": \\\"$mode\\\"}" > /dev/null',
        '  curl -s -X POST localhost:8000/api/run \\',
        '       -H "Content-Type: application/json" \\',
        '       -d \'{"iterations": 30}\' | python -m json.tool',
        "done",
    ])

    doc.h2("Understanding mode names")
    doc.table(
        ["Mode flag", "Paper label", "What is fixed"],
        [
            ["hyperagent",  "full",         "Nothing -- full system"],
            ["baseline",    "frozen_meta",  "Meta policy frozen at seed values"],
            ["no_archive",  "no_archive",   "Archive disabled; always mutate from current best"],
        ],
        col_widths=[45, 45, 78],
    )


def section_output(doc: Manual):
    doc.add_page()
    doc.h1("4.  Getting Output")

    doc.h2("The metrics CSV")
    doc.body(
        "The primary output of the CLI runner is results/raw_metrics.csv. "
        "Each row represents one iteration of one run:"
    )
    doc.table(
        ["Column", "Type", "Description"],
        [
            ["condition",              "string",  "hyperagent / baseline / no_archive"],
            ["label",                  "string",  "Paper label: full / frozen_meta / no_archive"],
            ["seed",                   "int",     "Random seed for this run"],
            ["iteration",              "int",     "Step number (0 = seed agent)"],
            ["best_fitness",           "float",   "Best train accuracy seen so far (non-decreasing)"],
            ["best_test_accuracy",     "float",   "Corresponding test accuracy"],
            ["child_train_accuracy",   "float",   "Raw train accuracy of the child just produced"],
            ["child_test_accuracy",    "float",   "Raw test accuracy of the child just produced"],
            ["archive_size",           "int",     "Total agents in archive at this iteration"],
            ["meta_focus_metric",      "string",  "Feature the meta policy is prioritising"],
            ["meta_weight_step",       "float",   "Current step size for weight updates"],
            ["meta_threshold_step",    "float",   "Current step size for threshold updates"],
            ["meta_exploration_scale", "float",   "Current noise amplitude"],
            ["mutation_source",        "string",  "heuristic or llm"],
            ["mode",                   "string",  "Same as condition"],
        ],
        col_widths=[52, 18, 98],
    )

    doc.h2("Fetching metrics from the API")
    doc.body("If you ran via the API, fetch the same data:")
    doc.h3("As JSON")
    doc.code([
        "curl http://localhost:8000/api/metrics/json | python -m json.tool",
    ])
    doc.h3("As CSV (download to file)")
    doc.code([
        "curl http://localhost:8000/api/metrics/csv -o my_run.csv",
    ])

    doc.h2("The SQLite database")
    doc.body(
        "Every run made via the API is also persisted to hyperagents.db "
        "in the repo root. You can query it with any SQLite client or via the API:"
    )
    doc.code([
        "# List all saved runs",
        "curl http://localhost:8000/api/runs | python -m json.tool",
        "",
        "# Get full snapshot of run #3",
        "curl http://localhost:8000/api/runs/3 | python -m json.tool",
        "",
        "# Restore run #3 into the active engine",
        "curl -X POST http://localhost:8000/api/runs/3/load",
    ])

    doc.h2("The state snapshot")
    doc.body(
        "GET /api/state returns a rich JSON snapshot. Key fields:"
    )
    doc.kv_table([
        ("best_agent.evaluation.fitness",        "Best train accuracy (0-1)"),
        ("best_agent.evaluation.test_accuracy",  "Best test accuracy (0-1)"),
        ("best_agent.agent.task_policy.weights", "Current feature weights"),
        ("best_agent.agent.meta_policy",         "Current meta-policy parameters"),
        ("archive",                              "Array of ALL agent variants ever created"),
        ("progress",                             "Per-iteration metrics array"),
        ("recent_events",                        "Last 12 mutation events (newest first)"),
        ("provider.mode",                        "'openai' or 'heuristic'"),
    ])

    doc.callout(
        "Tip: pretty-print with jq",
        "If you have jq installed, it is easier to read:\n"
        "curl http://localhost:8000/api/state | jq '.best_agent.evaluation'\n"
        "curl http://localhost:8000/api/state | jq '.progress[-5:]'",
    )


def section_plotting(doc: Manual):
    doc.add_page()
    doc.h1("5.  Plotting Results")

    doc.h2("Generate figures from the CLI")
    doc.body(
        "After running run_experiment.py, generate the standard paper figures:"
    )
    doc.code([
        "# Must have matplotlib installed: pip install matplotlib",
        "python scripts/plot_results.py",
    ])
    doc.body("This produces two files:")
    doc.kv_table([
        ("results/learning_curves.png",
         "Two-panel plot: best train accuracy (left) and best test "
         "accuracy (right) over iterations, with mean +/- std bands "
         "across all seeds."),
        ("results/meta_policy_drift.png",
         "Three-panel plot showing how weight_step, threshold_step, "
         "and exploration_scale evolve over iterations in the "
         "hyperagent vs baseline conditions."),
    ])

    doc.h2("Learning curves figure")
    doc.body(
        "The learning curves figure is the primary result figure. "
        "It shows three coloured lines, one per condition:"
    )
    doc.kv_table([
        ("Brown / warm",  "hyperagent (full system)"),
        ("Teal / cool",   "baseline (frozen meta policy)"),
        ("Earthy / muted","no_archive (greedy)"),
    ])
    doc.body(
        "Each line shows the mean across all 5 seeds. The shaded band "
        "around each line shows +/- one standard deviation -- narrower "
        "bands mean more consistent results across seeds."
    )

    doc.h2("Meta-policy drift figure")
    doc.body(
        "The meta-policy drift figure has three panels, one for each "
        "meta-policy parameter. It compares only hyperagent vs baseline:"
    )
    doc.kv_table([
        ("Weight step",      "How large each weight update is. Goes up when the agent "
                             "is not improving, down when it is."),
        ("Threshold step",   "How aggressively the decision threshold is shifted. "
                             "Increases when false positive / negative counts diverge."),
        ("Exploration scale","Noise amplitude. The hyperagent condition shows adaptive "
                             "drift; the baseline stays flat (frozen)."),
    ])
    doc.body(
        "The baseline lines will be flat or nearly flat for all three parameters "
        "(the meta policy is frozen). The hyperagent lines should drift -- this "
        "is the visual signature of metacognitive self-modification."
    )

    doc.h2("Custom analysis in Python")
    doc.body("Load the CSV and build your own charts:")
    doc.code([
        "import csv",
        "from collections import defaultdict",
        "",
        "rows = list(csv.DictReader(open('results/raw_metrics.csv')))",
        "",
        "# Group by condition and iteration",
        "by_cond = defaultdict(lambda: defaultdict(list))",
        "for r in rows:",
        "    by_cond[r['condition']][int(r['iteration'])].append(",
        "        float(r['best_test_accuracy']))",
        "",
        "# Print final mean test accuracy per condition",
        "for cond, iters in by_cond.items():",
        "    last = max(iters.keys())",
        "    vals = iters[last]",
        "    mean = sum(vals) / len(vals)",
        "    print(f'{cond}: {mean:.3f}')",
    ])
    doc.body("Or with pandas (pip install pandas):")
    doc.code([
        "import pandas as pd",
        "df = pd.read_csv('results/raw_metrics.csv')",
        "",
        "# Final test accuracy per condition (mean +/- std)",
        "final = df.groupby(['condition', 'seed'])['best_test_accuracy'].last()",
        "print(final.groupby('condition').agg(['mean', 'std']).round(3))",
        "",
        "# Learning curve for one condition",
        "ha = df[df['condition'] == 'hyperagent']",
        "curve = ha.groupby('iteration')['best_test_accuracy'].mean()",
        "print(curve.tail(10))",
    ])


def section_interpret(doc: Manual):
    doc.add_page()
    doc.h1("6.  Interpreting the Plots")

    doc.h2("What to look for in the learning curves")

    doc.h3("Shape of the lines")
    doc.body(
        "All three conditions start at approximately the same accuracy (~65%). "
        "A well-behaved run shows a rapid rise in the first 5-10 iterations "
        "followed by a plateau as the agent approaches the classification limit "
        "of the dataset."
    )
    doc.kv_table([
        ("Steep early rise",
         "Good -- the error-pressure mutation is working. The agent is quickly "
         "identifying which features to emphasise."),
        ("Flat line from the start",
         "Something is wrong -- check that the mode was set correctly "
         "and the seed agent was initialised."),
        ("Line drops then recovers",
         "Normal in no_archive mode. Without stepping stones the agent "
         "sometimes takes a detour before finding a better path."),
        ("Line rises, then plateaus, then rises again",
         "Plateau restart nudge fired. The meta policy increased "
         "exploration_scale after 5 stuck iterations, allowing escape."),
    ])

    doc.h3("Gaps between conditions")
    doc.body("The expected ordering from top to bottom is:")
    doc.numbered([
        "hyperagent (full) -- highest, because both policies adapt.",
        "baseline (frozen meta) -- middle, task policy adapts but meta is frozen.",
        "no_archive (greedy) -- lowest, tends to plateau around 75-80%.",
    ])
    doc.body(
        "If hyperagent and baseline are very close, it means the meta policy "
        "contribution is small for the chosen seed set -- this is a valid "
        "finding, not an error."
    )

    doc.h3("Train vs test gap")
    doc.body(
        "It is normal for train accuracy to be slightly higher than test accuracy. "
        "A large gap (> 10 percentage points) suggests the agent may have "
        "overfit to the training set. With the default 30 iterations and 5 seeds "
        "this rarely occurs because the dataset is deterministic."
    )

    doc.h2("What to look for in the meta-policy drift figure")
    doc.kv_table([
        ("exploration_scale rises then falls",
         "Healthy: the agent explores when stuck and exploits when improving."),
        ("exploration_scale only rises",
         "The agent is stuck and the plateau nudge is firing repeatedly. "
         "Try more iterations or a different seed."),
        ("weight_step monotonically decreases",
         "The agent is consistently improving and refining -- ideal."),
        ("baseline lines non-flat",
         "This would be a bug. The baseline meta policy should not change."),
    ])

    doc.h2("Numerical benchmarks")
    doc.body("Typical results for the default 5-seed, 30-iteration protocol:")
    doc.table(
        ["Condition",   "Mean train (final)", "Mean test (final)", "Typical range"],
        [
            ["hyperagent", "0.850",  "0.880 - 0.920", "0.82 - 0.95"],
            ["baseline",   "0.840",  "0.860 - 0.900", "0.80 - 0.92"],
            ["no_archive", "0.800",  "0.780 - 0.820", "0.75 - 0.85"],
        ],
        col_widths=[45, 42, 45, 36],
    )
    doc.body(
        "Seed variance is the primary source of result spread. Seeds that start "
        "on difficult borderline repos tend to plateau sooner. Running with more "
        "seeds (--seeds 5 or more) gives tighter confidence intervals."
    )

    doc.callout(
        "Main finding to report",
        "The no_archive condition plateaus significantly below both archive "
        "conditions. This demonstrates the stepping-stones contribution of the "
        "archive, independent of whether the meta policy is adaptive or frozen. "
        "The gap between hyperagent and baseline demonstrates the additional "
        "contribution of metacognitive self-modification.",
    )


def section_modes(doc: Manual):
    doc.add_page()
    doc.h1("7.  The Three Ablation Modes")

    doc.body(
        "The three modes exist to isolate exactly which component of the design "
        "is responsible for performance gains. This is called an ablation study."
    )

    doc.h2("hyperagent -- full system")
    doc.bullet([
        "Task policy evolves: weights, threshold, review style.",
        "Meta policy evolves: focus metric, step sizes, exploration scale.",
        "Parent selection: weighted by fitness x exploration x weight-space novelty.",
        "Archive: all variants kept indefinitely.",
        "Expected result: highest final accuracy.",
    ])

    doc.h2("baseline -- frozen meta policy")
    doc.bullet([
        "Task policy evolves (same as hyperagent).",
        "Meta policy is FROZEN at the seed agent's values for the entire run.",
        "The mutation direction still responds to errors, but the step sizes "
        "and exploration scale never adapt.",
        "Archive: same weighted selection as hyperagent.",
        "Expected result: slightly below hyperagent; isolates meta-policy value.",
    ])

    doc.h2("no_archive -- greedy parent selection")
    doc.bullet([
        "Task policy evolves (same as hyperagent).",
        "Meta policy evolves (same as hyperagent).",
        "Parent selection: ALWAYS the single current best agent.",
        "Archive: still stored, but never used for selection.",
        "Expected result: lowest accuracy; demonstrates archive value.",
    ])

    doc.callout(
        "How to read the comparison",
        "hyperagent > baseline  =>  adaptive meta policy adds value.\n"
        "hyperagent > no_archive  =>  archive stepping stones add value.\n"
        "If these gaps are small, run more iterations or more seeds "
        "to increase statistical power.",
    )

    doc.h2("Plateau detection (applies to hyperagent and no_archive)")
    doc.body(
        "If no fitness improvement occurs for 5 consecutive iterations, "
        "the engine applies a stronger restart nudge:"
    )
    doc.bullet([
        "exploration_scale += 0.10  (vs normal +0.05)",
        "weight_step is reset to mid-range (0.13)",
        "A memory note is written: 'Plateau (N iters). Restart nudge applied.'",
    ])
    doc.body(
        "This is visible in the meta-policy drift figure as a sudden spike "
        "in exploration_scale followed by a recovery as the agent finds "
        "a better region of the search space."
    )

    doc.h2("Weight-space novelty")
    doc.body(
        "Parent selection uses the mean Euclidean distance to the 3 nearest "
        "neighbours in the 5D weight space as a novelty bonus. Agents that "
        "are far from their neighbours in parameter space get a higher "
        "selection probability, keeping the archive diverse."
    )
    doc.code([
        "novelty_score = 1.0 + normalised_knn_distance * 0.30",
        "selection_weight = fitness * exploration_scale * novelty_score",
    ])


def section_prompt(doc: Manual):
    doc.add_page()
    doc.h1("8.  The Self-Improving Prompt Engine")

    doc.body(
        "Beyond numeric weights, HyperAgents also evolves natural-language "
        "code-reviewer prompts. The same archive + mutation pattern applies, "
        "but the evolvable artefact is a text prompt used with an LLM."
    )

    doc.h2("How it works")
    doc.numbered([
        "The active prompt is used to review a codebase with your LLM of choice.",
        "You read the review output and rate it 1-5 (1=poor, 5=excellent).",
        "You note what the review got right (strengths) and what it missed (gaps).",
        "You POST this to /api/promptagent/submit.",
        "The engine archives the current prompt + evaluation.",
        "Mutation produces an improved prompt (LLM-guided or heuristic).",
        "The new prompt becomes active. Repeat from step 1.",
    ])

    doc.h2("Mutation strategy")
    doc.table(
        ["Rating", "Strategy"],
        [
            ["1-2 (poor)",         "Prepend a specificity directive + address the top 2 gaps "
                                   "explicitly at the start of the prompt."],
            ["3 (acceptable)",     "Append gap-derived focus areas as additional instructions."],
            ["4-5 (good/great)",   "Reinforce the primary strength; make minimal changes only."],
        ],
        col_widths=[35, 133],
    )
    doc.body(
        "Fitness is the normalised rating: (rating - 1) / 4.0, "
        "mapping 1->0.0 and 5->1.0."
    )

    doc.h2("Quick start")
    doc.h3("1. Get the current active prompt")
    doc.code([
        "curl http://localhost:8000/api/promptagent/state | python -m json.tool",
    ])
    doc.h3("2. Copy the prompt and use it with your LLM to review a codebase")
    doc.body("(e.g. paste into ChatGPT, Claude, or your local LLM)")

    doc.h3("3. Submit the review result")
    doc.code([
        'curl -X POST http://localhost:8000/api/promptagent/submit \\',
        '     -H "Content-Type: application/json" \\',
        '     -d \'{',
        '       "review_text": "<paste the full review output here>",',
        '       "rating": 3,',
        '       "strengths": ["Good security analysis", "Clear structure"],',
        '       "gaps": ["No line citations", "Missed test coverage"],',
        '       "codebase_ref": "my-repo @ main"',
        '     }\'',
    ])

    doc.h3("4. Use the new prompt")
    doc.body("The response contains new_prompt. Use it for the next review cycle.")

    doc.h3("5. Export the best prompt found so far")
    doc.code([
        'curl http://localhost:8000/api/promptagent/export \\',
        '     | python -c "import json,sys; print(json.load(sys.stdin)[\'prompt\'])"',
        '     > code-reviewer.md',
    ])

    doc.h2("Interpreting progress")
    doc.kv_table([
        ("fitness rising",
         "The prompt is improving. Continue until fitness >= 0.75 (rating 4)."),
        ("mutation_source = llm",
         "OpenAI guided the mutation. Check the rationale field for the key change."),
        ("mutation_source = heuristic",
         "Offline mutation applied. Gaps were appended / prepended directly."),
        ("archive_size",
         "Total prompts evaluated. A good stopping point is 5-10 cycles."),
    ])

    doc.callout(
        "Tip: seed from your own prompt",
        "If you already have a code-reviewer prompt, pass it as seed_prompt "
        "to /api/promptagent/reset and the engine will evolve from your baseline "
        "rather than the built-in default.",
    )


def section_api(doc: Manual):
    doc.add_page()
    doc.h1("9.  API Quick Reference")

    doc.body(
        "Base URL: http://127.0.0.1:8000  --  Interactive docs: /docs"
    )

    doc.h2("Engine")
    doc.table(
        ["Method", "Path", "Description"],
        [
            ["GET",    "/api/state",          "Full engine snapshot"],
            ["POST",   "/api/reset",           "Reset: body {\"mode\": \"hyperagent\"}"],
            ["POST",   "/api/run",             "Run N iters: body {\"iterations\": 30}"],
            ["GET",    "/api/metrics/json",    "Per-iteration metrics as JSON"],
            ["GET",    "/api/metrics/csv",     "Per-iteration metrics as CSV"],
        ],
        col_widths=[18, 58, 92],
    )

    doc.h2("Run management")
    doc.table(
        ["Method", "Path", "Description"],
        [
            ["GET",    "/api/runs",              "List all saved runs"],
            ["GET",    "/api/runs/{id}",          "Get one run snapshot"],
            ["POST",   "/api/runs/{id}/load",     "Restore a run into engine"],
            ["DELETE", "/api/runs/{id}",          "Delete a run"],
        ],
        col_widths=[18, 58, 92],
    )

    doc.h2("Prompt agent")
    doc.table(
        ["Method", "Path", "Description"],
        [
            ["GET",    "/api/promptagent/state",   "Active prompt + archive"],
            ["POST",   "/api/promptagent/reset",   "Reset: body {\"seed_prompt\": \"...\"}"],
            ["POST",   "/api/promptagent/submit",  "Submit review result"],
            ["GET",    "/api/promptagent/export",  "Best prompt as JSON"],
        ],
        col_widths=[18, 65, 85],
    )

    doc.h2("Accounts")
    doc.table(
        ["Method", "Path", "Description"],
        [
            ["POST",   "/api/accounts",               "Add account (synthetic or GitHub)"],
            ["GET",    "/api/accounts",               "List all accounts"],
            ["GET",    "/api/accounts/{id}/repos",    "Repos for one account"],
            ["DELETE", "/api/accounts/{id}",          "Delete account + repos"],
            ["POST",   "/api/accounts/apply-all",     "Push account repos into engine dataset"],
        ],
        col_widths=[18, 65, 85],
    )

    doc.body("For full field-level documentation see docs/api.md or /docs in the browser.")


def section_glossary(doc: Manual):
    doc.add_page()
    doc.h1("10.  Glossary")

    doc.kv_table([
        ("Ablation",
         "Removing or freezing one component to measure its contribution."),
        ("Agent",
         "A program that makes classification decisions."),
        ("Archive",
         "The full history of every agent variant ever produced, "
         "used as a pool of stepping stones."),
        ("Baseline",
         "The experiment condition where the meta policy is frozen, "
         "used as a comparison point."),
        ("Exploration scale",
         "A meta-policy parameter controlling how much random noise is "
         "added to mutations. High = explore; Low = exploit."),
        ("False negative",
         "A repo labelled ACCEPT that the agent incorrectly rejected."),
        ("False positive",
         "A repo labelled REJECT that the agent incorrectly accepted."),
        ("Fitness",
         "Train accuracy. Higher is always better. Monotonically "
         "non-decreasing in the best_fitness column."),
        ("Hyperagent",
         "An agent whose meta policy (self-improvement strategy) is "
         "itself evolvable."),
        ("Iteration",
         "One round of: select parent, mutate, evaluate, archive."),
        ("Meta policy",
         "The policy that controls how the task policy mutates. "
         "Contains focus_metric, weight_step, threshold_step, "
         "exploration_scale, and memory notes."),
        ("Mutation",
         "A small change applied to an agent's task policy (and optionally "
         "meta policy) to produce a child agent."),
        ("No archive",
         "The experiment condition where parent selection is greedy "
         "(always the current best), removing the stepping-stones mechanism."),
        ("Novelty",
         "The mean Euclidean distance to nearest neighbours in weight space. "
         "Used as a diversity bonus in parent selection."),
        ("Plateau",
         "A period of 5+ iterations with no fitness improvement. "
         "Triggers the restart nudge."),
        ("Plateau nudge",
         "A stronger exploration boost applied when the agent is stuck: "
         "exploration_scale += 0.10 and weight_step is reset to 0.13."),
        ("Prompt agent",
         "The variant of the system that evolves a text prompt "
         "rather than numeric weights."),
        ("Seed",
         "A fixed starting number that makes the random choices reproducible."),
        ("Task policy",
         "The policy that directly controls ACCEPT vs REJECT decisions. "
         "Contains weights, threshold, and review_style."),
        ("Test accuracy",
         "Accuracy on repos the agent was never trained on. "
         "The primary measure of generalisation."),
        ("Threshold",
         "The minimum score a repository must achieve to be accepted."),
        ("Train accuracy",
         "Accuracy on the 20 repos the agent learned from."),
        ("Weights",
         "Five numbers (one per feature) that say how much each quality "
         "dimension contributes to the total score."),
    ], col1=52)


def back_cover(doc: Manual):
    doc.add_page()
    doc.set_fill_color(*CREAM)
    doc.rect(0, 0, 210, 297, "F")
    doc.set_fill_color(*BROWN)
    doc.rect(0, 0, 210, 6, "F")
    doc.set_fill_color(*TEAL)
    doc.rect(0, 291, 210, 6, "F")

    doc.ln(55)
    doc.set_x(doc.l_margin)
    doc.set_font("Arial", "B", 22)
    doc.set_text_color(*BROWN)
    doc.multi_cell(doc.epw, 10, "Quick Reference", align="C", new_x="LMARGIN", new_y="NEXT")

    doc.ln(6)
    doc.set_x(doc.l_margin)
    doc.set_font("Arial", "B", 10.5)
    doc.set_text_color(*TEAL)
    doc.multi_cell(doc.epw, 6, "Run the full ablation experiment:", align="C", new_x="LMARGIN", new_y="NEXT")
    doc.set_x(doc.l_margin)
    doc.set_font("Mono", "", 9.5)
    doc.set_text_color(*DARK)
    doc.multi_cell(doc.epw, 5.5,
        "python scripts/run_experiment.py --iterations 30 --seeds 5",
        align="C", new_x="LMARGIN", new_y="NEXT")

    doc.ln(5)
    doc.set_x(doc.l_margin)
    doc.set_font("Arial", "B", 10.5)
    doc.set_text_color(*TEAL)
    doc.multi_cell(doc.epw, 6, "Generate figures:", align="C", new_x="LMARGIN", new_y="NEXT")
    doc.set_x(doc.l_margin)
    doc.set_font("Mono", "", 9.5)
    doc.set_text_color(*DARK)
    doc.multi_cell(doc.epw, 5.5, "python scripts/plot_results.py", align="C", new_x="LMARGIN", new_y="NEXT")

    doc.ln(5)
    doc.set_x(doc.l_margin)
    doc.set_font("Arial", "B", 10.5)
    doc.set_text_color(*TEAL)
    doc.multi_cell(doc.epw, 6, "Start the API server:", align="C", new_x="LMARGIN", new_y="NEXT")
    doc.set_x(doc.l_margin)
    doc.set_font("Mono", "", 9.5)
    doc.set_text_color(*DARK)
    doc.multi_cell(doc.epw, 5.5,
        "cd backend  &&  uvicorn app.main:app --port 8000 --reload",
        align="C", new_x="LMARGIN", new_y="NEXT")

    doc.ln(10)
    doc.set_draw_color(*LINE)
    doc.set_line_width(0.4)
    doc.line(45, doc.get_y(), 165, doc.get_y())

    doc.ln(8)
    doc.set_x(doc.l_margin)
    doc.set_font("Arial", "I", 9.5)
    doc.set_text_color(*MUTED)
    doc.multi_cell(doc.epw, 5.5,
        "Based on arXiv:2603.19461v1  |  github.com/AISmithy/hyperagents",
        align="C", new_x="LMARGIN", new_y="NEXT")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    doc = Manual()
    cover(doc)
    toc(doc)
    section_what(doc)
    section_install(doc)
    section_first_run(doc)
    section_output(doc)
    section_plotting(doc)
    section_interpret(doc)
    section_modes(doc)
    section_prompt(doc)
    section_api(doc)
    section_glossary(doc)
    back_cover(doc)
    doc.output(str(OUT))
    print(f"Saved -> {OUT}  ({doc.page} pages)")


if __name__ == "__main__":
    main()
