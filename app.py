import streamlit as st

from agent_client import run_agent


st.set_page_config(page_title="Project Atlas Employee Assistant")
st.title("Project Atlas Employee Assistant")
st.write("Ask about the fictional pilot or request an internal follow-up task.")

with st.form("assistant_request"):
    request = st.text_area("Your request", height=100)
    submitted = st.form_submit_button("Send")

if submitted:
    if not request.strip():
        st.warning("Enter a question or task request first.")
    else:
        with st.spinner("Checking Project Atlas documents..."):
            answer, sources, task_result = run_agent(request)

        st.subheader("Response")
        st.markdown(answer)

        if task_result is not None:
            task = task_result["task"]
            st.subheader("Internal task")
            if task_result["created"]:
                st.success("New task created.")
            else:
                st.info("Existing task returned; no duplicate was created.")

            st.write(f"**Task:** {task['title']}")
            st.write(f"**Owner:** {task['owner_team']}")
            st.write(f"**Due date:** {task['due_date']}")
            st.write(f"**State:** {task['state']}")
            st.caption(f"Source: {task['source_uri']}")

        st.subheader("Sources")
        for number, result in enumerate(sources, start=1):
            uri = result["location"]["s3Location"]["uri"]
            st.caption(f"[{number}] {uri}")
