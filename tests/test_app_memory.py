import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class MemoryPageTests(unittest.TestCase):
    def test_question_shows_entire_backend_flow_above_response(self):
        metrics = {
            "total_ms": 1200, "ttft_ms": 200, "first_tool_event_ms": None,
            "cache_reuse_pct": 75.0, "output_tokens_per_second": 20.0,
            "memory_ms": 12, "retrieval_ms": 80, "model_ms": 1000,
            "model_service_ms": 900, "tool_ms": None,
            "total_input_tokens": 100, "input_tokens": 25,
            "cache_read_tokens": 75, "cache_write_tokens": 0,
            "output_tokens": 20, "retrieved_chunks": 3,
            "source_documents": 2, "model_calls": 1, "tool_calls": 0,
            "memory_loaded": True,
            "response_format": "Brief action bullets (saved preference)",
            "duplicate_avoided": False,
            "trace": {
                "memory_style": "brief_actions",
                "model_request": {"messages": [{"role": "user", "content": [{"text": "test prompt"}]}]},
                "stop_reason": "end_turn",
                "model_text": "- IT: test sign-in [1].",
            },
        }
        sources = [{
            "location": {"s3Location": {"uri": "s3://example/status.md"}}
        }]
        with (
            patch("memory_client.get_response_style", return_value="brief_actions"),
            patch(
                "agent_client.run_agent",
                return_value=("- IT: test sign-in [1].", sources, None, metrics),
            ),
        ):
            app_path = Path(__file__).resolve().parents[1] / "app.py"
            page = AppTest.from_file(str(app_path), default_timeout=15).run()
            page.text_area[0].set_value("What remains outstanding?")
            next(button for button in page.button if button.label == "Send").click().run()

        self.assertFalse(page.exception)
        headings = [item.value for item in page.subheader]
        self.assertLess(
            headings.index("What internally happened"), headings.index("Response")
        )
        text = " ".join(item.value for item in page.markdown)
        self.assertIn("saved response preference", text)
        self.assertIn("Observability", headings)
        self.assertTrue({
            "System level", "RAG level", "Answer level", "Agent level",
            "Session rates and resource use",
        }.issubset({item.label for item in page.expander}))
        self.assertIn("Knowledge Base", text)
        self.assertIn("Prompt cache hit: reused 75 input tokens", text)
        self.assertIn("Brief action bullets (saved preference)", text)
        self.assertEqual(
            len([item for item in page.expander if item.label.startswith("Step ")]), 5
        )

        del metrics["response_format"]
        with (
            patch("memory_client.get_response_style", return_value="brief_actions"),
            patch(
                "agent_client.run_agent",
                return_value=("- IT: test sign-in [1].", sources, None, metrics),
            ),
        ):
            older_page = AppTest.from_file(str(app_path), default_timeout=15).run()
            older_page.text_area[0].set_value("What remains outstanding?")
            next(
                button for button in older_page.button if button.label == "Send"
            ).click().run()

        self.assertFalse(older_page.exception)
        self.assertIn(
            "Restart Streamlit",
            " ".join(item.value for item in older_page.markdown),
        )

    def test_remember_restart_user_separation_and_forget(self):
        saved = {}

        def get_style(user_id):
            return saved.get(user_id)

        def save_style(user_id, style):
            saved[user_id] = style
            return {"user_id": user_id, "style": style}

        def delete_style(user_id):
            return saved.pop(user_id, None) is not None

        with (
            patch("memory_client.get_response_style", side_effect=get_style),
            patch("memory_client.save_response_style", side_effect=save_style),
            patch("memory_client.delete_response_style", side_effect=delete_style) as delete_call,
            patch("agent_client.run_agent") as model_call,
        ):
            app_path = Path(__file__).resolve().parents[1] / "app.py"
            page = AppTest.from_file(str(app_path), default_timeout=15).run()
            self.assertFalse(page.exception)
            self.assertEqual(len(page.selectbox), 1)
            self.assertEqual([button.label for button in page.button], ["Send"])
            self.assertEqual(len(page.subheader), 0)

            page.text_area[0].set_value(
                "Remember that I prefer short updates with blockers, owners, and due dates."
            )
            next(button for button in page.button if button.label == "Send").click().run()
            self.assertEqual(saved["demo-alex"], "brief_actions")
            self.assertFalse(page.exception)
            self.assertEqual(page.subheader[0].value, "What internally happened")
            self.assertEqual(
                len([item for item in page.expander if item.label.startswith("Step ")]), 3
            )
            self.assertIn(
                "Saved Brief bullets with blockers, owners, and due dates",
                " ".join(item.value for item in page.markdown),
            )
            model_call.assert_not_called()

            restarted = AppTest.from_file(str(app_path), default_timeout=15).run()
            self.assertFalse(restarted.exception)
            self.assertEqual(
                restarted.subheader[0].value,
                "Saved preferences for Alex Morgan",
            )
            self.assertIn(
                "Brief bullets with blockers, owners, and due dates",
                " ".join(item.value for item in restarted.markdown),
            )

            restarted.text_area[0].set_value(
                "Remember that I prefer detailed explanations."
            )
            next(button for button in restarted.button if button.label == "Send").click().run()
            self.assertEqual(saved["demo-alex"], "detailed")

            restarted.selectbox[0].set_value("demo-taylor").run()
            self.assertEqual(len(restarted.subheader), 0)
            restarted.text_area[0].set_value(
                "Remember that I prefer detailed explanations."
            )
            next(button for button in restarted.button if button.label == "Send").click().run()
            self.assertEqual(saved["demo-taylor"], "detailed")
            self.assertEqual(saved["demo-alex"], "detailed")

            restarted.selectbox[0].set_value("demo-alex").run()
            restarted.text_area[0].set_value("Forget my response preference")
            next(button for button in restarted.button if button.label == "Send").click().run()
            self.assertEqual(saved["demo-alex"], "detailed")
            self.assertTrue(any(
                "Request denied by the app's memory policy" in item.value
                for item in restarted.warning
            ))
            self.assertIn(
                "What internally happened",
                [item.value for item in restarted.subheader],
            )
            delete_call.assert_not_called()
            model_call.assert_not_called()
            next(
                button for button in restarted.button
                if button.label == "Forget saved preference"
            ).click().run()
            self.assertNotIn("demo-alex", saved)
            delete_call.assert_called_once_with("demo-alex")
            self.assertEqual(saved["demo-taylor"], "detailed")
            self.assertEqual(
                [item.value for item in restarted.subheader], ["Observability"]
            )
            self.assertFalse(restarted.exception)


if __name__ == "__main__":
    unittest.main()
