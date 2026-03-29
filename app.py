import os
import streamlit as st
from langfuse.decorators import observe
from planner import plan
from researcher import research_task
from writer import load_research_notes, generate_structure, render_docx


@observe(name="research-pipeline")
def _run_research_and_write(plan_data: dict, topic: str) -> str:
    tasks = plan_data["tasks"]
    project_folder = plan_data["folder"]

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

    with st.status("Writing document...", expanded=False) as status:
        notes = load_research_notes(project_folder)
        structure = generate_structure(topic, notes)
        output_path = os.path.join(project_folder, "report.docx")
        render_docx(structure, output_path)
        status.update(label="Document ready", state="complete")

    return output_path


st.set_page_config(page_title="Research Agent", page_icon="🔬", layout="centered")
st.title("Research Document Agent")
st.caption("Enter a topic to research and generate a Word document.")

# ── Session state defaults ─────────────────────────────────────────────────────
if "plan_data" not in st.session_state:
    st.session_state.plan_data = None
if "output_path" not in st.session_state:
    st.session_state.output_path = None

# ── Step 1: Topic input + Plan ─────────────────────────────────────────────────
topic = st.text_input(
    "Research topic",
    placeholder="e.g. Is Nvidia stock a good investment?",
    disabled=st.session_state.plan_data is not None,
)
plan_btn = st.button(
    "Generate Plan",
    disabled=not topic.strip() or st.session_state.plan_data is not None,
)

if plan_btn and topic.strip():
    with st.spinner("Planning research tasks..."):
        st.session_state.plan_data = plan(topic.strip())
    st.rerun()

# ── Step 2: Show plan + confirm ────────────────────────────────────────────────
if st.session_state.plan_data and st.session_state.output_path is None:
    plan_data = st.session_state.plan_data
    tasks = plan_data["tasks"]

    st.success(f"Plan ready — {len(tasks)} tasks")
    for task in tasks:
        st.markdown(f"**{task['id']}.** `{task['type']}` {task['description']}")

    col1, col2 = st.columns([1, 5])
    execute = col1.button("Execute Plan")
    if col2.button("Start Over"):
        st.session_state.plan_data = None
        st.session_state.output_path = None
        st.rerun()

    if execute:
        output_path = _run_research_and_write(plan_data, topic.strip())
        st.session_state.output_path = output_path
        st.rerun()

# ── Step 3: Download ───────────────────────────────────────────────────────────
if st.session_state.output_path:
    st.success("All done!")
    with open(st.session_state.output_path, "rb") as f:
        st.download_button(
            label="Download report.docx",
            data=f,
            file_name=f"{st.session_state.plan_data['folder']}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    if st.button("Start New Research"):
        st.session_state.plan_data = None
        st.session_state.output_path = None
        st.rerun()
