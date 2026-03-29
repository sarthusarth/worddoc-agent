# Doc Agent

An AI-powered research document generator. Give it a topic, it plans research tasks, searches the web, and produces a formatted Word document — with per-paragraph source citations, a Streamlit UI with step-by-step progress, and full observability via Langfuse.

## Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                        Streamlit UI  (app.py)                   │
│                                                                 │
│  [Topic input] ──▶ "Generate Plan" ──▶ Plan shown to user       │
│                                              │                  │
│                                    [Execute Plan] [Start Over]  │
│                                              │                  │
│                               Research runs task by task        │
│                                              │                  │
│                                    [Download report.docx]       │
└──────────────────────────┬──────────────────────────────────────┘
                           │ topic
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  1. PLANNER  (planner.py)                                        │
│                                                                  │
│   Claude Sonnet  ──▶  plan.json                                  │
│                       ├── topic                                  │
│                       ├── folder  (kebab-case slug)              │
│                       └── tasks[] {id, type, description}        │
│                                                                  │
│   types: define │ search │ compare │ examples │ critique │       │
│          synthesise                                              │
│                                                                  │
│   Side-effects: notes.txt  ←  project_folder + topic             │
└──────────────────────────┬───────────────────────────────────────┘
                           │ tasks[]  (user confirms before this)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. RESEARCHER  (researcher.py)          for each task          │
│                                                                 │
│   ┌─────────────────────────────────────────────────────┐       │
│   │  Task N  (agentic loop)                             │       │
│   │                                                     │       │
│   │  prior notes injected ──▶ Claude Haiku              │       │
│   │                               │                     │       │
│   │                    ┌──────────┴──────────┐          │       │
│   │                    ▼                     ▼          │       │
│   │             web_search (Exa)       write_file       │       │
│   │                    │                     │          │       │
│   │             result text         task-N.md           │       │
│   │             + source URL        (paragraph +        │       │
│   │                    │             > Source: URL)     │       │
│   │                    └──────▶ Claude Haiku            │       │
│   │                            (next turn)              │       │
│   │                                 │                   │       │
│   │                           end_turn                  │       │
│   └─────────────────────────────────────────────────────┘       │
│                                                                 │
│   Note: synthesise tasks receive all prior task-N.md as context │
└──────────────────────────┬──────────────────────────────────────┘
                           │ task-1.md … task-N.md
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  3. WRITER  (writer.py)                                          │
│                                                                  │
│   all task-N.md  ──▶  Claude Haiku  ──▶  JSON structure          │
│                                          ├── title               │
│                                          ├── subtitle            │
│                                          ├── sections[]          │
│                                          │   ├── paragraph       │
│                                          │   │    └── source URL │
│                                          │   └── bullets         │
│                                          │        └── source URL │
│                                          └── conclusion          │
│                                                 │                │
│                                    ┌────────────┴────────────┐   │
│                                    ▼                         ▼   │
│                               report.docx             report.json│
│                          (source per paragraph)  (editable later)│
└──────────────────────────────────────────────────────────────────┘
```

## Observability (Langfuse)

Every pipeline run is traced end-to-end with token counts and costs at each level.

```
Trace: research-pipeline
├── Span: planner
│   └── model, input tokens, output tokens, cost
├── Span: research-task  ×N  (one per task)
│   ├── Span: exa_web_search  (one per search)
│   │   └── query, URL found, Exa API cost
│   └── model, tokens + cost accumulated per agentic turn
└── Span: writer
    └── model, input tokens, output tokens, cost
```

**Cost tracking:**
- LLM costs are calculated explicitly from token counts using pricing in `utils.py` (`_MODEL_PRICING`) — not looked up from Langfuse's model registry, so new Claude models work out of the box
- Exa search cost is read from `result.cost_dollars.total` if available, otherwise falls back to `$0.001` per call
- All costs roll up to the trace total automatically

## Project structure

```
doc-agent/
├── app.py          # Streamlit UI — plan confirmation + pipeline orchestration
├── planner.py      # Generates a structured research plan
├── researcher.py   # Agentic loop — searches and writes per-task notes
├── writer.py       # Turns notes into a formatted .docx + saves report.json
├── tools.py        # web_search (Exa), write_file, read_file
├── prompts.py      # System prompts for planner and writer
├── utils.py        # load_yaml, token_usage (pricing helper)
├── config.yml      # Model name used across all agents
└── <topic-slug>/   # Created per run
    ├── plan.json        # Research plan
    ├── notes.txt        # Active project pointer (folder + topic)
    ├── task-1.md        # Per-task research notes with inline sources
    ├── task-N.md
    ├── report.docx      # Final formatted document
    └── report.json      # Document structure — load this for future edits
```

## Setup

**1. Install dependencies**
```bash
uv sync
```

**2. Create a `.env` file:**
```
ANTHROPIC_API_KEY=sk-ant-...
EXA_API_KEY=exa-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

**3. Edit `config.yml` to set the model:**
```yaml
MODEL: claude-haiku-4-5-20251001
```

> Note: the planner always uses `claude-sonnet-4-6` regardless of `config.yml` — it needs stronger reasoning for plan quality. All other agents use the configured model.

## Running

**Streamlit UI (recommended)**
```bash
uv run streamlit run app.py
```

**CLI — run each stage individually**
```bash
uv run python planner.py      # creates notes.txt + <folder>/plan.json
uv run python researcher.py   # creates <folder>/task-N.md files
uv run python writer.py       # creates <folder>/report.docx + report.json
```

## How context flows between tasks

The researcher injects prior notes into each task based on type:

| Task type | Prior context injected |
|---|---|
| `define` | none (starting point) |
| `search`, `compare`, `examples`, `critique` | task-1 (`define`) only |
| `synthesise` | all prior `task-N.md` files |

This ensures the synthesis task reasons over actual research findings rather than re-searching from scratch.

## Source citations

Each paragraph in the research notes ends with a `> Source: <URL>` line. The writer carries these through to the final `.docx` as small 8pt italic text directly below each paragraph — gray for valid URLs, black for unclear references.

## Editing a document later (Future Task)

Load `report.json`, modify any block, then call `render_docx` directly:

```python
import json
from writer import render_docx

with open("my-topic/report.json") as f:
    structure = json.load(f)

# Edit structure here...
render_docx(structure, "my-topic/report_v2.docx")
```
