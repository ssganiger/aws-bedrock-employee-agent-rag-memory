import re
from datetime import datetime
from actions_client import create_or_get_task
from status_source import load_latest_status


def list_open_actions() -> list[dict]:
    status = load_latest_status()
    text = status["text"]

    if "Open actions:" not in text:
        raise ValueError("The status update has no Open actions section.")

    section = text.split("Open actions:", 1)[1].lstrip()
    action_block = section.split("\n\n", 1)[0]
    actions = []

    for line in action_block.splitlines():
        if not line.strip():
            continue

        match = re.fullmatch(
            r"- \[(project-atlas#[a-z0-9-]+#[a-z0-9-]+)\] ([^:]+): (.+) by (\d{1,2} [A-Za-z]+ \d{4})\.",
            line.strip(),
        )
        if not match:
            raise ValueError(f"Cannot parse open action: {line}")

        action_id, team, action_text, due_text = match.groups()
        due_date = datetime.strptime(due_text, "%d %B %Y").date()

        actions.append({
            "action_id": action_id,
            "owner_team": team,
            "title": action_text[0].upper() + action_text[1:],
            "due_date": due_date.isoformat(),
            "source_uri": status["source_uri"],
            "source_status_date": status["status_date"],
        })

    return sorted(actions, key=lambda action: action["due_date"])

def create_next_open_action_task() -> tuple[dict, bool]:
    actions = list_open_actions()
    if not actions:
        raise RuntimeError("No open actions in the latest status update.")

    action = actions[0]
    return create_or_get_task(
        action_id=action["action_id"],
        title=action["title"],
        description=f"Complete the Project Atlas open action: {action['title']}.",
        owner_team=action["owner_team"],
        due_date=action["due_date"],
        source_uri=action["source_uri"],
        source_status_date=action["source_status_date"],
    )

if __name__ == "__main__":
    for action in list_open_actions():
        print(action)
