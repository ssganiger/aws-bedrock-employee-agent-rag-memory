import streamlit as st
from uuid import uuid4
from botocore.exceptions import BotoCoreError, ClientError

from agent_client import run_agent
from conversation_memory import configured as conversation_configured, recent_turns
from memory_client import (
    DEMO_USERS,
    STYLES,
    delete_response_style,
    delete_personal_fact,
    get_personal_facts,
    get_response_style,
    is_forget_command,
    parse_remember_command,
    learn_personal_facts,
    save_response_style,
)
from observability import build_report, session_summary
from request_flow import model_flow_details, model_flow_steps


def show_request_flow(
    steps: list[str], details: list[dict | None] | None = None
) -> None:
    st.subheader("What internally happened")
    for number, step in enumerate(steps, start=1):
        st.markdown(f"- {step}")
        detail = details[number - 1] if details and number <= len(details) else None
        if detail is not None:
            with st.expander(f"Step {number} details"):
                st.json(detail)


def show_performance(metrics: dict, task_result: dict | None) -> None:
    st.markdown("#### Existing performance measures")
    total_card, first_card, cache_card, rate_card = st.columns(4)
    total_card.metric("Total time", f"{metrics['total_ms'] / 1000:.2f} s")
    if metrics["first_tool_event_ms"] is None:
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
            {"Stage": "Memory read", "Time": f"{metrics['memory_ms']} ms"},
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
            st.write(
                "**Response format:** "
                + metrics.get("response_format", "Unavailable in this running app; restart Streamlit.")
            )
        st.write(
            "**Personal memory:** " +
            (
                "Saved response style loaded for this request."
                if metrics["memory_loaded"] else "No preference saved."
            )
        )
        st.write(
            f"**Conversation:** {metrics.get('conversation_turns_loaded', 0)} recent turns, "
            f"{metrics.get('episodes_loaded', 0)} episodes, "
            f"{metrics.get('personal_facts_loaded', 0)} personal facts loaded."
        )
        if metrics.get("conversation_save_error"):
            st.warning("The answer was produced, but saving conversation history failed: " +
                       metrics["conversation_save_error"])
        if metrics["duplicate_avoided"]:
            st.write("**Task efficiency:** Existing task reused; no duplicate write.")
        st.caption(
            "TTFT is client-observed time from starting the streaming model call "
            "to its first nonempty text chunk. Tool requests have no answer TTFT. "
            "Cache reuse is cache-read tokens divided by all input tokens. "
            "Output rate is an approximate post-first-text rate."
        )


def show_observability(report: dict, metrics: dict | None = None,
                       task_result: dict | None = None) -> None:
    """Show observed values and explicitly mark unavailable evaluations."""
    history = st.session_state.setdefault("observability_history", [])
    history.append(report)
    st.subheader("Observability")
    st.caption(
        "This transaction is measured by the app. Session rates cover only "
        "requests sent from this browser session; refreshing may reset them."
    )
    system = report["system"]
    cards = st.columns(4)
    cards[0].metric("Request status", report["status"].title())
    cards[1].metric(
        "Backend latency",
        f"{system['backend_latency_ms']} ms"
        if system["backend_latency_ms"] is not None else "N/A",
    )
    cards[2].metric(
        "Model cost estimate",
        f"${system['estimated_model_usd']:.6f}"
        if system["estimated_model_usd"] is not None else "N/A",
    )
    cards[3].metric(
        "Cache read",
        str(system["cache_read_tokens"])
        if system["cache_read_tokens"] is not None else "N/A",
    )
    with st.expander("System level", expanded=True):
        st.json(system)
        st.caption("Error on this request: " + (report["error"] or "None reported."))
        if report["error_stage"]:
            st.caption("Failed stage: " + report["error_stage"])
        st.caption("Cost is a model-only estimate when all four pricing rates are configured.")
    with st.expander("RAG level"):
        rag = report["rag"]
        retrieval_state = (
            "Succeeded" if rag["retrieval_succeeded"] else
            "Failed" if rag["retrieval_succeeded"] is False else "N/A"
        )
        recall = (
            f"{rag['recall_at_k']:.0%}"
            if rag["recall_at_k"] is not None else "N/A"
        )
        st.write(
            f"**Retrieval:** {retrieval_state}; "
            f"**chunks returned:** {rag['returned_chunks'] if rag['returned_chunks'] is not None else 'N/A'}; "
            f"**Recall@{rag['retrieval_k']}:** {recall}"
        )
        if rag["retrieved"]:
            st.table(rag["retrieved"])
        st.json(rag)
        st.caption(
            "Retrieval scores rank passages; they are not Recall@K or answer-quality scores. "
            "Recall@K is calculated only for an exact question in the small labelled demo set."
        )
    with st.expander("Answer level"):
        answer_observation = report["answer"]
        st.write("**Citation-number check:** " + (answer_observation["citation_check"] or "N/A"))
        st.write("**Faithfulness / groundedness / answer relevance:** N/A without an evaluator.")
        st.json(answer_observation)
        st.caption("Citation-number checks validate references, not factual support.")
    with st.expander("Agent level"):
        agent = report["agent"]
        st.write(
            f"**Model calls:** {agent['model_calls']}; "
            f"**tool calls:** {agent['tool_calls']}; "
            f"**tool outcome:** {'Success' if agent['tool_succeeded'] else 'Failed' if agent['tool_failed'] else 'N/A'}."
        )
        st.json(agent)
        st.caption(
            "Application retry and loop counts exclude any retries inside the AWS SDK. "
            "Recording a task does not complete the underlying work."
        )
    with st.expander("Memory level"):
        st.json(report["memory"])
        st.caption("Raw turns and episodes live in AgentCore; response style and supported personal facts live in DynamoDB.")
    with st.expander("Session rates and resource use"):
        summary = session_summary(history)
        st.write(f"**Transactions in this session:** {summary['transactions']}")
        st.write(
            f"**Error rate:** {summary['error_rate_percent']:.1f}%; "
            f"**retrieval success rate:** "
            + (f"{summary['retrieval_success_rate_percent']:.1f}%" if summary['retrieval_success_rate_percent'] is not None else "N/A")
            + "; **tool success rate:** "
            + (f"{summary['tool_success_rate_percent']:.1f}%" if summary['tool_success_rate_percent'] is not None else "N/A")
        )
        st.json(summary)
        if metrics is not None:
            st.json({
                "retrieved_chunks": metrics.get("retrieved_chunks"),
                "source_documents": metrics.get("source_documents"),
                "model_calls": metrics.get("model_calls"),
                "tool_calls": metrics.get("tool_calls"),
                "response_format": metrics.get("response_format"),
            })
        st.caption("Rates use this browser session only. Quality failure rate needs evaluated answers.")
    if metrics is not None:
        show_performance(metrics, task_result)


st.set_page_config(page_title="Project Atlas Employee Assistant")
st.title("Project Atlas Employee Assistant")
st.write("Ask about the fictional pilot, remember a response preference, or request an internal task.")

user_id = st.selectbox(
    "Fictional demo user",
    options=list(DEMO_USERS),
    format_func=lambda value: DEMO_USERS[value],
)
st.caption("This selector demonstrates memory separation. It is not sign-in or access control.")

session_id = None
if conversation_configured():
    session_key = f"atlas_conversation_{user_id}"
    session_id = st.query_params.get(session_key)
    if not session_id:
        session_id = uuid4().hex
        st.query_params[session_key] = session_id
    st.caption(f"Conversation ID: {session_id[:8]} (kept in this page URL)")
    if st.button("New conversation"):
        session_id = uuid4().hex
        st.query_params[session_key] = session_id
        st.rerun()
    try:
        previous_turns = recent_turns(user_id, session_id)
    except Exception as error:
        st.error(f"Conversation history is unavailable: {error}")
        st.stop()
    if previous_turns:
        with st.expander(f"Conversation history ({len(previous_turns)} recent turns)"):
            for turn in previous_turns:
                st.write(f"**{turn['role'].title()}:** {turn['text']}")
else:
    st.caption("Conversation history is not configured. Set ATLAS_AGENTCORE_MEMORY_ID to enable it.")

try:
    current_style = get_response_style(user_id)
    current_facts = get_personal_facts(user_id)
except Exception as error:
    st.error(f"Personal memory is unavailable: {error}")
    st.stop()

with st.form("assistant_request"):
    request = st.text_area("Your request", height=100)
    submitted = st.form_submit_button("Send")
learned = []
if submitted and request.strip():
    try:
        learned = learn_personal_facts(user_id, request)
        if learned:
            current_facts = get_personal_facts(user_id)
    except (BotoCoreError, ClientError) as error:
        st.error(f"Could not save a personal fact: {error}")
        st.stop()
st.caption(
    "To save a style, type 'Remember that I prefer short updates' or "
    "'Remember that I prefer detailed explanations' above. "
    "To remove a saved style, use the Forget button below when it appears."
)
if st.session_state.get("memory_notice"):
    notice = st.session_state.pop("memory_notice")
    flow = st.session_state.pop("memory_notice_flow", None)
    details = st.session_state.pop("memory_notice_details", None)
    if flow:
        show_request_flow(flow, details)
    st.success(notice)
    pending_report = st.session_state.pop("memory_notice_observability", None)
    if pending_report is not None:
        show_observability(pending_report)
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
            st.session_state["memory_notice_observability"] = build_report(
                "Forget saved preference", status="success"
            )
            st.rerun()
        except (BotoCoreError, ClientError) as error:
            st.error(f"Could not forget personal memory: {error}")

if current_facts:
    st.subheader(f"Personal facts learned for {DEMO_USERS[user_id]}")
    st.caption("Learned automatically from clear first-person statements. These are not Project Atlas status facts.")
    for fact in current_facts:
        st.write(f"**{fact['kind'].title()}:** {fact['value']}")
        if st.button(f"Forget {fact['kind']} fact", key=f"forget_{user_id}_{fact['kind']}"):
            delete_personal_fact(user_id, fact["kind"])
            st.rerun()

if submitted:
    if not request.strip():
        show_request_flow([
            f"Checked {DEMO_USERS[user_id]}'s saved preference in DynamoDB.",
            "The request was empty, so no Knowledge Base retrieval or model call followed.",
        ], [
            {"user_id": user_id, "saved_style": current_style},
            {"request_text": request},
        ])
        st.warning("Enter a question or task request first.")
        show_observability(build_report(request, status="rejected"))
    else:
        flow_area = None
        try:
            if is_forget_command(request):
                show_request_flow([
                    f"Checked {DEMO_USERS[user_id]}'s saved preference in DynamoDB.",
                    "Recognized a request to delete personal memory.",
                    "Applied the app rule: text requests cannot delete saved preferences.",
                    "Stopped before Knowledge Base retrieval, Bedrock, or a DynamoDB deletion.",
                ], [
                    {"user_id": user_id, "saved_style": current_style},
                    {"request_text": request},
                    {"decision": "Denied; only the Forget saved preference button can delete."},
                    None,
                ])
                st.warning(
                    "Request denied by the app's memory policy: saved preferences "
                    "cannot be deleted by a text request. Use Forget saved "
                    "preference below to delete the saved style."
                )
                show_observability(build_report(request, status="denied"))
            else:
                remember_style = parse_remember_command(request)
                if remember_style is not None:
                    saved_item = save_response_style(user_id, remember_style)
                    st.session_state["memory_notice_flow"] = [
                        f"Checked {DEMO_USERS[user_id]}'s saved preference in DynamoDB.",
                        "Recognized an explicit request to remember a response style.",
                        f"Saved {STYLES[remember_style]} for {DEMO_USERS[user_id]} in DynamoDB.",
                        "No Knowledge Base retrieval or Bedrock model call was needed.",
                    ]
                    st.session_state["memory_notice_details"] = [
                        {"user_id": user_id, "previous_saved_style": current_style},
                        {"request_text": request, "parsed_style": remember_style},
                        {"DynamoDB_item_written": saved_item},
                        None,
                    ]
                    st.session_state["memory_notice"] = (
                        f"Remembered for {DEMO_USERS[user_id]}: {STYLES[remember_style]}"
                    )
                    st.session_state["memory_notice_observability"] = build_report(
                        request, status="success"
                    )
                    st.rerun()
                elif request.strip().lower().rstrip("?. ") in {
                    "what do you remember about me", "show my memory"
                }:
                    show_request_flow([
                        f"Read {DEMO_USERS[user_id]}'s response preference from DynamoDB.",
                        "Displayed the saved preference below; no Knowledge Base or Bedrock model call was needed.",
                    ], [
                        {"user_id": user_id, "saved_style": current_style},
                        None,
                    ])
                    remembered = (
                        f"Response preference: {STYLES[current_style]}."
                        if current_style else "No response preference saved."
                    )
                    if current_facts:
                        remembered += " Personal facts: " + "; ".join(
                            f"{fact['kind']} = {fact['value']}" for fact in current_facts
                        ) + "."
                    else:
                        remembered += " No personal facts learned."
                    st.info(remembered)
                    show_observability(build_report(request))
                else:
                    flow_area = st.empty()
                    st.subheader("Response")
                    response_area = st.empty()
                    with st.spinner("Checking Project Atlas documents..."):
                        answer, sources, task_result, metrics = run_agent(
                            request, on_text=response_area.markdown, user_id=user_id,
                            session_id=session_id, personal_facts=current_facts,
                        )
                    if learned:
                        metrics["personal_facts_learned"] = [
                            {"kind": fact["kind"], "value": fact["value"]} for fact in learned
                        ]
                    with flow_area.container():
                        show_request_flow(
                            model_flow_steps(DEMO_USERS[user_id], metrics, task_result),
                            model_flow_details(
                                user_id, request, metrics, sources, task_result
                            ),
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

                    show_observability(
                        build_report(request, answer, sources, task_result, metrics),
                        metrics, task_result,
                    )
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
            partial_metrics = getattr(error, "metrics", None)
            partial_sources = getattr(error, "sources", None)
            show_observability(
                build_report(
                    request, sources=partial_sources, metrics=partial_metrics,
                    status="error", error=str(error),
                    rag_attempted=flow_area is not None,
                    error_stage=getattr(error, "stage", None),
                ),
                partial_metrics,
            )
