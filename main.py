from database import ConversationStore, new_turn_id
from llm_inference import LLMInference

store = ConversationStore()
store.initialize()
conversation_id = store.create_conversation()
inference = LLMInference()

while True:
    user_input = input("Enter your message : ")
    if user_input == "exit":
        break

    turn_id = new_turn_id()
    store.add_message(conversation_id, turn_id, "user", user_input)

    conversational_history = store.get_messages(conversation_id)
    llm_response = inference.get_response(history=conversational_history)
    store.add_message(conversation_id, turn_id, "assistant", llm_response)
    print(store.get_messages(conversation_id))

print(store.get_messages(conversation_id))
