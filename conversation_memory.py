"""AgentCore conversation events and cross-session episodic recall for demo users."""

import os
from datetime import datetime, timezone

import boto3

from memory_client import DEMO_USERS, REGION


def configured() -> bool:
    return bool(os.environ.get("ATLAS_AGENTCORE_MEMORY_ID"))


def _client(user_id: str):
    if user_id not in DEMO_USERS:
        raise ValueError("Choose a fictional demo user.")
    if not configured():
        raise RuntimeError("Set ATLAS_AGENTCORE_MEMORY_ID to enable conversations.")
    return boto3.client("bedrock-agentcore", region_name=REGION)


def _memory_id() -> str:
    return os.environ["ATLAS_AGENTCORE_MEMORY_ID"]


def recent_turns(user_id: str, session_id: str, limit: int = 8) -> list[dict]:
    """Return a bounded, chronological window of saved conversational events."""
    client = _client(user_id)
    events = []
    token = None
    while True:
        args = dict(memoryId=_memory_id(), actorId=user_id,
                    sessionId=session_id, includePayloads=True, maxResults=100)
        if token:
            args["nextToken"] = token
        page = client.list_events(**args)
        events.extend(page.get("events", []))
        token = page.get("nextToken")
        if not token:
            break
    events.sort(key=lambda event: (event.get("eventTimestamp", datetime.min.replace(tzinfo=timezone.utc)),
                                   event.get("eventId", "")))
    turns = []
    for event in events:
        for payload in event.get("payload", []):
            block = payload.get("conversational", {})
            role = block.get("role")
            value = block.get("content", {}).get("text", "")
            if role in {"USER", "ASSISTANT", "TOOL"} and value:
                turns.append({"role": role, "text": value[:1500],
                              "event_id": event.get("eventId")})
    return turns[-limit:]


def save_turn(user_id: str, session_id: str, role: str, text: str) -> str:
    if role not in {"USER", "ASSISTANT", "TOOL"}:
        raise ValueError("Unsupported conversation role.")
    response = _client(user_id).create_event(
        memoryId=_memory_id(), actorId=user_id, sessionId=session_id,
        eventTimestamp=datetime.now(timezone.utc),
        payload=[{"conversational": {"content": {"text": text[:6000]},
                                     "role": role}}],
    )
    return response["event"]["eventId"]


def relevant_episodes(user_id: str, request: str, limit: int = 2) -> list[dict]:
    """Retrieve episodes only within this actor's namespace."""
    strategy_id = os.environ.get("ATLAS_EPISODIC_STRATEGY_ID")
    if not strategy_id:
        return []
    namespace = f"/strategy/{strategy_id}/actor/{user_id}/"
    response = _client(user_id).retrieve_memory_records(
        memoryId=_memory_id(), namespace=namespace,
        searchCriteria={"searchQuery": request,
                        "memoryStrategyId": strategy_id, "topK": limit},
        maxResults=limit,
    )
    return [{"id": row["memoryRecordId"],
             "text": row.get("content", {}).get("text", "")[:1500],
             "score": row.get("score")}
            for row in response.get("memoryRecordSummaries", [])]
