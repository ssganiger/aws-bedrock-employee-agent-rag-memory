import unittest

from request_flow import model_flow_steps


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

    def test_task_explains_mcp_and_duplicate_result(self):
        steps = model_flow_steps("Alex Morgan", self.metrics, {"created": False})

        self.assertIn("MCP task tool", steps[4])
        self.assertIn("S3", steps[5])
        self.assertIn("DynamoDB", steps[5])
        self.assertIn("no duplicate", steps[6])


if __name__ == "__main__":
    unittest.main()
