"""
# Aria - AI Therapist

Aria is a compassionate AI therapist chatbot powered by Ollama and LLaMA 3.2,
designed to provide emotional support and a safe space for users to express their feelings.

## Features
- Empathetic, non-judgmental responses
- Active listening with thoughtful follow-up questions
- Suggests healthy coping strategies
- Warm and conversational tone
- Reminds users to seek professional help when needed

## Requirements
- Python 3.8+
- Ollama installed and running (https://ollama.com)
- LLaMA 3.2 model: run `ollama pull llama3.2`
- Install dependency: `pip install ollama`

## Usage
    python aria_therapist.py

## Disclaimer
Aria is an AI and is NOT a substitute for professional mental health care.
If you are experiencing a mental health crisis, please contact a licensed
therapist or call a crisis helpline.
"""

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
