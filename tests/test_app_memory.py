import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class MemoryPageTests(unittest.TestCase):
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
            patch("memory_client.delete_response_style", side_effect=delete_style),
            patch("agent_client.run_agent") as model_call,
        ):
            app_path = Path(__file__).resolve().parents[1] / "app.py"
            page = AppTest.from_file(str(app_path), default_timeout=15).run()
            self.assertFalse(page.exception)

            page.text_area[0].set_value(
                "Remember that I prefer short updates with blockers, owners, and due dates."
            )
            page.button[2].click().run()
            self.assertEqual(saved["demo-alex"], "brief_actions")
            self.assertFalse(page.exception)
            model_call.assert_not_called()

            restarted = AppTest.from_file(str(app_path), default_timeout=15).run()
            self.assertFalse(restarted.exception)
            self.assertIn(
                "Brief bullets with blockers, owners, and due dates",
                " ".join(item.value for item in restarted.markdown),
            )

            restarted.text_area[0].set_value(
                "Remember that I prefer detailed explanations."
            )
            restarted.button[2].click().run()
            self.assertEqual(saved["demo-alex"], "detailed")
            self.assertEqual(restarted.selectbox[1].value, "detailed")

            restarted.selectbox[0].set_value("demo-taylor").run()
            self.assertIn(
                "Currently remembered:** Nothing",
                " ".join(item.value for item in restarted.markdown),
            )
            restarted.selectbox[1].set_value("detailed")
            restarted.button[0].click().run()
            self.assertEqual(saved["demo-taylor"], "detailed")
            self.assertEqual(saved["demo-alex"], "detailed")

            restarted.selectbox[0].set_value("demo-alex").run()
            restarted.button[1].click().run()
            self.assertNotIn("demo-alex", saved)
            self.assertEqual(saved["demo-taylor"], "detailed")
            self.assertFalse(restarted.exception)


if __name__ == "__main__":
    unittest.main()
