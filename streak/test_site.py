
import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta


_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["STREAK_DB"] = _tmp.name
os.environ["SECRET_KEY"] = "test-secret-key" 

import app as app_module  
from logic import (  
    Habit, best_habit_streak, completion_counts, decorations, global_streak, habit_streak,
    heatmap, is_wilting, level_title, longest_streak, month_grid, percent, plant_stage,
    plural, unlocked_achievements, xp_info,
)
from plants import SPECIES, plant_svg  

TODAY = date(2026, 10, 14)  
ALL_DAYS = {0, 1, 2, 3, 4, 5, 6}


def days_ago(n):
    return TODAY - timedelta(days=n)


def make_habit(days=None, created_ago=30):
    return Habit(1, "Тест", "#4caf50", days if days is not None else ALL_DAYS, days_ago(created_ago))


#расчеты

class StreakTests(unittest.TestCase):
    def test_daily_streak(self):
        self.assertEqual(habit_streak(make_habit(), {days_ago(i) for i in range(5)}, TODAY), 5)

    def test_today_not_done_does_not_break_streak(self):
        self.assertEqual(habit_streak(make_habit(), {days_ago(i) for i in range(1, 4)}, TODAY), 3)

    def test_gap_breaks_streak(self):
        self.assertEqual(habit_streak(make_habit(), {days_ago(0), days_ago(1), days_ago(3)}, TODAY), 2)

    def test_unscheduled_days_do_not_break_streak(self):
        habit = make_habit(days={0, 2, 4})  
        done = {date(2026, 10, 14), date(2026, 10, 12), date(2026, 10, 9)}
        self.assertEqual(habit_streak(habit, done, TODAY), 3)

    def test_best_streak_is_the_longest_run(self):
        done = {days_ago(i) for i in (0, 1, 2, 10, 11, 12, 13, 14)}  
        self.assertEqual(best_habit_streak(make_habit(), done, TODAY), 5)
        self.assertEqual(best_habit_streak(make_habit(), set(), TODAY), 0)

    def test_global_and_longest_streak(self):
        days = {days_ago(0), days_ago(1), days_ago(2), days_ago(10), days_ago(11)}
        self.assertEqual(global_streak(days, TODAY), 3)
        self.assertEqual(longest_streak(days), 3)
        self.assertEqual(longest_streak(set()), 0)


class PercentTests(unittest.TestCase):
    def test_five_of_seven_is_71(self):
        completed, planned = completion_counts(make_habit(), {days_ago(i) for i in range(5)}, TODAY, 7)
        self.assertEqual((completed, planned, percent(completed, planned)), (5, 7, 71))

    def test_unscheduled_day_is_not_a_fail(self):
        habit = make_habit(days={0, 2, 4})
        done = {date(2026, 10, 14), date(2026, 10, 12), date(2026, 10, 9)}
        self.assertEqual(completion_counts(habit, done, TODAY, 7), (3, 3))

    def test_no_plans_gives_zero(self):
        self.assertEqual(percent(0, 0), 0)


class GrowthTests(unittest.TestCase):
    def test_six_stages(self):
        names = [plant_stage(n)["name"] for n in (0, 2, 5, 10, 20, 40)]
        self.assertEqual(names, ["Семя", "Росток", "Побег", "Бутон", "Цветение", "Расцвет"])
        last = plant_stage(500)
        self.assertEqual((last["index"], last["next_at"], last["progress"]), (5, None, 100))

    def test_wilting(self):
        habit = make_habit()
        self.assertTrue(is_wilting(habit, set(), TODAY))
        self.assertFalse(is_wilting(habit, {days_ago(1)}, TODAY))
        self.assertFalse(is_wilting(make_habit(created_ago=2), set(), TODAY))
        self.assertEqual(plant_stage(5, wilting=True)["icon"], "🥀")

    def test_xp_level_title_and_decorations(self):
        self.assertEqual((xp_info(0)["level"], xp_info(0)["title"]), (1, "Семечко"))
        info = xp_info(25)
        self.assertEqual((info["xp"], info["level"], info["xp_into"]), (250, 3, 50))
        self.assertEqual(level_title(999), "Древо жизни")
        unlocked = [d["key"] for d in decorations(3) if d["unlocked"]]
        self.assertEqual(unlocked, ["butterfly", "bee"])

    def test_achievement_progress(self):
        items = {a["id"]: a for a in unlocked_achievements({"total_done": 10})}
        self.assertTrue(items["ten"]["unlocked"])
        self.assertFalse(items["fifty"]["unlocked"])
        self.assertEqual((items["fifty"]["value"], items["fifty"]["progress"]), (10, 20))

    def test_plural(self):
        forms = ("день", "дня", "дней")
        self.assertEqual([plural(n, forms) for n in (1, 2, 5, 11, 21, 22, 25)],
                         ["день", "дня", "дней", "дней", "день", "дня", "дней"])


class CalendarTests(unittest.TestCase):
    def test_month_grid_states(self):
        grid = month_grid(2026, 10, [make_habit(created_ago=60)], {1: {days_ago(1)}}, TODAY)
        cells = {c["date"]: c["state"] for week in grid for c in week}
        self.assertEqual(cells[days_ago(1)], "full")
        self.assertEqual(cells[days_ago(2)], "empty")
        self.assertEqual(cells[date(2026, 10, 20)], "future")
        self.assertEqual(cells[date(2026, 9, 30)], "out")

    def test_heatmap_shape(self):
        heat = heatmap([make_habit(created_ago=60)], {1: {TODAY}}, TODAY)
        self.assertEqual(len(heat["columns"]), 26)
        self.assertTrue(all(len(col) == 7 for col in heat["columns"]))
        cells = {c["date"]: c["cls"] for col in heat["columns"] for c in col}
        self.assertEqual(cells[TODAY], "l4")            
        self.assertEqual(cells[days_ago(1)], "l0")       
        self.assertEqual(cells[date(2026, 10, 18)], "future")


class PlantDrawingTests(unittest.TestCase):
    def test_every_species_and_stage_renders(self):
        for key in SPECIES:
            for stage in range(6):
                svg = str(plant_svg(key, stage, "#e53935"))
                self.assertTrue(svg.startswith("<svg"), (key, stage))
                self.assertIn("--hc:#e53935", svg)

    def test_wilting_class_unknown_species_and_stage_clamp(self):
        self.assertIn("wilt", str(plant_svg("tree", 3, "#e53935", wilting=True)))
        self.assertIn("<svg", str(plant_svg("не-существует", 99, "#e53935")))

    def test_color_is_escaped(self):
        self.assertNotIn('"><script>', str(plant_svg("rose", 4, '"><script>alert(1)</script>')))

    def test_no_color_means_inherit(self):
        self.assertNotIn("--hc", str(plant_svg("rose", 4, None)))


#сайт: страницы, аккаунты

class WebTests(unittest.TestCase):
    def setUp(self):
        with app_module.app.app_context():
            db = app_module.get_db()
            for table in ("completions", "habits", "users"):
                db.execute(f"DELETE FROM {table}")
            db.execute("DELETE FROM sqlite_sequence")
            db.commit()
        app_module.FAILED_LOGINS.clear()
        app_module.today = lambda: TODAY
        self.client = app_module.app.test_client()

    #помощники

    def token(self, client):
        with client.session_transaction() as s:
            return s.get("csrf")

    def post(self, url, data=None, client=None, with_token=True):
        client = client or self.client
        if self.token(client) is None:
            client.get("/login")
        if self.token(client) is None:
            client.get("/")
        data = dict(data or {})
        if with_token:
            data["csrf"] = self.token(client)
        return client.post(url, data=data)

    def register(self, username="egor", password="parol12345", client=None, **extra):
        return self.post("/register", {"username": username, "password": password,
                                       "password2": password, **extra}, client)

    def add(self, name="Читать", client=None, **extra):
        data = {"name": name, "color": "#2196f3", "species": "tulip", "days": list("0123456")}
        data.update(extra)
        return self.post("/habit/add", data, client)

    def page(self, url, client=None):
        return (client or self.client).get(url).get_data(as_text=True)

    def db_one(self, sql, args=()):
        with app_module.app.app_context():
            return app_module.get_db().execute(sql, args).fetchone()

    #гости, вход, CSRF

    def test_guest_sees_landing_and_private_pages_redirect(self):
        self.assertIn("Создать аккаунт", self.page("/"))
        for url in ("/stats", "/garden", "/achievements", "/account", "/export.csv", "/day/2026-10-13", "/habit/1/edit"):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn("/login", r.headers["Location"])

    def test_register_login_logout_and_throttle(self):
        self.assertEqual(self.register().status_code, 302)
        self.assertIn("egor", self.page("/"))
        self.post("/logout")
        bad = self.post("/login", {"username": "egor", "password": "неверный"})
        self.assertIn("Неверный логин или пароль", bad.get_data(as_text=True))
        self.assertEqual(self.post("/login", {"username": "EGOR", "password": "parol12345"}).status_code, 302)
        self.post("/logout")
        for _ in range(5):
            self.post("/login", {"username": "egor", "password": "wrong-password"})
        self.assertEqual(self.post("/login", {"username": "egor", "password": "parol12345"}).status_code, 429)

    def test_register_validation_and_duplicates(self):
        for kwargs, text in [(dict(password="short"), "не короче 8"),
                             (dict(username="ab"), "Логин:"), (dict(username="<b>x</b>"), "Логин:")]:
            self.assertIn(text, self.register(**kwargs).get_data(as_text=True))
        self.register("Egor")
        other = app_module.app.test_client()
        self.assertIn("уже занят", self.register("egor", client=other).get_data(as_text=True))

    def test_password_stored_hashed(self):
        self.register(password="parol12345")
        stored = self.db_one("SELECT password_hash FROM users")[0]
        self.assertNotIn("parol12345", stored)

    def test_post_without_csrf_is_rejected(self):
        self.register()
        self.client.get("/")
        self.assertEqual(self.post("/habit/add", {"name": "Взлом"}, with_token=False).status_code, 400)

    #изоляция данных

    def test_users_cannot_touch_each_others_habits(self):
        alice, bob = self.client, app_module.app.test_client()
        self.register("alice", client=alice)
        self.add("Секрет Алисы", client=alice)
        self.post("/habit/1/toggle", client=alice)
        self.register("bob", client=bob)
        self.assertNotIn("Секрет Алисы", self.page("/garden", bob))
        for url in ("/habit/1/toggle", "/habit/1/delete"):
            self.assertEqual(self.post(url, client=bob).status_code, 404, url)
        self.assertEqual(self.post("/habit/1/edit", {"name": "Взлом"}, client=bob).status_code, 404)
        self.assertEqual(bob.get("/habit/1/edit").status_code, 404)
        self.assertIn("Секрет Алисы", self.page("/garden", alice))

    #привычки: вид растения, цвет, проверка форм

    def test_species_and_color_are_validated(self):
        self.register()
        self.add("Роза", species="rose", color="#ABCDEF")
        self.add("Взлом", species="evil<script>", color="javascript:x")
        rows = self.db_one("SELECT group_concat(species), group_concat(color) FROM habits")
        self.assertEqual(rows[0], "rose,sunflower")
        self.assertEqual(rows[1], "#abcdef,#fdd835")

    def test_names_are_escaped_and_limit_of_habits(self):
        self.register()
        self.add("<script>alert(1)</script>")
        self.assertNotIn("<script>alert(1)</script>", self.page("/") + self.page("/garden"))
        for i in range(app_module.MAX_HABITS + 2):
            self.add(f"П{i}")
        self.assertEqual(self.db_one("SELECT COUNT(*) FROM habits")[0], app_module.MAX_HABITS)

    def test_all_pages_open_empty_and_filled(self):
        self.register()
        urls = ("/", "/stats", "/garden", "/achievements", "/account", "/export.csv", "/day/2026-10-13",
                "/stats?year=2026&month=2", "/stats?year=abc&month=99")
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.add()
        self.post("/habit/1/toggle")
        for url in urls + ("/habit/1/edit",):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_toggle_edit_delete(self):
        self.register()
        self.add()
        self.post("/habit/1/toggle")
        self.assertIn("1/1", self.page("/"))
        self.post("/habit/1/toggle")
        self.assertIn("0/1", self.page("/"))
        self.post("/habit/1/edit", {"name": "Читать книгу", "color": "#ff0000", "species": "cactus", "days": ["0", "2"]})
        self.assertIn("Читать книгу", self.page("/garden"))
        self.post("/habit/1/toggle")
        self.post("/habit/1/delete")
        self.assertEqual(self.db_one("SELECT COUNT(*) FROM completions")[0], 0)

    #отметки за прошлые дни

    def test_backfill_moves_creation_date_back(self):
        self.register()
        self.add()
        d = days_ago(3).isoformat()
        self.assertEqual(self.post("/habit/1/toggle", {"day": d, "back": "day"}).status_code, 302)
        self.assertIsNotNone(self.db_one("SELECT 1 FROM completions WHERE day = ?", (d,)))
        self.assertEqual(self.db_one("SELECT created FROM habits")[0], d)
        self.post("/habit/1/toggle", {"day": d})                      # повторное нажатие снимает отметку
        self.assertIsNone(self.db_one("SELECT 1 FROM completions WHERE day = ?", (d,)))

    def test_backfill_limits(self):
        self.register()
        self.add()
        for bad in ((TODAY + timedelta(days=1)).isoformat(), (TODAY - timedelta(days=400)).isoformat(), "вчера", "2026-13-40"):
            self.assertEqual(self.post("/habit/1/toggle", {"day": bad}).status_code, 400, bad)
        for url, code in (("/day/2026-10-15", 404), ("/day/2025-01-01", 404), ("/day/abc", 404), ("/day/2026-10-14", 200)):
            self.assertEqual(self.client.get(url).status_code, code, url)

    #аккаунт

    def test_change_password(self):
        self.register()
        self.post("/account/password", {"old": "неверный", "password": "novyj-parol1", "password2": "novyj-parol1"})
        self.assertIn("Текущий пароль неверный", self.page("/account"))
        self.post("/account/password", {"old": "parol12345", "password": "novyj-parol1", "password2": "novyj-parol1"})
        self.post("/logout")
        self.assertEqual(self.post("/login", {"username": "egor", "password": "parol12345"}).status_code, 200)
        self.assertEqual(self.post("/login", {"username": "egor", "password": "novyj-parol1"}).status_code, 302)

    def test_delete_account_needs_password_and_removes_everything(self):
        self.register()
        self.add()
        self.post("/habit/1/toggle")
        self.post("/account/delete", {"password": "не тот"})
        self.assertEqual(self.db_one("SELECT COUNT(*) FROM users")[0], 1)
        self.post("/account/delete", {"password": "parol12345"})
        for table in ("users", "habits", "completions"):
            self.assertEqual(self.db_one(f"SELECT COUNT(*) FROM {table}")[0], 0, table)
        self.assertEqual(self.client.get("/stats").status_code, 302)

    def test_timezone(self):
        self.register(tz="Asia/Vladivostok")
        self.assertEqual(self.db_one("SELECT tz FROM users")[0], "Asia/Vladivostok")
        self.post("/account/timezone", {"tz": "../etc/passwd"})
        self.assertEqual(self.db_one("SELECT tz FROM users")[0], "Asia/Vladivostok")
        self.post("/account/timezone", {"tz": "Europe/Moscow"})
        self.assertEqual(self.db_one("SELECT tz FROM users")[0], "Europe/Moscow")
        self.assertIsNone(app_module.valid_tz("Nowhere/City"))
        self.assertIsNone(app_module.valid_tz("x" * 100))

    def test_export_csv_is_safe_for_excel(self):
        self.register()
        self.add("=1+1")
        self.post("/habit/1/toggle")
        r = self.client.get("/export.csv")
        text = r.get_data(as_text=True)
        self.assertIn("text/csv", r.headers["Content-Type"])
        self.assertIn("Дата;Привычка;Растение", text)
        self.assertIn("'=1+1", text)
        self.assertNotIn(";=1+1", text)

    #демо-аккаунт 

    def test_demo_account_is_complete_and_seeding_is_repeatable(self):
        from demo import DEMO_LOGIN, DEMO_PASSWORD, seed
        with app_module.app.app_context():
            self.assertTrue(seed(app_module.get_db(), TODAY))
            self.assertFalse(seed(app_module.get_db(), TODAY))      # второй раз ничего не дублируется
        self.assertEqual(self.db_one("SELECT COUNT(*), COUNT(DISTINCT species) FROM habits")[:], (8, 8))
        self.assertGreater(self.db_one("SELECT COUNT(*) FROM completions")[0], 100)
        self.assertEqual(self.post("/login", {"username": DEMO_LOGIN, "password": DEMO_PASSWORD}).status_code, 302)
        for url in ("/", "/stats", "/garden", "/achievements", "/day/2026-10-13"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertIn("Ур. 16", self.page("/"))

    def test_demo_account_is_protected_when_auto_demo_is_on(self):
        from demo import DEMO_LOGIN, DEMO_PASSWORD, seed
        with app_module.app.app_context():
            seed(app_module.get_db(), TODAY)
        app_module.AUTO_DEMO = True
        try:
            self.assertIn(DEMO_PASSWORD, self.page("/login"))        # подсказка с паролем на странице входа
            self.post("/login", {"username": DEMO_LOGIN, "password": DEMO_PASSWORD})
            self.post("/account/password", {"old": DEMO_PASSWORD, "password": "hacked-pass1", "password2": "hacked-pass1"})
            self.post("/account/delete", {"password": DEMO_PASSWORD})
            self.assertEqual(self.db_one("SELECT COUNT(*) FROM users")[0], 1)
            self.post("/logout")
            self.assertEqual(self.post("/login", {"username": DEMO_LOGIN, "password": DEMO_PASSWORD}).status_code, 302)
        finally:
            app_module.AUTO_DEMO = False

    #обновление старых баз

    def test_old_database_is_migrated(self):
        old = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        old.close()
        con = sqlite3.connect(old.name)
        con.executescript("""
            CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
                                password_hash TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE habits (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT NOT NULL,
                                 color TEXT NOT NULL, weekdays TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE completions (id INTEGER PRIMARY KEY AUTOINCREMENT, habit_id INTEGER NOT NULL,
                                      day TEXT NOT NULL, UNIQUE (habit_id, day));
            INSERT INTO habits (name, color, weekdays, created) VALUES ('Старая', '#4caf50', '0,1', '2026-10-01');
        """)
        con.commit()
        con.close()
        real = app_module.app.config["DATABASE"]
        app_module.app.config["DATABASE"] = old.name
        try:
            with app_module.app.app_context():
                app_module.init_db()
                db = app_module.get_db()
                self.assertIn("species", [r["name"] for r in db.execute("PRAGMA table_info(habits)")])
                self.assertIn("tz", [r["name"] for r in db.execute("PRAGMA table_info(users)")])
                self.assertEqual(db.execute("SELECT species FROM habits").fetchone()[0], "sunflower")
        finally:
            app_module.app.config["DATABASE"] = real
            os.unlink(old.name)


if __name__ == "__main__":
    unittest.main()
