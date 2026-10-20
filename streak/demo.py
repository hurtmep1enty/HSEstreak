
import random
import sqlite3
from datetime import timedelta

from werkzeug.security import generate_password_hash

DEMO_LOGIN = "demo"
DEMO_PASSWORD = "demo12345"


HABITS = [
    ("Читать 20 минут", "tree",      "#e53935", "0,1,2,3,4,5,6", 60, 0.85, 0),
    ("Английский",      "lavender",  "#8e24aa", "0,1,2,3,4,5,6", 45, 0.75, 4),
    ("Спорт",           "cactus",    "#f06292", "0,2,4",         50, 0.90, 0),
    ("Зарядка",         "sunflower", "#fdd835", "0,1,2,3,4,5,6", 20, 0.80, 0),
    ("Вода 2 литра",    "daisy",     "#039be5", "0,1,2,3,4,5,6", 26, 0.90, 0),
    ("Медитация",       "rose",      "#d81b60", "0,1,2,3,4,5,6", 14, 0.85, 0),
    ("Прогулка",        "bamboo",    "#26a69a", "2,5,6",         16, 0.70, 0),
    ("Дневник",         "tulip",     "#fb8c00", "0,1,2,3,4,5,6", 2,  0.50, 0),
]


def seed(db, today):
    if db.execute("SELECT 1 FROM users WHERE username = ?", (DEMO_LOGIN,)).fetchone():
        return False
    rnd = random.Random(2026) 
    try:
        user_id = db.execute(
            "INSERT INTO users (username, password_hash, created, tz) VALUES (?, ?, ?, ?)",
            (DEMO_LOGIN, generate_password_hash(DEMO_PASSWORD), today.isoformat(), "Europe/Moscow"),
        ).lastrowid
    except sqlite3.IntegrityError:  
        return False
    for name, species, color, weekdays, history, chance, gap in HABITS:
        created = today - timedelta(days=history)
        habit_id = db.execute(
            "INSERT INTO habits (user_id, name, color, weekdays, created, species) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, name, color, weekdays, created.isoformat(), species),
        ).lastrowid
        allowed = {int(x) for x in weekdays.split(",")}
        for ago in range(history, 0, -1):      
            d = today - timedelta(days=ago)
            if d.weekday() not in allowed or ago <= gap:
                continue
            if rnd.random() < chance:
                db.execute("INSERT INTO completions (habit_id, day) VALUES (?, ?)", (habit_id, d.isoformat()))
    db.commit()
    return True
