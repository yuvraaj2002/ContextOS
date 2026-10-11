from database import ConversationStore, new_turn_id
from llm_inference import LLMInference

store = ConversationStore()
store.initialize()
conversation_id = store.create_conversation()


class PersistedMessage(dict[str, str]):
    """Prompt-safe message carrying a database ID outside its JSON payload."""

    def __init__(self, message_id: int, role: str, content: str) -> None:
        super().__init__(role=role, content=content)
        self.message_id = message_id


def mark_evicted_messages_inactive(evicted_messages: list[dict[str, str]]) -> None:
    """Persist the exact records selected for eviction by LLMInference."""
    message_ids = [
        message.message_id
        for message in evicted_messages
        if isinstance(message, PersistedMessage)
    ]
    store.mark_messages_inactive(conversation_id, message_ids)


inference = LLMInference(on_messages_evicted=mark_evicted_messages_inactive)

while True:
    user_input = input("Enter your message : ")
    if user_input == "exit":
        break

    turn_id = new_turn_id()
    store.add_message(conversation_id, turn_id, "user", user_input)

    conversational_history = [
        PersistedMessage(
            message_id=int(message["id"]),
            role=str(message["role"]),
            content=str(message["content"]),
        )
        for message in store.get_active_messages(conversation_id)
    ]
    llm_response = inference.get_response(history=conversational_history)
    store.add_message(conversation_id, turn_id, "assistant", llm_response)
    print(store.get_messages(conversation_id))

print(store.get_messages(conversation_id))
