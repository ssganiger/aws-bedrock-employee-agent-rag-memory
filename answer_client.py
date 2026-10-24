import boto3

from rag_client import retrieve_sources


MODEL_ID = "global.amazon.nova-2-lite-v1:0"


def answer_question(
    question: str, sources: list[dict] | None = None
) -> tuple[str, list[dict]]:
    if sources is None:
        sources = retrieve_sources(question)
    if not sources:
        return "I could not find relevant Project Atlas documents.", []

    context = "\n\n".join(
        f"[{number}] {result['content']['text']}"
        for number, result in enumerate(sources, start=1)
    )

    client = boto3.client("bedrock-runtime", region_name="ap-southeast-2")
    response = client.converse(
        modelId=MODEL_ID,
        system=[{
            "text": (
                "Answer using only the supplied sources. Cite supporting source "
                "numbers such as [1]. If the sources do not contain the answer, "
                "say so. A due date does not prove an action is complete."
            )
        }],
        messages=[{
            "role": "user",
            "content": [
                {"text": f"Sources:\n{context}"},
                {"cachePoint": {"type": "default"}},
                {"text": f"Question: {question}"},
            ],
        }],
        inferenceConfig={"maxTokens": 450, "temperature": 0.1},
    )

    print("Bedrock usage:", response["usage"])
    answer = "".join(
        block["text"]
        for block in response["output"]["message"]["content"]
        if "text" in block
    )
    return answer, sources


if __name__ == "__main__":
    first_question = "What remains outstanding before the Project Atlas pilot can launch?"
    sources = retrieve_sources(first_question)

    questions = [
        first_question,
        "What must the assistant check before creating a task for the next open action?",
    ]

    for question in questions:
        print("\nQuestion:", question)
        answer, _ = answer_question(question, sources)
        print(answer)

    print("\nSource numbers:")
    for number, result in enumerate(sources, start=1):
        print(f"[{number}] {result['location']['s3Location']['uri']}")