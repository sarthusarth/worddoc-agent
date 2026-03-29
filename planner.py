import os
import json
import anthropic
from utils import load_yaml, token_usage
from dotenv import load_dotenv
from prompts import PLANNER_SYSTEM
from langfuse.decorators import observe, langfuse_context

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
config = load_yaml("config.yml")


@observe(name="planner")
def plan(
    topic: str, output_file: str = "plan.json", notes_file="notes.txt"
) -> list[dict]:
    """Return an ordered list of research tasks for the given topic and save to a JSON file."""
    response = client.messages.create(
        model=config["model"],
        max_tokens=1024,
        system=PLANNER_SYSTEM,
        messages=[{"role": "user", "content": f"Topic: {topic}"}],
    )
    langfuse_context.update_current_observation(
        model=config["model"],
        usage=token_usage(
            config["model"], response.usage.input_tokens, response.usage.output_tokens
        ),
        input=topic,
        output=response.content[0].text.strip(),
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]
    plan_data = json.loads(text.strip())
    os.makedirs(plan_data["folder"], exist_ok=True)
    output_file = os.path.join(plan_data["folder"], output_file)
    with open(output_file, "w") as f:
        json.dump(plan_data, f, indent=2)
    with open(notes_file, "w") as f:
        f.write(f"project_folder: {plan_data['folder']}\ntopic: {plan_data['topic']}\n")
    return plan_data


if __name__ == "__main__":
    tasks = plan("Is nividia stock a good investment?")
    print(tasks)
