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

## How the agent loop works

The researcher is the only true agent in the pipeline — the planner and writer are single LLM calls. For each research task, the researcher runs a `while True` loop:

1. The model receives the task description and any injected prior context, along with the available tools.
2. If the model returns `stop_reason="tool_use"`, Python executes every tool call in the response, collects the results, and appends them as a `tool_result` message before calling the model again.
3. This continues until the model returns `stop_reason="end_turn"`, meaning it has gathered enough information and written the output file.
4. If `stop_reason="max_tokens"` is returned, the loop breaks immediately to prevent a malformed message history (an unmatched `tool_use` block with no `tool_result`).

The loop is intentionally narrow: the researcher is only allowed to search and write. It cannot read files, run commands, or call other agents. This keeps the loop predictable and easy to trace.

## What tools are integrated

Three tools are available in `tools.py`. The researcher only receives two of them — `web_search` and `write_file`. `read_file` exists for future use by other agents.

**`web_search`** — powered by the Exa API. Takes a query string, returns the top result's URL, title, and full text. Each call is traced in Langfuse as a generation with the actual Exa cost attached. The researcher uses 1–2 searches per task.

**`write_file`** — writes arbitrary text to a given file path. The researcher uses this once per task to save its findings as a Markdown file (`task-N.md`) inside the project folder. Keeping file I/O as a tool (rather than hardcoded Python) means the LLM decides the content and the path — the human-readable output is the model's own words, not a template.

**`read_file`** — reads a file and returns its contents. Not given to the researcher (it has no need to read files during research) but available for a future editor agent that loads `report.json` and makes targeted changes.

## How context flows between tasks

The researcher injects prior notes into each task based on type:

| Task type | Prior context injected |
|---|---|
| `define` | none (starting point) |
| `search`, `compare`, `examples`, `critique` | task-1 (`define`) only |
| `synthesise` | all prior `task-N.md` files |

This ensures the synthesis task reasons over actual research findings rather than re-searching from scratch.

## Context strategy

Context is managed deliberately at each stage to balance quality against token cost.

**Planner** receives only the topic. It has no access to search results or prior runs — its job is pure structured reasoning about what needs to be researched, not the research itself.

**Researcher** receives selective prior context depending on the task type. Non-synthesis tasks only receive the `define` task output (task-1) as baseline grounding. This keeps the prompt small and focused — a search task about financials doesn't need to know what the compare task found. The synthesise task is the exception: it receives all prior `task-N.md` files because its whole purpose is to draw connections across the full research body. It also gets a higher `max_tokens` limit (4096 vs 2048) to accommodate the larger input.

**Writer** receives all task notes concatenated in order. By this point the research is complete and the writer needs the full picture to produce a coherent document. To prevent the output from being truncated, the prompt caps paragraphs at 60 words and sections at 1–2 blocks. If the JSON is still truncated at `max_tokens`, `json-repair` recovers a partial but valid structure rather than crashing.

**Tool results** are passed back inline as `tool_result` messages in the conversation history. The model sees the full search result text on the next turn, not a summary — this preserves detail that would otherwise be lost in a paraphrase.

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
