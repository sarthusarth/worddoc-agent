# Doc Agent

An AI-powered research document generator. Give it a topic, it plans research tasks, searches the web, and produces a formatted Word document — all observable via a Streamlit UI and traced in Langfuse.

## Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                        Streamlit UI                             │
│                     (app.py — run_pipeline)                     │
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
│   Outputs: notes.txt  ←  project_folder + topic                 │
└──────────────────────────┬───────────────────────────────────────┘
                           │ tasks[]
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  2. RESEARCHER  (researcher.py)          for each task           │
│                                                                  │
│   ┌─────────────────────────────────────────────────────┐       │
│   │  Task N  (agentic loop)                             │       │
│   │                                                     │       │
│   │  prior notes injected ──▶ Claude Haiku              │       │
│   │                               │                     │       │
│   │                    ┌──────────┴──────────┐          │       │
│   │                    ▼                     ▼          │       │
│   │             web_search (Exa)       write_file       │       │
│   │                    │                     │          │       │
│   │             result text            task-N.md        │       │
│   │                    │                                │       │
│   │                    └──────▶ Claude Haiku            │       │
│   │                            (next turn)              │       │
│   │                                 │                   │       │
│   │                           end_turn ──▶ task-N.md    │       │
│   └─────────────────────────────────────────────────────┘       │
│                                                                  │
│   Note: synthesise tasks receive all prior task-N.md as context │
└──────────────────────────┬───────────────────────────────────────┘
                           │ task-1.md … task-N.md
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  3. WRITER  (writer.py)                                          │
│                                                                  │
│   all task-N.md  ──▶  Claude Haiku  ──▶  JSON structure         │
│                                          ├── title               │
│                                          ├── subtitle            │
│                                          ├── sections[]          │
│                                          │   ├── paragraph       │
│                                          │   └── bullets         │
│                                          └── conclusion          │
│                                                 │                │
│                                          python-docx             │
│                                                 │                │
│                                          report.docx             │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  OBSERVABILITY  (Langfuse)                                       │
│                                                                  │
│  Trace: research-pipeline                                        │
│  ├── Generation: planner          tokens + cost                  │
│  ├── Span: research-task  ×N                                     │
│  │   ├── Span: exa_web_search     $cost per call                 │
│  │   └── token usage per turn                                    │
│  └── Generation: writer           tokens + cost                  │
└──────────────────────────────────────────────────────────────────┘
```

## Project structure

```
doc-agent/
├── app.py          # Streamlit UI — orchestrates the full pipeline
├── planner.py      # Generates a structured research plan
├── researcher.py   # Agentic loop — searches and writes per-task notes
├── writer.py       # Turns notes into a formatted .docx
├── tools.py        # web_search (Exa), write_file, read_file
├── prompts.py      # System prompts for planner and writer
├── utils.py        # Shared helpers (load_yaml, etc.)
├── config.yml      # Model configuration
└── <topic-slug>/   # Created per run
    ├── plan.json
    ├── task-1.md … task-N.md
    └── report.docx
```

## Setup

**1. Install dependencies**
```bash
uv sync
```

**2. Configure environment — create a `.env` file:**
```
ANTHROPIC_API_KEY=sk-ant-...
EXA_API_KEY=exa-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

**3. Configure model — edit `config.yml`:**
```yaml
MODEL: claude-haiku-4-5-20251001
```

## Running

**Streamlit UI (recommended)**
```bash
uv run streamlit run app.py
```

**CLI — run each stage individually**
```bash
uv run python planner.py      # creates notes.txt + plan.json
uv run python researcher.py   # creates task-N.md files
uv run python writer.py       # creates report.docx
```

## How context flows between tasks

The researcher injects prior notes into each task based on type:

| Task type | Prior context injected |
|---|---|
| `define` | none (starting point) |
| `search`, `compare`, `examples`, `critique` | task-1 (define) only |
| `synthesise` | all prior task-N.md files |

This ensures the synthesis task reasons over actual research findings rather than starting fresh.
