"""Small, explicit personal-memory store for fictional demo users."""

import os
import re
from datetime import datetime, timezone

import boto3


REGION = "ap-southeast-2"
MEMORY_KEY = "response_style"
DEMO_USERS = {
    "demo-alex": "Alex Morgan",
    "demo-taylor": "Taylor Chen",
}
STYLES = {
    "brief_actions": "Brief bullets with blockers, owners, and due dates",
    "detailed": "Detailed explanations with background and reasoning",
}


def _table(user_id: str):
    if user_id not in DEMO_USERS:
        raise ValueError("Choose one of the fictional demo users.")
    table_name = os.environ.get("ATLAS_MEMORY_TABLE")
    if not table_name:
        raise RuntimeError("Set ATLAS_MEMORY_TABLE to the DynamoDB memory table name.")
    return boto3.resource("dynamodb", region_name=REGION).Table(table_name)


def get_response_style(user_id: str) -> str | None:
    """Read one user's durable response preference, if present."""
    item = _table(user_id).get_item(
        Key={"user_id": user_id, "memory_key": MEMORY_KEY},
        ConsistentRead=True,
    ).get("Item")
    if item is None:
        return None
    style = item.get("style")
    if style not in STYLES:
        raise ValueError("The saved response style is not supported by this app.")
    return style


def save_response_style(user_id: str, style: str) -> dict:
    """Create or replace only the user's response-style memory."""
    if style not in STYLES:
        raise ValueError("Choose a supported response style.")
    item = {
        "user_id": user_id,
        "memory_key": MEMORY_KEY,
        "style": style,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "explicit_demo_user_request",
    }
    _table(user_id).put_item(Item=item)
    return item


def delete_response_style(user_id: str) -> bool:
    """Forget this preference; return whether a saved item existed."""
    response = _table(user_id).delete_item(
        Key={"user_id": user_id, "memory_key": MEMORY_KEY},
        ReturnValues="ALL_OLD",
    )
    return "Attributes" in response


def parse_remember_command(request: str) -> str | None:
    """Map an explicit 'remember' request to a controlled style value."""
    normalized = " ".join(request.strip().lower().split())
    if not normalized.startswith(("remember ", "please remember ")):
        return None
    match = re.fullmatch(
        r"(?:please )?remember (?:that )?i prefer (.+?)[.!]?",
        normalized,
    )
    if not match:
        raise ValueError("Try: Remember that I prefer short updates with blockers, owners, and due dates.")
    preference = match.group(1)
    brief = bool(re.search(r"\b(short|brief|concise)\b", preference))
    detailed = bool(re.search(r"\b(detailed|detail|in-depth|thorough)\b", preference))
    if brief == detailed:
        raise ValueError("Ask me to remember either a short or detailed response style.")
    return "brief_actions" if brief else "detailed"


def is_forget_command(request: str) -> bool:
    """Identify memory-deletion requests that the page must deny."""
    normalized = " ".join(request.strip().lower().rstrip(".!? ").split())
    return bool(re.fullmatch(
        r"(?:please )?(?:forget|delete|remove) my (?:saved )?(?:response )?preferences?",
        normalized,
    ))
