import streamlit as st
from botocore.exceptions import BotoCoreError, ClientError

from agent_client import run_agent
from memory_client import (
    DEMO_USERS,
    STYLES,
    delete_response_style,
    get_response_style,
    is_forget_command,
    parse_remember_command,
    save_response_style,
)


def show_performance(metrics: dict, task_result: dict | None) -> None:
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
            {"Stage": "Personal memory read", "Time": f"{metrics['memory_ms']} ms"},
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
        st.write(
            "**Personal memory:** " +
            ("Saved response style applied." if metrics["memory_loaded"] else "No preference saved.")
        )
        if metrics["duplicate_avoided"]:
            st.write("**Task efficiency:** Existing task reused; no duplicate write.")
        st.caption(
            "TTFT is client-observed time from starting the streaming model call "
            "to its first nonempty text chunk. Tool requests have no answer TTFT. "
            "Cache reuse is cache-read tokens divided by all input tokens. "
            "Output rate is an approximate post-first-text rate."
        )


st.set_page_config(page_title="Project Atlas Employee Assistant")
st.title("Project Atlas Employee Assistant")
st.write("Ask about the fictional pilot, remember a response preference, or request an internal task.")

user_id = st.selectbox(
    "Fictional demo user",
    options=list(DEMO_USERS),
    format_func=lambda value: DEMO_USERS[value],
)
st.caption("This selector demonstrates memory separation. It is not sign-in or access control.")

try:
    current_style = get_response_style(user_id)
except Exception as error:
    st.error(f"Personal memory is unavailable: {error}")
    st.stop()

st.subheader(f"Saved preferences for {DEMO_USERS[user_id]}")
if st.session_state.get("memory_notice"):
    st.success(st.session_state.pop("memory_notice"))
if current_style:
    st.write(f"- **Response style:** {STYLES[current_style]}")
else:
    st.write("No saved preferences.")
st.caption("The saved style changes answer format only. Project facts still come from source documents.")
if current_style and st.button("Forget saved preference"):
    try:
        delete_response_style(user_id)
        st.session_state["memory_notice"] = f"Forgot the saved preference for {DEMO_USERS[user_id]}."
        st.rerun()
    except (BotoCoreError, ClientError) as error:
        st.error(f"Could not forget personal memory: {error}")

with st.form("assistant_request"):
    request = st.text_area("Your request", height=100)
    submitted = st.form_submit_button("Send")
st.caption(
    "To save a style, type 'Remember that I prefer short updates' or "
    "'Remember that I prefer detailed explanations' above. "
    "To remove a saved style, use the Forget button above."
)

if submitted:
    if not request.strip():
        st.warning("Enter a question or task request first.")
    else:
        try:
            if is_forget_command(request):
                st.warning(
                    "Request denied by the app's memory policy: saved preferences "
                    "cannot be deleted by a text request. Use Forget saved "
                    "preference above to delete the saved style."
                )
            else:
                remember_style = parse_remember_command(request)
                if remember_style is not None:
                    save_response_style(user_id, remember_style)
                    st.session_state["memory_notice"] = (
                        f"Remembered for {DEMO_USERS[user_id]}: {STYLES[remember_style]}"
                    )
                    st.rerun()
                elif request.strip().lower().rstrip("?. ") in {
                    "what do you remember about me", "show my memory"
                }:
                    st.info(
                        f"I remember your response preference: {STYLES[current_style]}"
                        if current_style else "I have no saved response preference for you."
                    )
                else:
                    st.subheader("Response")
                    response_area = st.empty()
                    with st.spinner("Checking Project Atlas documents..."):
                        answer, sources, task_result, metrics = run_agent(
                            request, on_text=response_area.markdown, user_id=user_id
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

                    show_performance(metrics, task_result)
                    st.subheader("Sources")
                    for number, result in enumerate(sources, start=1):
                        uri = result["location"]["s3Location"]["uri"]
                        st.caption(f"[{number}] {uri}")
        except (BotoCoreError, ClientError, RuntimeError, ValueError) as error:
            st.error(str(error))
