import os
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from conversation_memory import recent_turns, relevant_episodes, save_turn
from memory_client import extract_personal_facts


class ConversationMemoryTests(unittest.TestCase):
    def test_recent_turns_are_ordered_and_actor_scoped(self):
        client = Mock()
        client.list_events.return_value = {"events": [
            {"eventId": "later", "eventTimestamp": datetime(2026, 10, 25, 2, tzinfo=timezone.utc),
             "payload": [{"conversational": {"role": "ASSISTANT", "content": {"text": "Second"}}}]},
            {"eventId": "earlier", "eventTimestamp": datetime(2026, 10, 25, 1, tzinfo=timezone.utc),
             "payload": [{"conversational": {"role": "USER", "content": {"text": "First"}}}]},
        ]}
        with (patch.dict(os.environ, {"ATLAS_AGENTCORE_MEMORY_ID": "demo-memory"}),
              patch("conversation_memory.boto3.client", return_value=client)):
            turns = recent_turns("demo-alex", "session-one")
        self.assertEqual([turn["text"] for turn in turns], ["First", "Second"])
        self.assertEqual(client.list_events.call_args.kwargs["actorId"], "demo-alex")
        self.assertEqual(client.list_events.call_args.kwargs["sessionId"], "session-one")

    def test_episode_retrieval_uses_actor_namespace(self):
        client = Mock()
        client.retrieve_memory_records.return_value = {"memoryRecordSummaries": [
            {"memoryRecordId": "episode-1", "content": {"text": "Task already existed"}, "score": 0.8}
        ]}
        with (patch.dict(os.environ, {"ATLAS_AGENTCORE_MEMORY_ID": "demo-memory",
                                   "ATLAS_EPISODIC_STRATEGY_ID": "strategy-1"}),
              patch("conversation_memory.boto3.client", return_value=client)):
            episodes = relevant_episodes("demo-taylor", "earlier task")
        self.assertEqual(episodes[0]["text"], "Task already existed")
        self.assertEqual(client.retrieve_memory_records.call_args.kwargs["namespace"],
                         "/strategy/strategy-1/actor/demo-taylor/")

    def test_tool_outcome_is_saved_as_a_tool_event(self):
        client = Mock()
        client.create_event.return_value = {"event": {"eventId": "event-1"}}
        with (patch.dict(os.environ, {"ATLAS_AGENTCORE_MEMORY_ID": "demo-memory"}),
              patch("conversation_memory.boto3.client", return_value=client)):
            self.assertEqual(save_turn("demo-alex", "session-one", "TOOL", "created=false"), "event-1")
        payload = client.create_event.call_args.kwargs["payload"]
        self.assertEqual(payload[0]["conversational"]["role"], "TOOL")


class PersonalFactLearningTests(unittest.TestCase):
    def test_clear_first_person_statement_is_learned(self):
        self.assertEqual(extract_personal_facts(
            "I work on the IT team. What remains outstanding?"), {"team": "IT"})
        self.assertEqual(extract_personal_facts("I'm a pilot volunteer. Can I join?"),
                         {"role": "pilot volunteer"})

    def test_question_about_other_people_is_not_a_personal_fact(self):
        self.assertEqual(extract_personal_facts("Who works on the IT team?"), {})
        self.assertEqual(extract_personal_facts("Is Taylor a pilot volunteer?"), {})


if __name__ == "__main__":
    unittest.main()
