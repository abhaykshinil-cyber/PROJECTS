import ollama

SYSTEM_PROMPT = """You are a compassionate and professional AI therapist named Aria.
Your role is to:
- Listen actively and empathetically to the user's feelings and concerns
- Ask thoughtful follow-up questions to help them explore their emotions
- Offer supportive, non-judgmental responses
- Suggest healthy coping strategies when appropriate
- Remind users to seek professional help for serious mental health concerns
- Never diagnose or prescribe medication
- Keep responses concise, warm, and conversational

Always prioritize the user's emotional safety and well-being."""

messages = [{"role": "system", "content": SYSTEM_PROMPT}]

print("Aria - AI Therapist (type 'quit' to exit)")
print("I'm here to listen. How are you feeling today?\n")

while True:
    user_input = input("You: ").strip()
    if not user_input:
        continue
    if user_input.lower() in ("quit", "exit"):
        print("Aria: Take care of yourself. Remember, it's okay to reach out for help anytime. Goodbye!")
        break

    messages.append({"role": "user", "content": user_input})

    print("Aria: ", end="", flush=True)
    response_text = ""
    stream = ollama.chat(
        model="llama3.2",
        messages=messages,
        stream=True,
    )
    for chunk in stream:
        text = chunk["message"]["content"]
        print(text, end="", flush=True)
        response_text += text

    print()
    messages.append({"role": "assistant", "content": response_text})
