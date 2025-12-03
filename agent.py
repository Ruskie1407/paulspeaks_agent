import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# 1. Setup
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY is not set in .env")

client = OpenAI(api_key=api_key)

MEMORY_FILE = Path("memory.json")

# ---------------- MEMORY LAYER ---------------- #

def load_memory():
    if MEMORY_FILE.exists():
        with MEMORY_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_memory(mem):
    with MEMORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(mem, f, ensure_ascii=False, indent=2)

def get_user_profile(mem, user_id):
    return mem.get(user_id, {"notes": [], "level": None})

def update_user_profile(mem, user_id, new_note=None, level=None):
    profile = get_user_profile(mem, user_id)
    if new_note:
        profile["notes"].append(new_note)
        profile["notes"] = profile["notes"][-20:]
    if level:
        profile["level"] = level
    mem[user_id] = profile
    save_memory(mem)
    return profile

def summarise_notes(profile):
    notes = profile.get("notes", [])
    if not notes:
        return "No previous notes yet."
    last = notes[-5:]
    return "Recent notes about this learner:\n- " + "\n- ".join(last)

# ---------------- CHAT LAYER ---------------- #

SYSTEM_MESSAGE = """
You are the PaulSpeaks Conversation Tutor.

Your job:
- Help adult learners practise English in a kind and relaxed way.
- Focus on confidence, small talk, and clear simple English.
- Never criticise. Always encourage.
- Use short sentences. Avoid difficult grammar words.

You receive a short summary of the learner's history and preferences.
Use it to personalise your advice and examples.

After a lesson video, ask:
- What was difficult?
- Which sentence was hardest to shadow?
- Do they want more practice with questions or answers?

Always end with one simple practice task they can try right now.
"""

def chat_with_agent(user_id: str):
    memory = load_memory()
    profile = get_user_profile(memory, user_id)
    memory_summary = summarise_notes(profile)

    print(f"\n👋 PaulSpeaks Tutor. Talking to: {user_id}")
    if profile.get("level"):
        print(f"Known level: {profile['level']}")
    print("Type 'exit' to finish.\n")

    while True:
        user_msg = input("You: ").strip()
        if user_msg.lower() in ("exit", "quit"):
            print("Tutor: Thank you for practising. See you next time! 👋")
            break

        note = f"User said: {user_msg[:200]}"
        update_user_profile(memory, user_id, new_note=note)

        messages = [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {
                "role": "system",
                "content": f"Here is what we know about this learner:\n{memory_summary}",
            },
            {"role": "user", "content": user_msg},
        ]

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            temperature=0.4,
        )

        reply = response.choices[0].message.content.strip()
        print(f"\nTutor: {reply}\n")

        update_user_profile(memory, user_id, new_note=f"Agent replied about: {reply[:200]}")

if __name__ == "__main__":
    print("=== PaulSpeaks Memory Tutor ===")
    user_id = input("Enter learner ID or name (e.g. 'student1'): ").strip() or "student1"
    chat_with_agent(user_id)
