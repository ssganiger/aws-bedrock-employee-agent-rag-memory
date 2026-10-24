from datetime import datetime, timezone

import os
import boto3
from botocore.exceptions import ClientError


TABLE_NAME = os.environ["ATLAS_ACTIONS_TABLE"]
REGION = "ap-southeast-2"


def create_or_get_task(
    action_id: str,
    title: str,
    description: str,
    owner_team: str,
    due_date: str,
    source_uri: str,
    source_status_date: str,
) -> tuple[dict, bool]:
    fields = (
        action_id, title, description, owner_team,
        due_date, source_uri, source_status_date,
    )
    if any(not value.strip() for value in fields):
        raise ValueError("Every task field is required.")

    item = {
        "action_id": action_id,
        "project_name": "Project Atlas",
        "title": title,
        "description": description,
        "owner_team": owner_team,
        "due_date": due_date,
        "source_uri": source_uri,
        "source_status_date": source_status_date,
        "state": "Open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE_NAME)

    try:
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(action_id)",
        )
        return item, True
    except ClientError as error:
        if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise

    existing = table.get_item(
        Key={"action_id": action_id},
        ConsistentRead=True,
    ).get("Item")
    if existing is None:
        raise RuntimeError("Task already exists but could not be read.")
    return existing, False
