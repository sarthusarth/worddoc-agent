import json
import os
import anthropic
from utils import load_yaml, token_usage
from dotenv import load_dotenv
from tools import TOOL_DEFINITIONS, handle_tool_call
from langfuse.decorators import observe, langfuse_context

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
config = load_yaml("config.yml")

RESEARCHER_TOOLS = [TOOL_DEFINITIONS["web_search"], TOOL_DEFINITIONS["write_file"]]

RESEARCHER_SYSTEM = """You are a focused research agent working on one task at a time.

You will be given a single research task and a project folder path.
Your job:
1. Use web_search to find accurate, relevant information for the task.
2. Synthesise the findings into clear, factual prose (2–4 paragraphs).
3. Save your findings using write_file to: {project_folder}/task-{task_id}.md

## Notes on file writing
- Always write to the exact path: {project_folder}/task-{task_id}.md
- Start the file with a heading: # Task {task_id}: <short title>
- After EACH paragraph, add a source line in this exact format:
  > Source: <URL>
- Do NOT put a combined sources section at the end — every paragraph must have its own source line immediately after it
- If one search result is used across multiple paragraphs, repeat the source line after each paragraph

## Notes on searching
- Run 1–2 searches per task — enough to be thorough, not exhaustive
- Prefer recent, authoritative sources
- If a search returns irrelevant results, refine the query and try again"""


def load_context(notes_file: str = "notes.txt") -> tuple[str, str]:
    """Read project_folder and topic from notes.txt."""
    context = {}
    with open(notes_file) as f:
        for line in f:
            if ":" in line:
                key, _, value = line.partition(":")
                context[key.strip()] = value.strip()
    return context["project_folder"], context["topic"]


def load_plan(project_folder: str) -> list[dict]:
    """Load tasks from plan.json in the project folder."""
    plan_path = os.path.join(project_folder, "plan.json")
    with open(plan_path) as f:
        return json.load(f)["tasks"]


def load_prior_notes(task: dict, project_folder: str) -> str:
    """Return completed task notes that this task depends on."""
    current_id = task["id"]
    task_type = task["type"]

    # synthesise needs all prior notes; others only need task-1 (define) for baseline
    if task_type == "synthesise":
        ids_to_load = range(1, current_id)
    else:
        ids_to_load = [1] if current_id > 1 else []

    sections = []
    for i in ids_to_load:
        path = os.path.join(project_folder, f"task-{i}.md")
        if os.path.exists(path):
            with open(path) as f:
                sections.append(f.read())

    if not sections:
        return ""
    return "\n\n---\n\n".join(sections)


@observe(name="research-task")
def research_task(task: dict, project_folder: str, log=print) -> None:
    """Run the agentic loop for a single research task."""
    system = RESEARCHER_SYSTEM.replace("{project_folder}", project_folder).replace(
        "{task_id}", str(task["id"])
    )

    prior_notes = load_prior_notes(task, project_folder)
    context_block = (
        f"\n\n## Prior research notes\n\n{prior_notes}" if prior_notes else ""
    )

    user_message = (
        f"Task type: {task['type']}\n"
        f"Task: {task['description']}\n"
        f"Save your findings to: {project_folder}/task-{task['id']}.md"
        f"{context_block}"
    )

    messages = [{"role": "user", "content": user_message}]

    # Synthesis tasks inject all prior notes — give them more room
    max_tokens = 4096 if task.get("type") == "synthesise" else 2048

    while True:
        response = client.messages.create(
            model=config["model"],
            max_tokens=max_tokens,
            system=system,
            tools=RESEARCHER_TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})
        langfuse_context.update_current_observation(
            model=config["model"],
            usage=token_usage(
                config["model"],
                response.usage.input_tokens,
                response.usage.output_tokens,
            ),
        )

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "max_tokens":
            # Response was cut off — appending tool_results would corrupt message history
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    preview = list(block.input.values())[0][:80] if block.input else ""
                    log(f"**{block.name}**: {preview}")
                    langfuse_context.update_current_observation(
                        metadata={f"tool:{block.name}": block.input}
                    )
                    result = handle_tool_call(block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )
            messages.append({"role": "user", "content": tool_results})


def research(notes_file: str = "notes.txt", log=print) -> None:
    """Main entry point: load context, loop through all tasks."""
    project_folder, topic = load_context(notes_file)
    tasks = load_plan(project_folder)

    log(f"Starting research: '{topic}' — {len(tasks)} tasks")
    for task in tasks:
        log(f"\n[Task {task['id']}] {task['description']}")
        research_task(task, project_folder, log=log)
        log(f"[Task {task['id']}] Done.")

    log(f"\nResearch complete. Files saved to ./{project_folder}/")


if __name__ == "__main__":
    research()
