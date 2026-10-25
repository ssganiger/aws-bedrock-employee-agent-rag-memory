"""Create or inspect the Sydney AgentCore Memory used by the fictional demo."""

import boto3


REGION = "ap-southeast-2"
NAME = "ProjectAtlasEmployeeDemoMemory"
NAMESPACE = "/strategy/{memoryStrategyId}/actor/{actorId}/"


def find_memory(client):
    token = None
    while True:
        args = {"maxResults": 20}
        if token:
            args["nextToken"] = token
        page = client.list_memories(**args)
        for row in page.get("memories", []):
            detail = client.get_memory(memoryId=row["id"])["memory"]
            if detail["name"] == NAME:
                return detail
        token = page.get("nextToken")
        if not token:
            return None


def main():
    client = boto3.client("bedrock-agentcore-control", region_name=REGION)
    memory = find_memory(client)
    if memory is None:
        response = client.create_memory(
            name=NAME,
            description="Fictional Project Atlas employee conversations and episodes",
            eventExpiryDuration=7,
            memoryStrategies=[{"episodicMemoryStrategy": {
                "name": "ProjectAtlasEpisodes",
                "namespaceTemplates": [NAMESPACE],
                "reflectionConfiguration": {"namespaceTemplates": [NAMESPACE]},
            }}],
        )
        memory = client.get_memory(memoryId=response["memory"]["id"])["memory"]
        print("Created AgentCore Memory resource.")
    else:
        print("Using existing AgentCore Memory resource.")
    print("Memory ID:", memory["id"])
    print("Status:", memory["status"])
    for strategy in memory.get("strategies", []):
        if strategy.get("name") == "ProjectAtlasEpisodes":
            print("Episodic strategy ID:", strategy["strategyId"])
            print("Episodic strategy status:", strategy.get("status"))


if __name__ == "__main__":
    main()
