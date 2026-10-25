"""Plain-language steps shown for one completed assistant request."""

from memory_client import MEMORY_KEY


def model_flow_steps(user_name: str, metrics: dict, task_result: dict | None) -> list[str]:
    if metrics["memory_loaded"]:
        memory_step = f"Read {user_name}'s saved response preference from DynamoDB."
    else:
        memory_step = f"Checked DynamoDB for {user_name}; no response preference is saved."

    steps = [
        memory_step,
        (
            "Retrieved "
            f"{metrics['retrieved_chunks']} passage(s) from "
            f"{metrics['source_documents']} Project Atlas document(s) "
            "through the Bedrock Knowledge Base."
        ),
        "Built a Bedrock prompt with those passages and a cache checkpoint.",
    ]

    read = metrics["cache_read_tokens"]
    written = metrics["cache_write_tokens"]
    if read and written:
        steps.append(
            f"Prompt cache: reused {read} input tokens and wrote {written} tokens."
        )
    elif read:
        steps.append(f"Prompt cache hit: reused {read} input tokens.")
    elif written:
        steps.append(
            f"Prompt cache write: stored {written} input tokens for possible reuse. "
            "No tokens were read from cache on this request."
        )
    else:
        steps.append("Prompt cache: Bedrock reported no cache read or write for this request.")

    if task_result is None:
        response_format = metrics.get("response_format")
        if response_format:
            steps.append(
                "Nova 2 Lite generated the source-grounded answer using "
                f"{response_format}."
            )
        else:
            steps.append(
                "Nova 2 Lite generated the answer, but this running app did not "
                "report which response format it used. Restart Streamlit to load "
                "the latest code."
            )
    else:
        steps.append("Nova 2 Lite selected the MCP task tool for this explicit task request.")
        steps.append("The MCP tool checked the latest status document in S3 and the task table in DynamoDB.")
        if task_result["created"]:
            steps.append("The MCP tool created the internal task in DynamoDB.")
        else:
            steps.append("The MCP tool found the existing task in DynamoDB; no duplicate was created.")

    return steps


def model_flow_details(
    user_id: str,
    request: str,
    metrics: dict,
    sources: list[dict],
    task_result: dict | None,
) -> list[dict | None]:
    """Return observed request/response data aligned with model_flow_steps."""
    trace = metrics.get("trace", {})
    memory_detail = {
        "DynamoDB_key_read": {"user_id": user_id, "memory_key": MEMORY_KEY},
        "saved_style": trace.get("memory_style")
        if "memory_style" in trace else "Not reported by this running app",
    }
    retrieval_detail = {
        "query_sent_to_knowledge_base": request,
        "retrieved_passages": [
            {
                "source_uri": source.get("location", {}).get("s3Location", {}).get("uri"),
                "text": source.get("content", {}).get("text"),
                "score": source.get("score"),
            }
            for source in sources
        ],
    }
    prompt_detail = (
        {"ConverseStream_request": trace["model_request"]}
        if "model_request" in trace else None
    )
    cache_points = [
        block["cachePoint"]
        for message in trace.get("model_request", {}).get("messages", [])
        for block in message.get("content", [])
        if "cachePoint" in block
    ]
    cache_detail = {
        "cache_checkpoints_sent": cache_points,
        "uncached_input_tokens": metrics["input_tokens"],
        "cache_read_input_tokens": metrics["cache_read_tokens"],
        "cache_write_input_tokens": metrics["cache_write_tokens"],
        "cache_reuse_percent": metrics["cache_reuse_pct"],
    }
    if task_result is None:
        model_detail = {
            "stop_reason": trace.get("stop_reason", "Not reported"),
            "model_text": trace.get("model_text", "Not reported by this running app"),
            "response_format": metrics.get("response_format", "Not reported"),
        }
        return [memory_detail, retrieval_detail, prompt_detail, cache_detail, model_detail]

    tool_request = trace.get("tool_request")
    tool_result = trace.get("tool_result", task_result)
    task = tool_result.get("task", {})
    source_detail = {
        "source_uri": task.get("source_uri"),
        "source_status_date": task.get("source_status_date"),
        "action_id": task.get("action_id"),
    }
    return [
        memory_detail,
        retrieval_detail,
        prompt_detail,
        cache_detail,
        {"model_tool_request": tool_request} if tool_request else None,
        source_detail,
        {"MCP_tool_result": tool_result},
    ]
