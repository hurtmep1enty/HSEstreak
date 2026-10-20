
import csv
import hmac
import io
import os
import re
import secrets
import sqlite3
import time
from datetime import date, datetime, timedelta
from functools import wraps
from zoneinfo import ZoneInfo

from flask import (Flask, Response, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from logic import (
    PALETTE,
    XP_PER_COMPLETION,
    Habit,
    best_habit_streak,
    completion_counts,
    day_progress,
    decorations,
    global_streak,
    greeting,
    habit_streak,
    heatmap,
    is_wilting,
    longest_streak,
    month_grid,
    percent,
    perfect_days,
    plant_stage,
    plural,
    tip_of_the_day,
    unlocked_achievements,
    xp_info,
)
from demo import DEMO_LOGIN, DEMO_PASSWORD, seed as seed_demo_data
from plants import DEFAULT_SPECIES, SPECIES, plant_svg

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_secret_key():
    from_env = os.environ.get("SECRET_KEY")
    if from_env:
        return from_env
    path = os.path.join(BASE_DIR, "secret_key.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(path, "w", encoding="utf-8") as f:
        f.write(key)
    return key


app = Flask(__name__)
app.config["SECRET_KEY"] = load_secret_key()
app.config["DATABASE"] = os.environ.get("STREAK_DB", os.path.join(BASE_DIR, "streak.db"))
app.config["SESSION_COOKIE_HTTPONLY"] = True      
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"     
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("HTTPS") == "1"  
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024      

WEEKDAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
WEEKDAYS_FULL = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
          "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня",
              "июля", "августа", "сентября", "октября", "ноября", "декабря"]
DEFAULT_COLOR = SPECIES[DEFAULT_SPECIES][1]

# Часовые пояса для настроек. Пользователь сам выбирает свой, чтобы «сегодня» менялось в его полночь.
TIMEZONES = [
    ("Europe/Kaliningrad", "Калининград (UTC+2)"),
    ("Europe/Moscow", "Москва, Санкт-Петербург (UTC+3)"),
    ("Europe/Minsk", "Минск (UTC+3)"),
    ("Europe/Samara", "Самара (UTC+4)"),
    ("Asia/Yekaterinburg", "Екатеринбург (UTC+5)"),
    ("Asia/Omsk", "Омск (UTC+6)"),
    ("Asia/Krasnoyarsk", "Красноярск, Новосибирск (UTC+7)"),
    ("Asia/Irkutsk", "Иркутск (UTC+8)"),
    ("Asia/Yakutsk", "Якутск (UTC+9)"),
    ("Asia/Vladivostok", "Владивосток (UTC+10)"),
    ("Asia/Magadan", "Магадан (UTC+11)"),
    ("Asia/Kamchatka", "Камчатка (UTC+12)"),
    ("Europe/Kyiv", "Киев"),
    ("Asia/Almaty", "Алматы"),
    ("Europe/London", "Лондон"),
    ("Europe/Berlin", "Берлин"),
    ("America/New_York", "Нью-Йорк"),
    ("UTC", "UTC"),
]

USERNAME_RE = re.compile(r"[A-Za-z0-9_.\-]{3,30}")
MIN_PASSWORD = 8
MAX_PASSWORD = 128
MAX_HABITS = 30          
BACKFILL_DAYS = 365      

app.jinja_env.filters["plural"] = plural

if os.environ.get("BEHIND_PROXY") == "1":
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)


AUTO_DEMO = os.environ.get("AUTO_DEMO") == "1"


# время и дата

def valid_tz(name):
    """Название часового пояса, если оно настоящее, иначе None."""
    if not name or len(name) > 64 or not re.fullmatch(r"[A-Za-z0-9_+\-/]+", name):
        return None
    try:
        ZoneInfo(name)
    except Exception:  
        return None
    return name


def now_local():
    """Текущее время в часовом поясе вошедшего пользователя (или по часам сервера)."""
    try:
        user = getattr(g, "user", None)
    except RuntimeError:          
        user = None
    name = valid_tz(user["tz"]) if user is not None and user["tz"] else None
    return datetime.now(ZoneInfo(name)) if name else datetime.now()


def today():
    """Сегодняшняя дата (вынесено в функцию, чтобы её можно было подменить в тестах)."""
    return now_local().date()


#база

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT NOT NULL UNIQUE COLLATE NOCASE,  -- без учёта регистра: Egor = egor
            password_hash TEXT NOT NULL,                        -- хеш, сам пароль нигде не хранится
            created       TEXT NOT NULL,
            tz            TEXT                                  -- часовой пояс, например Europe/Moscow
        );
        CREATE TABLE IF NOT EXISTS habits (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id  INTEGER,                -- владелец привычки
            name     TEXT NOT NULL,
            color    TEXT NOT NULL,
            weekdays TEXT NOT NULL,          -- например "0,2,4" = Пн, Ср, Пт
            created  TEXT NOT NULL,          -- дата создания, ГГГГ-ММ-ДД
            species  TEXT NOT NULL DEFAULT 'sunflower'   -- вид растения
        );
        CREATE TABLE IF NOT EXISTS completions (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id INTEGER NOT NULL,
            day      TEXT NOT NULL,          -- дата выполнения, ГГГГ-ММ-ДД
            UNIQUE (habit_id, day)           -- одну привычку нельзя отметить дважды за день
        );
        """
    )
    # Миграции: если база создана старой версией, добавляем недостающие столбцы.
    habit_cols = [r["name"] for r in db.execute("PRAGMA table_info(habits)")]
    if "user_id" not in habit_cols:
        db.execute("ALTER TABLE habits ADD COLUMN user_id INTEGER")
    if "species" not in habit_cols:
        db.execute("ALTER TABLE habits ADD COLUMN species TEXT NOT NULL DEFAULT 'sunflower'")
    user_cols = [r["name"] for r in db.execute("PRAGMA table_info(users)")]
    if "tz" not in user_cols:
        db.execute("ALTER TABLE users ADD COLUMN tz TEXT")
    db.execute("CREATE INDEX IF NOT EXISTS idx_habits_user ON habits (user_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_completions_habit ON completions (habit_id, day)")
    db.commit()


def row_to_habit(r):
    return Habit(
        id=r["id"],
        name=r["name"],
        color=r["color"],
        days={int(x) for x in r["weekdays"].split(",") if x != ""},
        created=date.fromisoformat(r["created"]),
        species=r["species"] if r["species"] in SPECIES else DEFAULT_SPECIES,
    )


def load_habits(user_id):
    rows = get_db().execute(
        "SELECT * FROM habits WHERE user_id = ? ORDER BY id", (user_id,)
    ).fetchall()
    return [row_to_habit(r) for r in rows]


def load_done(user_id):
    done = {}
    rows = get_db().execute(
        "SELECT c.habit_id, c.day FROM completions c "
        "JOIN habits h ON h.id = c.habit_id WHERE h.user_id = ?",
        (user_id,),
    )
    for r in rows:
        done.setdefault(r["habit_id"], set()).add(date.fromisoformat(r["day"]))
    return done


def own_habit_or_404(habit_id):
    row = get_db().execute(
        "SELECT * FROM habits WHERE id = ? AND user_id = ?", (habit_id, g.user["id"])
    ).fetchone()
    if row is None:
        abort(404)
    return row


#проверка данных из форм

def clean_color(value):
    if value and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return value.lower()
    return DEFAULT_COLOR


def clean_species(value):
    return value if value in SPECIES else DEFAULT_SPECIES


def clean_days(values):
    days = sorted({int(v) for v in values if v.isdigit() and 0 <= int(v) <= 6})
    if not days:
        days = list(range(7))
    return ",".join(str(d) for d in days)


def parse_day(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


#вход, сессии и защита форм

def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


@app.before_request
def check_csrf():
    if request.method == "POST":
        sent = request.form.get("csrf", "").encode()
        expected = session.get("csrf", "").encode()
        if not expected or not hmac.compare_digest(sent, expected):
            abort(400)


@app.errorhandler(400)
def bad_request(_err):
    return "Сессия устарела или форма неверна. Вернитесь назад, обновите страницу и попробуйте снова.", 400


@app.before_request
def load_user():
    g.user = None
    if request.endpoint == "static":
        return
    user_id = session.get("user_id")
    if user_id is not None:
        g.user = get_db().execute(
            "SELECT id, username, tz, created FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if g.user is None: 
            session.pop("user_id", None)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def start_session(user_id):
    session.clear() 
    session["user_id"] = user_id
    session.permanent = True


# Защита от подбора пароля: не больше 5 неудачных попыток за 5 минут на пару (IP, логин).
FAILED_LOGINS = {}
MAX_FAILS = 5
FAIL_WINDOW = 300
# Хеш-пустышка: пароль проверяется, даже если логина нет, чтобы по времени ответа нельзя было угадать логины.
DUMMY_HASH = generate_password_hash("пустышка")


def too_many_attempts(key):
    now = time.time()
    FAILED_LOGINS[key] = [t for t in FAILED_LOGINS.get(key, []) if now - t < FAIL_WINDOW]
    return len(FAILED_LOGINS[key]) >= MAX_FAILS


def password_problem(password, password2):
    """Текст ошибки, если новый пароль не подходит, иначе None."""
    if len(password) < MIN_PASSWORD:
        return f"Пароль должен быть не короче {MIN_PASSWORD} символов."
    if len(password) > MAX_PASSWORD:
        return "Пароль слишком длинный."
    if password != password2:
        return "Пароли не совпадают."
    return None


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("index"))
    error = None
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not USERNAME_RE.fullmatch(username):
            error = "Логин: от 3 до 30 символов, только латинские буквы, цифры и знаки _ . -"
        else:
            error = password_problem(password, request.form.get("password2", ""))
        if error is None:
            db = get_db()
            try:
                cur = db.execute(
                    "INSERT INTO users (username, password_hash, created, tz) VALUES (?, ?, ?, ?)",
                    (username, generate_password_hash(password), date.today().isoformat(),
                     valid_tz(request.form.get("tz", ""))),
                )
            except sqlite3.IntegrityError:
                error = "Такой логин уже занят."
            else:
                user_id = cur.lastrowid
                db.execute("UPDATE habits SET user_id = ? WHERE user_id IS NULL", (user_id,))
                db.commit()
                start_session(user_id)
                return redirect(url_for("index"))
    return render_template("register.html", error=error, username=username)


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("index"))
    error = None
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        key = (request.remote_addr, username.lower())
        if too_many_attempts(key):
            return render_template(
                "login.html", error="Слишком много попыток. Подождите 5 минут.", username=username
            ), 429
        row = get_db().execute(
            "SELECT id, password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
        password_ok = check_password_hash(row["password_hash"] if row else DUMMY_HASH, password)
        if row and password_ok:
            FAILED_LOGINS.pop(key, None)
            start_session(row["id"])
            return redirect(url_for("index"))
        FAILED_LOGINS.setdefault(key, []).append(time.time())
        error = "Неверный логин или пароль."
    return render_template("login.html", error=error, username=username)


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


#общая сводка

def overall_stats(user_id):
    d = today()
    habits = load_habits(user_id)
    done = load_done(user_id)
    total_done = sum(len(s) for s in done.values())
    all_days = set().union(*done.values()) if done else set()
    xp = xp_info(total_done)
    stages = [
        plant_stage(len(done.get(h.id, set())), is_wilting(h, done.get(h.id, set()), d))["index"]
        for h in habits
    ]
    return {
        "total_done": total_done,
        "habits_count": len(habits),
        "streak": global_streak(all_days, d),
        "longest_streak": longest_streak(all_days),
        "perfect_days": perfect_days(habits, done, d),
        "species_count": len({h.species for h in habits if len(done.get(h.id, ())) >= 3}),
        "level": xp["level"],
        "title": xp["title"],
        "xp": xp["xp"],
        "xp_into": xp["xp_into"],
        "max_stage": max(stages) if stages else 0,
    }


@app.context_processor
def inject_globals():
    user = getattr(g, "user", None)
    return {
        "overall": overall_stats(user["id"]) if user else None,
        "csrf_token": csrf_token,
        "demo_hint": (DEMO_LOGIN, DEMO_PASSWORD) if AUTO_DEMO else None,
        "plant_svg": plant_svg,
        "species_list": SPECIES,
        "palette": PALETTE,
        "weekday_short": WEEKDAYS_SHORT,
        "xp_per": XP_PER_COMPLETION,
        "nav": [("index", "Сегодня", "🏠"), ("stats", "Статистика", "📊"),
                ("garden", "Мой сад", "🌻"), ("achievements", "Награды", "🏆")],
    }


def date_label(d):
    """«Понедельник, 12 октября» (с годом, если это не текущий год)."""
    text = f"{WEEKDAYS_FULL[d.weekday()]}, {d.day} {MONTHS_GEN[d.month - 1]}"
    return text if d.year == today().year else f"{text} {d.year}"


#страницы

@app.route("/")
def index():
    if g.user is None:
        return render_template("landing.html")
    uid = g.user["id"]
    d = today()
    done = load_done(uid)
    items = []
    for h in load_habits(uid):
        h_done = done.get(h.id, set())
        items.append({
            "habit": h,
            "scheduled": h.scheduled_on(d),
            "done": d in h_done,
            "streak": habit_streak(h, h_done, d),
            "stage": plant_stage(len(h_done), is_wilting(h, h_done, d)),
            "wilting": is_wilting(h, h_done, d),
        })
    todays = [i for i in items if i["scheduled"]]
    rest = [i for i in items if not i["scheduled"]]
    done_count = sum(1 for i in todays if i["done"])
    xp_today = done_count * XP_PER_COMPLETION
    xp_max = len(todays) * XP_PER_COMPLETION
    return render_template(
        "index.html",
        greeting=greeting(now_local().hour),
        date_label=date_label(d),
        tip=tip_of_the_day(d),
        todays=todays,
        rest=rest,
        done_count=done_count,
        all_done=bool(todays) and done_count == len(todays),
        xp_today=xp_today,
        xp_max=xp_max,
        xp_pct=percent(xp_today, xp_max),
        can_add=len(items) < MAX_HABITS,
    )


@app.post("/habit/add")
@login_required
def add_habit():
    name = request.form.get("name", "").strip()[:40]
    db = get_db()
    count = db.execute("SELECT COUNT(*) FROM habits WHERE user_id = ?", (g.user["id"],)).fetchone()[0]
    if count >= MAX_HABITS:
        flash(f"Больше {MAX_HABITS} привычек завести нельзя. Удали ненужные.", "error")
    elif name:
        db.execute(
            "INSERT INTO habits (user_id, name, color, weekdays, created, species) VALUES (?, ?, ?, ?, ?, ?)",
            (g.user["id"], name, clean_color(request.form.get("color")),
             clean_days(request.form.getlist("days")), today().isoformat(),
             clean_species(request.form.get("species"))),
        )
        db.commit()
        flash("Семечко посажено! Отмечай привычку каждый день, и оно вырастет.", "ok")
    return redirect(url_for("index"))


@app.route("/habit/<int:habit_id>/edit", methods=["GET", "POST"])
@login_required
def edit_habit(habit_id):
    row = own_habit_or_404(habit_id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:40] or row["name"]
        db = get_db()
        db.execute(
            "UPDATE habits SET name = ?, color = ?, weekdays = ?, species = ? WHERE id = ?",
            (name, clean_color(request.form.get("color")),
             clean_days(request.form.getlist("days")),
             clean_species(request.form.get("species")), habit_id),
        )
        db.commit()
        return redirect(url_for("garden"))
    return render_template("edit.html", habit=row_to_habit(row))


@app.post("/habit/<int:habit_id>/delete")
@login_required
def delete_habit(habit_id):
    own_habit_or_404(habit_id)
    db = get_db()
    db.execute("DELETE FROM completions WHERE habit_id = ?", (habit_id,))
    db.execute("DELETE FROM habits WHERE id = ?", (habit_id,))
    db.commit()
    return redirect(url_for("garden"))


@app.post("/habit/<int:habit_id>/toggle")
@login_required
def toggle(habit_id):
    row = own_habit_or_404(habit_id)
    t = today()
    day = t
    if request.form.get("day"):
        day = parse_day(request.form["day"])
        if day is None or day > t or day < t - timedelta(days=BACKFILL_DAYS):
            abort(400)
    db = get_db()
    exists = db.execute(
        "SELECT 1 FROM completions WHERE habit_id = ? AND day = ?", (habit_id, day.isoformat())
    ).fetchone()
    if exists:
        db.execute("DELETE FROM completions WHERE habit_id = ? AND day = ?", (habit_id, day.isoformat()))
    else:
        db.execute("INSERT INTO completions (habit_id, day) VALUES (?, ?)", (habit_id, day.isoformat()))
        if day < date.fromisoformat(row["created"]):
            db.execute("UPDATE habits SET created = ? WHERE id = ?", (day.isoformat(), habit_id))
    db.commit()
    if request.form.get("back") == "day":
        return redirect(url_for("day_view", day=day.isoformat()))
    return redirect(url_for("index"))


@app.route("/day/<day>")
@login_required
def day_view(day):
    d = parse_day(day)
    t = today()
    first = t - timedelta(days=BACKFILL_DAYS)
    if d is None or d > t or d < first:
        abort(404)
    uid = g.user["id"]
    habits = load_habits(uid)
    done = load_done(uid)
    items = [
        {"habit": h, "done": d in done.get(h.id, set()), "before_created": d < h.created}
        for h in habits if d.weekday() in h.days
    ]
    done_count = sum(1 for i in items if i["done"])
    return render_template(
        "day.html",
        day=d,
        day_iso=d.isoformat(),
        label=date_label(d),
        is_today=(d == t),
        items=items,
        done_count=done_count,
        prev_day=(d - timedelta(days=1)).isoformat() if d > first else None,
        next_day=(d + timedelta(days=1)).isoformat() if d < t else None,
    )


@app.route("/stats")
@login_required
def stats():
    uid = g.user["id"]
    d = today()
    try:
        year = int(request.args.get("year", d.year))
        month = int(request.args.get("month", d.month))
        date(year, month, 1)
    except ValueError:
        year, month = d.year, d.month

    habits = load_habits(uid)
    done = load_done(uid)
    weeks = month_grid(year, month, habits, done, d)

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    rows = []
    sum_done = sum_plan = 0
    for h in habits:
        h_done = done.get(h.id, set())
        w_done, w_plan = completion_counts(h, h_done, d, 7)
        m_done, m_plan = completion_counts(h, h_done, d, 30)
        sum_done += m_done
        sum_plan += m_plan
        rows.append({
            "habit": h,
            "week": percent(w_done, w_plan),
            "month": percent(m_done, m_plan),
            "month_plan": m_plan,
            "streak": habit_streak(h, h_done, d),
            "best": best_habit_streak(h, h_done, d),
            "total": len(h_done),
        })
    candidates = [r for r in rows if r["month_plan"] > 0 and r["month"] < 100]
    worst = min(candidates, key=lambda r: r["month"])["habit"].id if candidates else None

    by_weekday = [0] * 7
    for h_done in done.values():
        for day in h_done:
            by_weekday[day.weekday()] += 1
    best_count = max(by_weekday)

    o = overall_stats(uid)
    tiles = [
        {"icon": "✅", "value": o["total_done"], "label": "отметок всего"},
        {"icon": "🔥", "value": o["longest_streak"], "label": "рекорд серии, дн."},
        {"icon": "✨", "value": o["perfect_days"], "label": "идеальных дней"},
        {"icon": "📈", "value": f"{percent(sum_done, sum_plan)}%", "label": "выполнено за 30 дней"},
    ]

    return render_template(
        "stats.html",
        weeks=weeks,
        today=d,
        heat=heatmap(habits, done, d),
        tiles=tiles,
        month_label=f"{MONTHS[month - 1]} {year}",
        prev={"year": prev_year, "month": prev_month},
        next={"year": next_year, "month": next_month},
        rows=rows,
        worst=worst,
        by_weekday=by_weekday,
        best_count=best_count,
        best_weekday=WEEKDAYS_FULL[by_weekday.index(best_count)] if best_count else None,
    )


@app.route("/garden")
@login_required
def garden():
    uid = g.user["id"]
    d = today()
    done = load_done(uid)
    plants = []
    for h in load_habits(uid):
        h_done = done.get(h.id, set())
        wilting = is_wilting(h, h_done, d)
        plants.append({
            "habit": h,
            "total": len(h_done),
            "streak": habit_streak(h, h_done, d),
            "days_label": ", ".join(WEEKDAYS_SHORT[i] for i in sorted(h.days)) if len(h.days) < 7 else "каждый день",
            "stage": plant_stage(len(h_done), wilting),
            "wilting": wilting,
            "species_name": SPECIES[h.species][0],
        })
    level = overall_stats(uid)["level"]
    decor = decorations(level)
    next_decor = next((x for x in decor if not x["unlocked"]), None)
    return render_template("garden.html", plants=plants, decor=decor, next_decor=next_decor)


@app.route("/achievements")
@login_required
def achievements():
    o = overall_stats(g.user["id"])
    items = unlocked_achievements(o)
    return render_template(
        "achievements.html",
        items=items,
        unlocked=sum(1 for a in items if a["unlocked"]),
        decor=decorations(o["level"]),
    )


#аккаунт
@app.route("/account")
@login_required
def account():
    tz = valid_tz(g.user["tz"]) if g.user["tz"] else None
    zones = list(TIMEZONES)
    if tz and tz not in dict(zones):
        zones.insert(0, (tz, tz))
    return render_template(
        "account.html",
        tz=tz,
        zones=zones,
        member_since=g.user["created"],
        now=now_local().strftime("%H:%M"),
    )


@app.post("/account/timezone")
@login_required
def set_timezone():
    tz = valid_tz(request.form.get("tz", ""))
    if tz is None:
        flash("Такого часового пояса нет.", "error")
    else:
        db = get_db()
        db.execute("UPDATE users SET tz = ? WHERE id = ?", (tz, g.user["id"]))
        db.commit()
        flash("Часовой пояс сохранён.", "ok")
    return redirect(url_for("account"))


def verify_current_password(password):
    key = (request.remote_addr, f"acct:{g.user['id']}")
    if too_many_attempts(key):
        return "Слишком много попыток. Подождите 5 минут."
    row = get_db().execute("SELECT password_hash FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    if not check_password_hash(row["password_hash"], password):
        FAILED_LOGINS.setdefault(key, []).append(time.time())
        return "Текущий пароль неверный."
    FAILED_LOGINS.pop(key, None)
    return None


@app.post("/account/password")
@login_required
def change_password():
    if AUTO_DEMO and g.user["username"] == DEMO_LOGIN:
        flash("В демо-аккаунте это отключено.", "error")
        return redirect(url_for("account"))
    error = verify_current_password(request.form.get("old", ""))
    if error is None:
        error = password_problem(request.form.get("password", ""), request.form.get("password2", ""))
    if error:
        flash(error, "error")
    else:
        db = get_db()
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                   (generate_password_hash(request.form["password"]), g.user["id"]))
        db.commit()
        start_session(g.user["id"])
        flash("Пароль изменён.", "ok")
    return redirect(url_for("account"))


@app.post("/account/delete")
@login_required
def delete_account():
    if AUTO_DEMO and g.user["username"] == DEMO_LOGIN:
        flash("В демо-аккаунте это отключено.", "error")
        return redirect(url_for("account"))
    error = verify_current_password(request.form.get("password", ""))
    if error:
        flash(error, "error")
        return redirect(url_for("account"))
    uid = g.user["id"]
    db = get_db()
    db.execute("DELETE FROM completions WHERE habit_id IN (SELECT id FROM habits WHERE user_id = ?)", (uid,))
    db.execute("DELETE FROM habits WHERE user_id = ?", (uid,))
    db.execute("DELETE FROM users WHERE id = ?", (uid,))
    db.commit()
    session.clear()
    flash("Аккаунт и все данные удалены. Спасибо, что был с нами!", "ok")
    return redirect(url_for("login"))


def safe_cell(text):
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@app.get("/export.csv")
@login_required
def export_csv():
    rows = get_db().execute(
        "SELECT h.name, h.species, c.day FROM completions c JOIN habits h ON h.id = c.habit_id "
        "WHERE h.user_id = ? ORDER BY c.day, h.name", (g.user["id"],)
    ).fetchall()
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(["Дата", "Привычка", "Растение"])
    for r in rows:
        writer.writerow([r["day"], safe_cell(r["name"]), SPECIES.get(r["species"], SPECIES[DEFAULT_SPECIES])[0]])
    return Response("﻿" + out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="streak.csv"'})


with app.app_context():
    init_db()
    if AUTO_DEMO:
        seed_demo_data(get_db(), today())

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
