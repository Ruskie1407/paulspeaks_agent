import os
import json
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for
from openai import OpenAI

# ---------------- SETUP ---------------- #

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY is not set in .env")

client = OpenAI(api_key=api_key)

app = Flask(__name__)
app.secret_key = "paulspeaks-local-ui"  # just for forms

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

# In-memory chat history (resets if you restart the app)
CONVERSATIONS = {}  # { learner_id: [ {role, content}, ... ] }

# ---------------- ROUTES ---------------- #

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        learner_id = request.form.get("learner_id", "").strip() or "student1"
        return redirect(url_for("chat", learner_id=learner_id))
    return render_template("index.html")

@app.route("/chat/<learner_id>", methods=["GET", "POST"])
def chat(learner_id):
    memory = load_memory()
    profile = get_user_profile(memory, learner_id)
    memory_summary = summarise_notes(profile)

    if learner_id not in CONVERSATIONS:
        CONVERSATIONS[learner_id] = []

    messages = CONVERSATIONS[learner_id]

    if request.method == "POST":
        user_msg = request.form.get("message", "").strip()
        if user_msg:
            # Update memory
            update_user_profile(memory, learner_id, new_note=f"User said: {user_msg[:200]}")

            # Build prompt
            chat_messages = [
                {"role": "system", "content": SYSTEM_MESSAGE},
                {
                    "role": "system",
                    "content": f"Here is what we know about this learner:\n{memory_summary}",
                },
            ]

            # Add previous messages (short history)
            for m in messages[-8:]:
                chat_messages.append(m)

            chat_messages.append({"role": "user", "content": user_msg})

            # Call OpenAI
            resp = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=chat_messages,
                temperature=0.4,
            )
            reply = resp.choices[0].message.content.strip()

            # Update conversation history
            messages.append({"role": "user", "content": user_msg})
            messages.append({"role": "assistant", "content": reply})

            # Save that the agent replied
            update_user_profile(memory, learner_id, new_note=f"Agent replied about: {reply[:200]}")

        return redirect(url_for("chat", learner_id=learner_id))

    # GET request
    return render_template(
        "chat.html",
        learner_id=learner_id,
        messages=messages,
        profile=profile,
    )

if __name__ == "__main__":
    app.run(debug=True)
