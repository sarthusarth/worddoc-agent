import os
import subprocess
from exa_py import Exa
from dotenv import load_dotenv
from langfuse.decorators import observe, langfuse_context


load_dotenv()

exa = Exa(api_key=os.getenv("EXA_API_KEY"))

TOOL_DEFINITIONS = {
    "web_search": {
        "name": "web_search",
        "description": "Search the web for recent information on a query.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search query"}},
            "required": ["query"],
        },
    },
    "write_file": {
        "name": "write_file",
        "description": "Write a file and return the output.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Filename to write"},
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["filename", "content"],
        },
    },
    "read_file": {
        "name": "read_file",
        "description": "Read a file and return the content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Filename to read"}
            },
            "required": ["filename"],
        },
    },
}


def write_file(filename: str, content: str) -> str:
    """
    Write a file and return the output.
    """
    with open(filename, "w") as f:
        f.write(content)
    return f"File {filename} written successfully."


def read_file(filename: str) -> str:
    """
    Read a file and return the content.
    """
    with open(filename, "r") as f:
        return f.read()


@observe(name="exa_web_search", as_type="generation")
def web_search(query: str) -> str:
    """Search the web for recent information on a query."""
    results = exa.search(query=query, num_results=1, type="auto")
    result = results.results[0]
    cost = results.cost_dollars.total if results.cost_dollars else 0.001
    langfuse_context.update_current_observation(
        model="exa-search",
        input=query,
        output=result.url,
        metadata={"title": result.title, "url": result.url},
        usage={
            "unit": "TOKENS",
            "input": 0,
            "output": 0,
            "total_cost": cost,
        },
    )
    return f"URL: {result.url}\nTitle: {result.title}\nText: {result.text}"


def handle_tool_call(tool_name: str, tool_input: dict) -> str:
    """Dispatch a tool call and return a string result."""
    if tool_name == "web_search":
        return web_search(tool_input["query"])
    if tool_name == "write_file":
        return write_file(tool_input["filename"], tool_input["content"])
    if tool_name == "read_file":
        return read_file(tool_input["filename"])
    raise NotImplementedError(f"Tool not implemented: {tool_name}")
