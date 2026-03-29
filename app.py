import os
import streamlit as st
from langfuse.decorators import observe
from planner import plan
from researcher import research_task, load_plan
from writer import load_research_notes, generate_structure, render_docx

st.set_page_config(page_title="Research Agent", page_icon="🔬", layout="centered")
st.title("Research Document Agent")
st.caption("Enter a topic to research and generate a Word document.")

topic = st.text_input(
    "Research topic", placeholder="e.g. Is Nvidia stock a good investment?"
)
start = st.button("Start Research", disabled=not topic.strip())


@observe(name="research-pipeline")
def run_pipeline(topic: str) -> str:
    """Full pipeline wrapped in a single Langfuse trace."""
    # ── Step 1: Plan ──────────────────────────────────────────────────────────
    with st.status("Planning research tasks...", expanded=True) as status:
        plan_data = plan(topic)
        tasks = plan_data["tasks"]
        project_folder = plan_data["folder"]
        for task in tasks:
            st.write(f"**{task['id']}.** [{task['type']}] {task['description']}")
        status.update(label=f"Plan ready — {len(tasks)} tasks", state="complete")

    # ── Step 2: Research each task ────────────────────────────────────────────
    for task in tasks:
        with st.status(
            f"Task {task['id']}: {task['description']}", expanded=True
        ) as status:
            logs = st.empty()
            lines = []

            def log(msg, _logs=logs, _lines=lines):
                _lines.append(msg)
                _logs.markdown("\n\n".join(_lines))

            research_task(task, project_folder, log=log)
            status.update(
                label=f"✓ Task {task['id']}: {task['description']}", state="complete"
            )

    # ── Step 3: Write document ────────────────────────────────────────────────
    with st.status("Writing document...", expanded=False) as status:
        notes = load_research_notes(project_folder)
        structure = generate_structure(topic, notes)
        output_path = os.path.join(project_folder, "report.docx")
        render_docx(structure, output_path)
        status.update(label="Document ready", state="complete")

    return output_path


if start and topic.strip():
    output_path = run_pipeline(topic.strip())

    st.success("All done!")
    with open(output_path, "rb") as f:
        st.download_button(
            label="Download report.docx",
            data=f,
            file_name=f"{output_path.split('/')[0]}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
