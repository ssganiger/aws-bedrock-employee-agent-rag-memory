import unittest
from unittest.mock import Mock, patch

from agent_client import run_agent


SOURCE = {
    "content": {"text": "Project Atlas has three open actions."},
    "location": {"s3Location": {"uri": "s3://example/project-atlas/status.md"}},
}


def stream_client(events):
    client = Mock()
    client.converse_stream.return_value = {"stream": iter(events)}
    return client


class AgentMetricsTests(unittest.TestCase):
    def setUp(self):
        memory_patch = patch("agent_client.get_response_style", return_value=None)
        self.get_response_style = memory_patch.start()
        self.addCleanup(memory_patch.stop)

    @patch("agent_client.create_next_task_via_mcp")
    @patch("agent_client.boto3.client")
    @patch("agent_client.retrieve_sources", return_value=[SOURCE])
    def test_question_stream_reports_text_and_cache_usage(
        self, _retrieve, boto_client, create_task
    ):
        boto_client.return_value = stream_client([
            {"messageStart": {"role": "assistant"}},
            {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": "Atlas "}}},
            {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": "has blockers."}}},
            {"messageStop": {"stopReason": "end_turn"}},
            {"metadata": {
                "usage": {
                    "inputTokens": 20,
                    "outputTokens": 4,
                    "cacheReadInputTokens": 80,
                    "cacheWriteInputTokens": 0,
                },
                "metrics": {"latencyMs": 120},
            }},
        ])
        partial = []

        answer, sources, task, metrics = run_agent(
            "What is open?", on_text=partial.append
        )

        self.assertEqual(answer, "Atlas has blockers.")
        self.assertEqual(partial, ["Atlas ", "Atlas has blockers."])
        self.assertEqual(sources, [SOURCE])
        self.assertIsNone(task)
        self.assertIsNotNone(metrics["ttft_ms"])
        self.assertEqual(metrics["model_service_ms"], 120)
        self.assertEqual(metrics["total_input_tokens"], 100)
        self.assertEqual(metrics["cache_reuse_pct"], 80.0)
        self.assertEqual(metrics["retrieved_chunks"], 1)
        self.assertEqual(metrics["tool_calls"], 0)
        self.assertEqual(metrics["response_format"], "Default prose (no saved preference)")
        content = boto_client.return_value.converse_stream.call_args.kwargs["messages"][0]["content"]
        self.assertIn("two short prose paragraphs", content[2]["text"])
        self.assertEqual(
            metrics["trace"]["model_request"],
            boto_client.return_value.converse_stream.call_args.kwargs,
        )
        self.assertEqual(metrics["trace"]["model_text"], answer)
        create_task.assert_not_called()

    @patch("agent_client.boto3.client")
    @patch("agent_client.retrieve_sources", return_value=[SOURCE])
    def test_personal_memory_is_after_cache_checkpoint(self, _retrieve, boto_client):
        self.get_response_style.return_value = "brief_actions"
        boto_client.return_value = stream_client([
            {"contentBlockDelta": {
                "contentBlockIndex": 0, "delta": {"text": "- One blocker [1]."}
            }},
            {"messageStop": {"stopReason": "end_turn"}},
            {"metadata": {"usage": {"inputTokens": 30, "outputTokens": 5}}},
        ])

        _answer, _sources, _task, metrics = run_agent(
            "What is open?", user_id="demo-taylor"
        )

        self.get_response_style.assert_called_once_with("demo-taylor")
        content = boto_client.return_value.converse_stream.call_args.kwargs["messages"][0]["content"]
        self.assertEqual(content[1], {"cachePoint": {"type": "default"}})
        self.assertIn("only concise action bullets", content[2]["text"])
        self.assertIn("User request: What is open?", content[3]["text"])
        self.assertTrue(metrics["memory_loaded"])
        self.assertEqual(metrics["response_format"], "Brief action bullets (saved preference)")

    @patch("agent_client.create_next_task_via_mcp")
    @patch("agent_client.boto3.client")
    @patch("agent_client.retrieve_sources", return_value=[SOURCE])
    def test_explicit_task_stream_reuses_existing_task(
        self, _retrieve, boto_client, create_task
    ):
        boto_client.return_value = stream_client([
            {"contentBlockStart": {
                "contentBlockIndex": 0,
                "start": {"toolUse": {
                    "toolUseId": "tool-1", "name": "create_next_project_atlas_task"
                }},
            }},
            {"contentBlockDelta": {
                "contentBlockIndex": 0, "delta": {"toolUse": {"input": "{"}}
            }},
            {"contentBlockDelta": {
                "contentBlockIndex": 0, "delta": {"toolUse": {"input": "}"}}
            }},
            {"messageStop": {"stopReason": "tool_use"}},
            {"metadata": {
                "usage": {
                    "inputTokens": 0, "outputTokens": 18,
                    "cacheReadInputTokens": 100, "cacheWriteInputTokens": 0,
                },
                "metrics": {"latencyMs": 150},
            }},
        ])
        create_task.return_value = {
            "created": False,
            "task": {"action_id": "project-atlas#it#test-sign-in-remaining-12"},
        }

        answer, _sources, task, metrics = run_agent(
            "Create an internal task for the next open action."
        )

        self.assertIn("already existed", answer)
        self.assertFalse(task["created"])
        self.assertIsNone(metrics["ttft_ms"])
        self.assertIsNotNone(metrics["first_tool_event_ms"])
        self.assertIsNone(metrics["output_tokens_per_second"])
        self.assertEqual(metrics["tool_calls"], 1)
        self.assertTrue(metrics["duplicate_avoided"])
        self.assertEqual(
            metrics["trace"]["tool_request"],
            {"name": "create_next_project_atlas_task", "input": {}},
        )
        self.assertEqual(metrics["trace"]["tool_result"], task)
        create_task.assert_called_once_with()

    @patch("agent_client.create_next_task_via_mcp")
    @patch("agent_client.boto3.client")
    @patch("agent_client.retrieve_sources", return_value=[SOURCE])
    def test_tool_request_from_question_is_rejected(
        self, _retrieve, boto_client, create_task
    ):
        boto_client.return_value = stream_client([
            {"contentBlockStart": {
                "contentBlockIndex": 0,
                "start": {"toolUse": {
                    "toolUseId": "tool-1", "name": "create_next_project_atlas_task"
                }},
            }},
            {"contentBlockDelta": {
                "contentBlockIndex": 0, "delta": {"toolUse": {"input": "{}"}}
            }},
            {"messageStop": {"stopReason": "tool_use"}},
            {"metadata": {"usage": {"inputTokens": 10, "outputTokens": 2}}},
        ])

        with self.assertRaisesRegex(RuntimeError, "explicit create-task"):
            run_agent("What is the next action?")
        create_task.assert_not_called()


    @patch("agent_client.create_next_task_via_mcp", side_effect=RuntimeError("DynamoDB unavailable"))
    @patch("agent_client.boto3.client")
    @patch("agent_client.retrieve_sources", return_value=[SOURCE])
    def test_tool_failure_retains_partial_observability(
        self, _retrieve, boto_client, _create_task
    ):
        from agent_client import AgentExecutionError
        from observability import build_report

        boto_client.return_value = stream_client([
            {"contentBlockStart": {
                "contentBlockIndex": 0,
                "start": {"toolUse": {
                    "toolUseId": "tool-1", "name": "create_next_project_atlas_task"
                }},
            }},
            {"contentBlockDelta": {
                "contentBlockIndex": 0, "delta": {"toolUse": {"input": "{}"}}
            }},
            {"messageStop": {"stopReason": "tool_use"}},
            {"metadata": {"usage": {"inputTokens": 12, "outputTokens": 3}}},
        ])
        with self.assertRaises(AgentExecutionError) as caught:
            run_agent("Create an internal task for the next open action.")
        error = caught.exception
        self.assertEqual(error.stage, "MCP task tool")
        self.assertEqual(error.metrics["tool_calls"], 1)
        self.assertIsNotNone(error.metrics["tool_ms"])
        report = build_report(
            "Create an internal task for the next open action.",
            sources=error.sources, metrics=error.metrics,
            status="error", error=str(error), error_stage=error.stage,
        )
        self.assertTrue(report["agent"]["tool_failed"])
        self.assertTrue(report["rag"]["retrieval_succeeded"])


if __name__ == "__main__":
    unittest.main()
