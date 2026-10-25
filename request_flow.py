"""Plain-language steps shown for one completed assistant request."""


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
        steps.append(
            "Nova 2 Lite generated the source-grounded answer using "
            f"{metrics['response_format']}."
        )
    else:
        steps.append("Nova 2 Lite selected the MCP task tool for this explicit task request.")
        steps.append("The MCP tool checked the latest status document in S3 and the task table in DynamoDB.")
        if task_result["created"]:
            steps.append("The MCP tool created the internal task in DynamoDB.")
        else:
            steps.append("The MCP tool found the existing task in DynamoDB; no duplicate was created.")

    return steps
