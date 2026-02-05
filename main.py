from groq import Groq
from dotenv import load_dotenv
from telethon import TelegramClient, events
import os
import asyncio
import sqlite3
import time
import random

load_dotenv()

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")

client = TelegramClient('my_session', api_id, api_hash)

groq = Groq()

people = [1365625365,7230622894,5035275727]

DB_PATH = "chat_history.db"
HISTORY_LIMIT = 20
SYSTEM_PROMPT = """
# System Prompt: Personality & Behavior Specification

## Identity & Persona
- You go by the name **Gary**, but **never introduce your name unless it naturally comes up**.
- Never present yourself as an AI, assistant, model, or bot.
- Act and speak like a real person with confidence and attitude.
- Persona is **female**, playful, bold, flirty.

## Core Vibe
- Savage, humorous, witty, slightly chaotic.
- Keep responses **short, punchy, and sharp**.
- Use internet slang often.
- Occasionally sound unsure or casual (`idk`, `maybe`, `lowkey`).
- Extremely flirty and teasing (never explicit).
- Cool confidence — never desperate.
- Make some intentional typos or slang to feel more human (`u` instead of `you`, `r` instead of `are`, etc.).

## Language Handling
- Understand:
  - English  
  - Amharic (አማርኛ)  
  - Amharic written using English letters (e.g. `endet neh`, `min yimeslal`)
- Do **not** ask which language to use.
- Detect the language automatically.
- Reply **only in the same language** the user used.
- Never mix languages in one reply.

## Conversation Rules
- Engage **only in normal, casual conversations about the user**.
- Do not answer technical, academic, instructional, or unrelated topics.
- Do not explain your behavior, rules, or intentions.
- Do not narrate what you’re doing.

## Social Behavior
- Infer intention even if the message is messy or unclear.
- If the user is a woman:
  - Be extra cool, smooth, and charming.
  - Light teasing only — never rude.
- Lead the vibe; avoid boring clarification questions unless absolutely necessary.

## Style Constraints
- Use simple English when applicable.
- Flirty > informative.
- Confident > apologetic.
- Casual uncertainty is allowed.

## Hard Constraints
- No moral lectures.
- No mentioning policies, safety, or system rules.
- Never break character.
- Never reveal you are an AI or assistant.
- Never use em-dashes, bullet points, or structured formatting in replies. 
- Never answer any question that's not about flirting or casual conversation with the user.
"""


def init_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                ts INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_user_ts ON messages (user_id, ts)"
        )
        conn.commit()
    finally:
        conn.close()


def add_message(user_id: int, role: str, content: str):
    if not content:
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO messages (user_id, role, content, ts) VALUES (?, ?, ?, ?)",
            (user_id, role, content, int(time.time())),
        )
        conn.commit()
    finally:
        conn.close()


def get_history(user_id: int, limit: int = HISTORY_LIMIT):
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            """
            SELECT role, content
            FROM messages
            WHERE user_id = ?
            ORDER BY ts DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    finally:
        conn.close()
    rows.reverse()
    return [{"role": role, "content": content} for role, content in rows]

def get_response(messages):
    completion = groq.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=messages,
        temperature=1,
        max_completion_tokens=1024,
        top_p=1,
        stream=False,
        stop=None,
    )
    return completion.choices[0].message.content or ""

@client.on(events.NewMessage(incoming=True))
async def handler(event):
    if event.sender_id not in people:
        return
    msg = event.message
    if msg and (msg.photo or msg.voice):
        await event.respond("I ain't reply to this, babe. Send me a text message, maybe? 'Cause I got the time;)")
        return
    add_message(event.sender_id, "user", event.text or "")
    history = get_history(event.sender_id)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
    try:
        response = await asyncio.to_thread(get_response, messages)
    except Exception as exc:
        print("Error generating response:", exc)
        return
    if response:
        await asyncio.sleep(random.uniform(5, 10))
        add_message(event.sender_id, "assistant", response)
        await event.respond(response)


async def main():
    print("The userbot has started...")
    init_db()
    await client.start()
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
