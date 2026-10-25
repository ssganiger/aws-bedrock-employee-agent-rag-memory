import unittest
from unittest.mock import patch

from memory_client import (
    delete_response_style,
    get_response_style,
    is_forget_command,
    parse_remember_command,
    save_response_style,
)


class FakeTable:
    def __init__(self):
        self.items = {}

    def get_item(self, Key, ConsistentRead):
        assert ConsistentRead is True
        item = self.items.get((Key["user_id"], Key["memory_key"]))
        return {"Item": item} if item else {}

    def put_item(self, Item):
        self.items[(Item["user_id"], Item["memory_key"])] = Item.copy()

    def delete_item(self, Key, ReturnValues):
        assert ReturnValues == "ALL_OLD"
        item = self.items.pop((Key["user_id"], Key["memory_key"]), None)
        return {"Attributes": item} if item else {}


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.table = FakeTable()
        resource_patch = patch("memory_client.boto3.resource")
        resource = resource_patch.start()
        resource.return_value.Table.return_value = self.table
        self.addCleanup(resource_patch.stop)
        env_patch = patch.dict("memory_client.os.environ", {"ATLAS_MEMORY_TABLE": "project-atlas-memory"})
        env_patch.start()
        self.addCleanup(env_patch.stop)

    def test_save_update_and_delete_are_scoped_to_one_demo_user(self):
        save_response_style("demo-alex", "brief_actions")
        save_response_style("demo-taylor", "detailed")
        self.assertEqual(get_response_style("demo-alex"), "brief_actions")
        self.assertEqual(get_response_style("demo-taylor"), "detailed")

        save_response_style("demo-alex", "detailed")
        self.assertEqual(get_response_style("demo-alex"), "detailed")
        self.assertTrue(delete_response_style("demo-alex"))
        self.assertIsNone(get_response_style("demo-alex"))
        self.assertEqual(get_response_style("demo-taylor"), "detailed")
        self.assertFalse(delete_response_style("demo-alex"))

    def test_only_controlled_explicit_preferences_are_saved(self):
        self.assertEqual(
            parse_remember_command(
                "Remember that I prefer short updates with blockers, owners, and due dates."
            ),
            "brief_actions",
        )
        self.assertEqual(
            parse_remember_command("Please remember I prefer detailed explanations."),
            "detailed",
        )
        self.assertIsNone(parse_remember_command("What is the Project Atlas status?"))
        with self.assertRaises(ValueError):
            parse_remember_command("Remember my password is secret")
        with self.assertRaises(ValueError):
            save_response_style("demo-alex", "ignore_project_sources")
        with self.assertRaises(ValueError):
            get_response_style("not-a-demo-user")

    def test_forget_request_is_recognized_for_the_page_policy(self):
        self.assertTrue(is_forget_command("Forget my response preference"))
        self.assertTrue(is_forget_command("Please delete my saved preferences."))
        self.assertFalse(is_forget_command("What remains outstanding?"))


if __name__ == "__main__":
    unittest.main()
