import unittest
from unittest.mock import patch

from observability import build_report, session_summary


QUESTION = "What remains outstanding before the Project Atlas pilot can launch?"
SOURCE = {
    "content": {"text": "IT must test the remaining 12 accounts."},
    "location": {"s3Location": {"uri": "s3://example/project-atlas-status.md"}},
    "score": 0.89,
}
METRICS = {
    "total_ms": 1200, "memory_ms": 20, "retrieval_ms": 100,
    "model_ms": 1000, "model_service_ms": 900,
    "ttft_ms": 200, "first_tool_event_ms": None, "tool_ms": None,
    "input_tokens": 100, "output_tokens": 50,
    "cache_read_tokens": 400, "cache_write_tokens": 0,
    "cache_reuse_pct": 80.0, "output_tokens_per_second": 40.0,
    "source_documents": 1, "model_calls": 1, "tool_calls": 0,
    "duplicate_avoided": False, "trace": {},
}


class ObservabilityTests(unittest.TestCase):
    def test_gold_question_recall_and_citation_checks_are_separate_from_judge(self):
        report = build_report(QUESTION, "IT must test sign-in [1][3].", [SOURCE], None, METRICS)
        self.assertEqual(report["rag"]["recall_at_k"], 1.0)
        self.assertEqual(report["rag"]["retrieved"][0]["retrieval_score"], 0.89)
        self.assertEqual(report["answer"]["invalid_citation_numbers"], [3])
        self.assertIsNone(report["answer"]["faithfulness"])
        self.assertIsNone(report["rag"]["reranker_score"])

    def test_cost_is_unavailable_without_rates_and_model_only_with_rates(self):
        names = {
            "ATLAS_INPUT_USD_PER_MILLION": "1",
            "ATLAS_OUTPUT_USD_PER_MILLION": "2",
            "ATLAS_CACHE_READ_USD_PER_MILLION": "0.5",
            "ATLAS_CACHE_WRITE_USD_PER_MILLION": "1.5",
        }
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(build_report(QUESTION, "Answer [1]", [SOURCE], None, METRICS)["system"]["estimated_model_usd"])
        with patch.dict("os.environ", names, clear=True):
            report = build_report(QUESTION, "Answer [1]", [SOURCE], None, METRICS)
        self.assertAlmostEqual(report["system"]["estimated_model_usd"], 0.0004)

    def test_session_rates_exclude_memory_from_retrieval_denominator(self):
        memory = build_report("Show my memory")
        good = build_report(QUESTION, "Answer [1]", [SOURCE], None, METRICS)
        failed = build_report(QUESTION, status="error", error="KB unavailable", rag_attempted=True)
        summary = session_summary([memory, good, failed])
        self.assertEqual(summary["transactions"], 3)
        self.assertAlmostEqual(summary["error_rate_percent"], 100 / 3)
        self.assertEqual(summary["retrieval_success_rate_percent"], 100.0)
        self.assertEqual(summary["retrieval_outcome_unknown"], 1)
        self.assertIsNone(summary["hallucination_rate_percent"])


if __name__ == "__main__":
    unittest.main()
