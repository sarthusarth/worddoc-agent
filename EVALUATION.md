# Evaluation Guide

How to evaluate the doc-agent pipeline — stucturally and qualitatively.

---

## 1. Unit: each component in isolation

### Planner
- Primary Metric: Check the JSON output is valid and has all required fields (`topic`, `folder`, `tasks`)
- Secondary: Assert task types are drawn from the allowed set (`define`, `search`, `compare`, `examples`, `critique`, `synthesise`)
- Secondary: Assert ordering follows `define → search/compare/examples → critique → synthesise`

```python
plan_data = plan("Python programming language")
assert {"topic", "folder", "tasks"} == set(plan_data.keys())
assert plan_data["tasks"][0]["type"] == "define"
assert any(t["type"] == "synthesise" for t in plan_data["tasks"])
```

### Researcher (per task)
- Run a single `research_task()` call on a known task
- Assert the `task-N.md` file was written and is non-empty
- Assert the file contains at least one `> Source:` line (inline citation present)
- Assert the file starts with a `# Task N:` heading

```python
research_task({"id": 1, "type": "define", "description": "Define Python."}, "test-folder")
content = open("test-folder/task-1.md").read()
assert content.strip()
assert "> Source:" in content
```

### Writer
- Pre-seed a folder with hand-written `task-N.md` files (known content)
- Assert the output JSON has all required fields (`title`, `subtitle`, `sections`, `conclusion`)
- Assert every paragraph/bullets block has a `source` field
- Assert `report.docx` and `report.json` are both created and non-empty
- Assert `report.docx` opens without errors

```python
structure = generate_structure("Test topic", mock_notes)
assert {"title", "sections", "conclusion"} <= set(structure.keys())
for section in structure["sections"]:
    for block in section["content"]:
        assert "source" in block
```

---

## 2. LLM output quality 

The errors can be mainly categories in 2 types:
- Relevance Errors : Evaluating whether the generated documents/plan is relevant to the user task
- Trustfullness Errors: Evaluating trust worthiness of the infomation and hallucination rate

### Evaluating The Planner Agent
For the planner agent, only important metric is the relevance given the topic, we can use a LLM judge to score the plan on a scale 1-5. The prompt must be benchmarked and correlated with human score on small set of sample. -> (1/5)


### Evaluating The Researcher Agent
Here we have to evalute 2 things:
- Trustfullness: Any information generated is not provided in the web content -> (0/1) 
- Relevance:  Does the response answer the research question? Are section headings descriptive and non-generic? -> (1/5)

### Evaluating The Writer Agent
Again similar to the researcher agent
- Trustfullness: Any information generated is not provided in the tasks files -> (0/1) 
- Relevance:  Does the content answer the research question? Are section headings descriptive and non-generic? -> (1/5)

---

## 3. Other Observability checks (Langfuse)

Langfuse traces can be also used a as a passive evaluation layer:

| Signal | What we can infer/evaluate |
|---|---|
| Token count per task | Spikes indicate context bloat (too many prior notes injected) |
| Exa search cost per task | High cost = too many searches, check `num_results` and search count |
| Total pipeline cost | Budget guardrail — alert if above threshold per run |
| Missing spans | A task with no `exa_web_search` child span = the agent skipped searching |
| High output tokens on writer | Model may be padding — check if document is repetitive |

---
