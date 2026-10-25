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
from request_flow import model_flow_steps


def show_request_flow(steps: list[str]) -> None:
    st.subheader("What internally happened")
    for step in steps:
        st.markdown(f"- {step}")


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
        if task_result is None:
            st.write(f"**Response format:** {metrics['response_format']}")
        st.write(
            "**Personal memory:** " +
            (
                "Saved response style loaded for this request."
                if metrics["memory_loaded"] else "No preference saved."
            )
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

with st.form("assistant_request"):
    request = st.text_area("Your request", height=100)
    submitted = st.form_submit_button("Send")
st.caption(
    "To save a style, type 'Remember that I prefer short updates' or "
    "'Remember that I prefer detailed explanations' above. "
    "To remove a saved style, use the Forget button below when it appears."
)
if st.session_state.get("memory_notice"):
    notice = st.session_state.pop("memory_notice")
    flow = st.session_state.pop("memory_notice_flow", None)
    if flow:
        show_request_flow(flow)
    st.success(notice)
if current_style:
    st.subheader(f"Saved preferences for {DEMO_USERS[user_id]}")
    st.write(f"- **Response style:** {STYLES[current_style]}")
    st.caption(
        "The saved style changes answer format only. "
        "Project facts still come from source documents."
    )
    if st.button("Forget saved preference"):
        try:
            delete_response_style(user_id)
            st.session_state["memory_notice"] = (
                f"Forgot the saved preference for {DEMO_USERS[user_id]}."
            )
            st.rerun()
        except (BotoCoreError, ClientError) as error:
            st.error(f"Could not forget personal memory: {error}")

if submitted:
    if not request.strip():
        show_request_flow([
            f"Checked {DEMO_USERS[user_id]}'s saved preference in DynamoDB.",
            "The request was empty, so no Knowledge Base retrieval or model call followed.",
        ])
        st.warning("Enter a question or task request first.")
    else:
        flow_area = None
        try:
            if is_forget_command(request):
                show_request_flow([
                    f"Checked {DEMO_USERS[user_id]}'s saved preference in DynamoDB.",
                    "Recognized a request to delete personal memory.",
                    "Applied the app rule: text requests cannot delete saved preferences.",
                    "Stopped before Knowledge Base retrieval, Bedrock, or a DynamoDB deletion.",
                ])
                st.warning(
                    "Request denied by the app's memory policy: saved preferences "
                    "cannot be deleted by a text request. Use Forget saved "
                    "preference below to delete the saved style."
                )
            else:
                remember_style = parse_remember_command(request)
                if remember_style is not None:
                    save_response_style(user_id, remember_style)
                    st.session_state["memory_notice_flow"] = [
                        f"Checked {DEMO_USERS[user_id]}'s saved preference in DynamoDB.",
                        "Recognized an explicit request to remember a response style.",
                        f"Saved {STYLES[remember_style]} for {DEMO_USERS[user_id]} in DynamoDB.",
                        "No Knowledge Base retrieval or Bedrock model call was needed.",
                    ]
                    st.session_state["memory_notice"] = (
                        f"Remembered for {DEMO_USERS[user_id]}: {STYLES[remember_style]}"
                    )
                    st.rerun()
                elif request.strip().lower().rstrip("?. ") in {
                    "what do you remember about me", "show my memory"
                }:
                    show_request_flow([
                        f"Read {DEMO_USERS[user_id]}'s response preference from DynamoDB.",
                        "Displayed the saved preference below; no Knowledge Base or Bedrock model call was needed.",
                    ])
                    st.info(
                        f"I remember your response preference: {STYLES[current_style]}"
                        if current_style else "I have no saved response preference for you."
                    )
                else:
                    flow_area = st.empty()
                    st.subheader("Response")
                    response_area = st.empty()
                    with st.spinner("Checking Project Atlas documents..."):
                        answer, sources, task_result, metrics = run_agent(
                            request, on_text=response_area.markdown, user_id=user_id
                        )
                    with flow_area.container():
                        show_request_flow(
                            model_flow_steps(DEMO_USERS[user_id], metrics, task_result)
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
            failure_step = [
                "The request stopped before a complete result because the app "
                "or an AWS service returned an error."
            ]
            if flow_area is None:
                show_request_flow(failure_step)
            else:
                with flow_area.container():
                    show_request_flow(failure_step)
            st.error(str(error))
