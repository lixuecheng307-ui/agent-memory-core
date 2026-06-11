from pathlib import Path

from memory_core import RagMemorySystem


def main():
    try:
        import streamlit as st
    except Exception:
        print("Streamlit is optional. Install with: pip install -e .[web]")
        return

    st.set_page_config(page_title="Agent Memory Core Demo", layout="wide")
    st.title("Agent Memory Core Demo")
    db_path = st.sidebar.text_input("SQLite DB", ".agent_memory_core/web_demo.sqlite3")
    project_id = st.sidebar.text_input("Project", "demo")
    system = RagMemorySystem(Path(db_path), default_project_id=project_id)

    tab_remember, tab_search, tab_list, tab_bench = st.tabs(["Remember", "Search", "List", "Benchmark"])
    with tab_remember:
        text = st.text_area("Memory")
        if st.button("Remember") and text.strip():
            record = system.remember(text, project_id=project_id)
            st.write(record.memory_id if record else "not stored")
    with tab_search:
        query = st.text_input("Query")
        if st.button("Build Context") and query.strip():
            traced = system.build_context_with_trace(query, project_id=project_id)
            st.code(traced.context)
            st.json(
                {
                    "included": [item.__dict__ for item in traced.retrieval_trace.included_memories],
                    "excluded": [item.__dict__ for item in traced.retrieval_trace.excluded_memories],
                }
            )
    with tab_list:
        for memory in system.list_memories(project_id=project_id):
            st.write(memory.memory_id, memory.status.value, memory.content)
    with tab_bench:
        st.write("Run `memory-core benchmark` to generate benchmark_results.json and benchmark_report.md.")


if __name__ == "__main__":
    main()
