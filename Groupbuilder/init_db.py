
import sqlite3

conn = sqlite3.connect('users.db')
cur = conn.cursor()

# Benutzer-Tabelle
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
)
""")

# Charakter-Tabelle
cur.execute("""
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    char_name TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
""")

# Eintrags-Tabelle
cur.execute("""
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    character_id INTEGER NOT NULL,
    day TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    spec TEXT NOT NULL,
    keystone TEXT NOT NULL,
    created_date TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (character_id) REFERENCES characters(id)
)
""")

conn.commit()
conn.close()
