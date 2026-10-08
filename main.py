import time
from llm_inference import LLMInference

# Data structure for conversational history
conversational_history = []
inference = LLMInference()



while True:
    user_input = input("Enter your message : ")
    if user_input == "exit":
        break
    # Adding the user message to conversational history
    conversational_history.append({'role': 'user', 'content': user_input, 'time_stamp': time.time()})

    # Adding the assistant message
    llm_response = inference.get_response(history=conversational_history)
    conversational_history.append({'role': 'assistant', 'content': llm_response, 'time_stamp': time.time()})
    print(conversational_history)

# Complete conversational history
print(conversational_history)