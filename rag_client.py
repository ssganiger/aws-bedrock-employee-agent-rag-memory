import os

import boto3


def retrieve_sources(question: str) -> list[dict]:
    kb_id = os.environ["BEDROCK_KNOWLEDGE_BASE_ID"]
    client = boto3.client("bedrock-agent-runtime", region_name="ap-southeast-2")

    response = client.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": question},
        retrievalConfiguration={
            "vectorSearchConfiguration": {"numberOfResults": 5}
        },
    )
    return response["retrievalResults"]


if __name__ == "__main__":
    question = "What remains outstanding before the Project Atlas pilot can launch?"

    for result in retrieve_sources(question):
        print("Source:", result["location"]["s3Location"]["uri"])
        print("Excerpt:", result["content"]["text"][:300])
        print()