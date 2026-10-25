import unittest

from request_flow import model_flow_details, model_flow_steps


class RequestFlowTests(unittest.TestCase):
    def setUp(self):
        self.metrics = {
            "memory_loaded": True,
            "retrieved_chunks": 5,
            "source_documents": 4,
            "cache_read_tokens": 2434,
            "cache_write_tokens": 0,
            "response_format": "Brief action bullets (saved preference)",
        }

    def test_question_explains_memory_rag_cache_and_answer_in_order(self):
        steps = model_flow_steps("Alex Morgan", self.metrics, None)

        self.assertEqual(len(steps), 5)
        self.assertIn("saved response preference", steps[0])
        self.assertIn("Knowledge Base", steps[1])
        self.assertIn("cache checkpoint", steps[2])
        self.assertIn("cache hit", steps[3].lower())
        self.assertIn("2434", steps[3])
        self.assertIn("Brief action bullets", steps[4])

    def test_cache_write_is_not_presented_as_a_hit(self):
        self.metrics.update({
            "memory_loaded": False,
            "cache_read_tokens": 0,
            "cache_write_tokens": 1357,
            "response_format": "Default prose (no saved preference)",
        })
        steps = model_flow_steps("Alex Morgan", self.metrics, None)

        self.assertIn("no response preference is saved", steps[0])
        self.assertIn("cache write", steps[3].lower())
        self.assertIn("No tokens were read", steps[3])
        self.assertNotIn("cache hit", steps[3].lower())

    def test_older_running_agent_does_not_crash_or_claim_a_format(self):
        del self.metrics["response_format"]

        steps = model_flow_steps("Alex Morgan", self.metrics, None)

        self.assertIn("did not report which response format", steps[-1])
        self.assertIn("Restart Streamlit", steps[-1])

    def test_task_explains_mcp_and_duplicate_result(self):
        steps = model_flow_steps("Alex Morgan", self.metrics, {"created": False})

        self.assertIn("MCP task tool", steps[4])
        self.assertIn("S3", steps[5])
        self.assertIn("DynamoDB", steps[5])
        self.assertIn("no duplicate", steps[6])

    def test_details_show_actual_passages_prompt_and_server_cache_counts(self):
        self.metrics.update({
            "input_tokens": 12,
            "cache_reuse_pct": 99.5,
            "trace": {
                "memory_style": "brief_actions",
                "model_request": {"messages": [{"content": [
                    {"text": "source"}, {"cachePoint": {"type": "default"}}
                ]}]},
                "stop_reason": "end_turn",
                "model_text": "- IT action [1].",
            },
        })
        sources = [{
            "location": {"s3Location": {"uri": "s3://example/status.md"}},
            "content": {"text": "The status document says IT has an open action."},
            "score": 0.91,
        }]

        details = model_flow_details(
            "demo-alex", "What remains open?", self.metrics, sources, None
        )

        self.assertEqual(len(details), 5)
        self.assertEqual(details[0]["saved_style"], "brief_actions")
        self.assertEqual(
            details[1]["retrieved_passages"][0]["text"], sources[0]["content"]["text"]
        )
        self.assertEqual(
            details[2]["ConverseStream_request"], self.metrics["trace"]["model_request"]
        )
        self.assertEqual(details[3]["cache_read_input_tokens"], 2434)
        self.assertEqual(details[3]["cache_checkpoints_sent"], [{"type": "default"}])
        self.assertEqual(details[4]["model_text"], "- IT action [1].")


if __name__ == "__main__":
    unittest.main()
