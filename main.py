from groq import Groq
from dotenv import load_dotenv
from telethon import TelegramClient, events
import os
import asyncio
import sqlite3
import time

load_dotenv()

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")

client = TelegramClient('my_session', api_id, api_hash)

groq = Groq()

people = [1365625365]

DB_PATH = "chat_history.db"
HISTORY_LIMIT = 20
SYSTEM_PROMPT = "You are a helpful assistant."


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
        model="llama-3.3-70b-versatile",
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
    print("New message received!")
    print("From:", event.sender_id)
    print("Text:", event.text)
    add_message(event.sender_id, "user", event.text or "")
    history = get_history(event.sender_id)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
    response = await asyncio.to_thread(get_response, messages)
    if response:
        add_message(event.sender_id, "assistant", response)
        await event.respond(response)


print("The userbot has started...")
init_db()
with client:
    client.run_until_disconnected()
