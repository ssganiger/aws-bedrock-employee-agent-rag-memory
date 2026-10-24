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
        st.subheader("Response")
        response_area = st.empty()
        with st.spinner("Checking Project Atlas documents..."):
            answer, sources, task_result, metrics = run_agent(
                request, on_text=response_area.markdown
            )

        response_area.markdown(answer)

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

        st.subheader("Performance for this request")
        total_card, first_card, cache_card, rate_card = st.columns(4)
        total_card.metric("Total time", f"{metrics['total_ms'] / 1000:.2f} s")
        if task_result is None:
            first_card.metric(
                "TTFT", f"{metrics['ttft_ms']} ms"
                if metrics["ttft_ms"] is not None else "N/A"
            )
        else:
            first_card.metric(
                "First tool event",
                f"{metrics['first_tool_event_ms']} ms"
                if metrics["first_tool_event_ms"] is not None else "N/A",
            )
        cache_card.metric("Cache reused", f"{metrics['cache_reuse_pct']:.1f}%")
        rate = metrics["output_tokens_per_second"]
        rate_card.metric(
            "Approx. output rate",
            f"{rate:.1f} tokens/s" if rate is not None else "N/A",
        )

        with st.expander("How this request ran"):
            timings = [
                {"Stage": "Knowledge Base retrieval", "Time": f"{metrics['retrieval_ms']} ms"},
                {
                    "Stage": "Bedrock model call, measured locally",
                    "Time": f"{metrics['model_ms']} ms",
                },
            ]
            if metrics["model_service_ms"] is not None:
                timings.append({
                    "Stage": "Bedrock reported model latency",
                    "Time": f"{metrics['model_service_ms']} ms",
                })
            if metrics["tool_ms"] is not None:
                timings.append({"Stage": "MCP task tool", "Time": f"{metrics['tool_ms']} ms"})
            st.table(timings)

            st.write(
                f"**Tokens:** {metrics['total_input_tokens']} input "
                f"({metrics['input_tokens']} uncached, "
                f"{metrics['cache_read_tokens']} cache read, "
                f"{metrics['cache_write_tokens']} cache write); "
                f"{metrics['output_tokens']} output."
            )
            st.write(
                f"**Resources used:** {metrics['retrieved_chunks']} retrieved chunks "
                f"from {metrics['source_documents']} documents; "
                f"{metrics['model_calls']} model call; {metrics['tool_calls']} tool call."
            )
            if metrics["duplicate_avoided"]:
                st.write("**Task efficiency:** Existing task reused; no duplicate write.")
            st.caption(
                "TTFT is client-observed time from starting the streaming model call "
                "to its first nonempty text chunk. Tool requests have no answer TTFT. "
                "Cache reuse is cache-read tokens divided by all input tokens. "
                "Output rate is an approximate post-first-text rate."
            )

        st.subheader("Sources")
        for number, result in enumerate(sources, start=1):
            uri = result["location"]["s3Location"]["uri"]
            st.caption(f"[{number}] {uri}")
