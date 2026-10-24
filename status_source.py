import re
import os
from datetime import datetime

import boto3


BUCKET = os.environ["ATLAS_SOURCE_BUCKET"]
PREFIX = "project-atlas/"


def load_latest_status() -> dict:
    s3 = boto3.client("s3", region_name="ap-southeast-2")
    paginator = s3.get_paginator("list_objects_v2")

    keys = [
        obj["Key"]
        for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX)
        for obj in page.get("Contents", [])
        if obj["Key"].split("/")[-1].startswith("project-atlas-status")
        and obj["Key"].endswith(".md")
    ]
    if not keys:
        raise RuntimeError("No Project Atlas status update found.")

    latest = None
    for key in keys:
        body = s3.get_object(Bucket=BUCKET, Key=key)["Body"]
        text = body.read().decode("utf-8")
        match = re.search(r"^Status date:\s*(.+)$", text, re.MULTILINE)
        if not match:
            raise ValueError(f"Status date missing from {key}")

        status_date = datetime.strptime(
            match.group(1).strip(), "%d %B %Y"
        ).date()

        if latest is None or status_date > latest["date"]:
            latest = {"date": status_date, "key": key, "text": text}

    return {
        "status_date": latest["date"].isoformat(),
        "source_uri": f"s3://{BUCKET}/{latest['key']}",
        "text": latest["text"],
    }


if __name__ == "__main__":
    status = load_latest_status()
    print("Status date:", status["status_date"])
    print("Source:", status["source_uri"])
    print(status["text"])
