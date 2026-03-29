import yaml

# Cost per million tokens (USD) — update if pricing changes
_MODEL_PRICING = {
    "claude-sonnet-4-6":          {"input": 3.00,  "output": 15.00},
    "claude-opus-4-6":            {"input": 15.00, "output": 75.00},
    "claude-haiku-4-5-20251001":  {"input": 0.80,  "output": 4.00},
}


def load_yaml(filename):
    """Load a YAML file and return its contents as a Python object."""
    with open(filename, "r") as f:
        return yaml.safe_load(f)


def token_usage(model: str, input_tokens: int, output_tokens: int) -> dict:
    """Return a Langfuse-compatible usage dict with token counts and costs."""
    pricing = _MODEL_PRICING.get(model, {"input": 0.0, "output": 0.0})
    input_cost  = (input_tokens  / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return {
        "input":        input_tokens,
        "output":       output_tokens,
        "unit":         "TOKENS",
        "input_cost":   input_cost,
        "output_cost":  output_cost,
        "total_cost":   input_cost + output_cost,
    }
