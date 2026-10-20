
import json
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
    ACHIEVEMENTS, PLANTS, Habit, completion_counts, daily_quote, global_streak, habit_best_streak,
    habit_streak, heatmap, inhabitants, is_wilting, level_title, longest_streak, month_grid,
    on_color, percent, perfect_days, plant_stage, plural, unlocked_achievements, xp_info,
)

TODAY = date(2026, 10, 14) 
ALL_DAYS = {0, 1, 2, 3, 4, 5, 6}


def days_ago(n):
    return TODAY - timedelta(days=n)


def make_habit(days=None, created_ago=30, hid=1):
    return Habit(hid, "Тест", "#4caf50", days if days is not None else ALL_DAYS, days_ago(created_ago))


#расчёты

class StreakTests(unittest.TestCase):
    def test_daily_streak(self):
        done = {days_ago(i) for i in range(5)}  
        self.assertEqual(habit_streak(make_habit(), done, TODAY), 5)

    def test_today_not_done_does_not_break_streak(self):
        done = {days_ago(i) for i in range(1, 4)}  
        self.assertEqual(habit_streak(make_habit(), done, TODAY), 3)

    def test_gap_breaks_streak(self):
        done = {days_ago(0), days_ago(1), days_ago(3)}  
        self.assertEqual(habit_streak(make_habit(), done, TODAY), 2)

    def test_unscheduled_days_do_not_break_streak(self):
        habit = make_habit(days={0, 2, 4})
        done = {date(2026, 10, 14), date(2026, 10, 12), date(2026, 10, 9)} 
        self.assertEqual(habit_streak(habit, done, TODAY), 3)

    def test_new_habit_has_zero_streak(self):
        self.assertEqual(habit_streak(make_habit(created_ago=0), set(), TODAY), 0)

    def test_global_and_longest_streak(self):
        days = {days_ago(0), days_ago(1), days_ago(2), days_ago(10), days_ago(11)}
        self.assertEqual(global_streak(days, TODAY), 3)
        self.assertEqual(longest_streak(days), 3)
        self.assertEqual(longest_streak(set()), 0)

    def test_best_streak(self):
        done = {days_ago(i) for i in (0, 1, 2, 5, 6, 7, 8)}   
        self.assertEqual(habit_best_streak(make_habit(), done, TODAY), 4)

    def test_best_streak_ignores_unfinished_today(self):
        done = {days_ago(1), days_ago(2), days_ago(3)}       
        self.assertEqual(habit_best_streak(make_habit(), done, TODAY), 3)
        self.assertEqual(habit_best_streak(make_habit(), set(), TODAY), 0)


class PercentTests(unittest.TestCase):
    def test_five_of_seven_is_71(self):
        done = {days_ago(i) for i in range(5)}
        completed, planned = completion_counts(make_habit(), done, TODAY, 7)
        self.assertEqual((completed, planned), (5, 7))
        self.assertEqual(percent(completed, planned), 71)

    def test_sunday_miss_is_not_a_fail_for_three_a_week(self):
        habit = make_habit(days={0, 2, 4}) 
        done = {date(2026, 10, 14), date(2026, 10, 12), date(2026, 10, 9)}
        completed, planned = completion_counts(habit, done, TODAY, 7)
        self.assertEqual(planned, 3)
        self.assertEqual(percent(completed, planned), 100)

    def test_no_plans_gives_zero(self):
        self.assertEqual(percent(0, 0), 0)

    def test_perfect_days(self):
        a, b = make_habit(created_ago=5, hid=1), make_habit(created_ago=5, hid=2)
        done = {1: {days_ago(1), days_ago(2), days_ago(3)}, 2: {days_ago(1), days_ago(2)}}
        self.assertEqual(perfect_days([a, b], done, TODAY), 2)          
        self.assertEqual(perfect_days([a], done, TODAY), 0)             
        self.assertEqual(perfect_days([a], done, TODAY, min_planned=1), 3)
        self.assertEqual(perfect_days([], {}, TODAY), 0)


class PlantTests(unittest.TestCase):
    def test_every_species_has_six_stages(self):
        self.assertGreaterEqual(len(PLANTS), 9)
        for key, plant in PLANTS.items():
            self.assertEqual(len(plant["stages"]), 6, key)
            self.assertTrue(plant["title"], key)

    def test_stages(self):
        self.assertEqual(plant_stage(0)["name"], "Жёлудь")
        self.assertEqual(plant_stage(3)["name"], "Росток")
        self.assertEqual(plant_stage(14)["index"], 3)
        self.assertEqual(plant_stage(30, species="rose")["name"], "Роза")
        last = plant_stage(100)
        self.assertEqual((last["name"], last["next_at"], last["progress"], last["index"]), ("Могучий дуб", None, 100, 5))

    def test_progress_to_next_stage(self):
        info = plant_stage(5) 
        self.assertEqual((info["index"], info["next_at"], info["progress"]), (1, 7, 50))

    def test_unknown_species_falls_back_to_oak(self):
        self.assertEqual(plant_stage(0, species="нет такого")["icon"], PLANTS["tree"]["stages"][0][0])

    def test_wilting(self):
        habit = make_habit()
        self.assertTrue(is_wilting(habit, set(), TODAY))
        self.assertFalse(is_wilting(habit, {days_ago(1)}, TODAY))
        self.assertFalse(is_wilting(make_habit(created_ago=2), set(), TODAY))  
        info = plant_stage(5, wilting=True)
        self.assertTrue(info["wilting"])
        self.assertIn("увядает", info["name"])


class MiscTests(unittest.TestCase):
    def test_xp_and_level(self):
        self.assertEqual(xp_info(0)["level"], 1)
        info = xp_info(25)
        self.assertEqual((info["xp"], info["level"], info["xp_into"]), (250, 3, 50))

    def test_level_titles_and_inhabitants(self):
        self.assertEqual([level_title(n) for n in (1, 3, 4, 5, 20)],
                         ["Семечко", "Садовник", "Садовник", "Мастер грядки", "Легенда сада"])
        self.assertEqual([r["unlocked"] for r in inhabitants(1)].count(True), 1)
        self.assertTrue(all(r["unlocked"] for r in inhabitants(10)))

    def test_plural(self):
        forms = ("день", "дня", "дней")
        self.assertEqual([plural(n, forms) for n in (1, 2, 5, 11, 12, 21, 22, 25)],
                         ["день", "дня", "дней", "дней", "дней", "день", "дня", "дней"])

    def test_on_color(self):
        self.assertEqual(on_color("#ffffff"), "#1b1b1b")
        self.assertEqual(on_color("#eab308"), "#1b1b1b") 
        self.assertEqual(on_color("#000000"), "#ffffff")
        self.assertEqual(on_color("не цвет"), "#ffffff")

    def test_quote_is_stable_per_day(self):
        self.assertEqual(daily_quote(TODAY), daily_quote(TODAY))
        self.assertNotEqual(daily_quote(TODAY), daily_quote(TODAY + timedelta(days=1)))

    def test_achievements_keep_saved_ones(self):
        empty = {k: 0 for k in ("total_done", "habits_count", "colors", "species", "longest_streak",
                                "perfect_days", "level", "max_stage", "mood_days")}
        items = {a["id"]: a for a in unlocked_achievements(empty, {"first": days_ago(3)})}
        self.assertTrue(items["first"]["unlocked"])      
        self.assertEqual(items["first"]["day"], days_ago(3))
        self.assertFalse(items["ten"]["unlocked"])
        self.assertEqual(len(items), len(ACHIEVEMENTS))
        self.assertEqual(len({a[0] for a in ACHIEVEMENTS}), len(ACHIEVEMENTS))  

    def test_month_grid_states(self):
        habit = make_habit(created_ago=60)
        grid = month_grid(2026, 10, [habit], {1: {days_ago(1)}}, TODAY)
        cells = {c["date"]: c["state"] for week in grid for c in week}
        self.assertEqual(cells[days_ago(1)], "full")
        self.assertEqual(cells[days_ago(2)], "empty")
        self.assertEqual(cells[date(2026, 10, 20)], "future")
        self.assertEqual(cells[date(2026, 9, 30)], "out")

    def test_heatmap(self):
        habit = make_habit(created_ago=60)
        hm = heatmap([habit], {1: {TODAY, days_ago(1)}}, TODAY, weeks=4)
        self.assertEqual(len(hm["columns"]), 4)
        self.assertTrue(all(len(col) == 7 for col in hm["columns"]))
        last = hm["columns"][-1]
        self.assertEqual(last[2]["level"], 4)             
        self.assertEqual(last[1]["level"], 4)             
        self.assertEqual(last[0]["level"], 0)             
        self.assertIsNone(last[3])                        
        self.assertEqual(hm["months"][0], (0, "сен"))
        old = hm["columns"][0][0]
        self.assertFalse(old["link"])                     
        self.assertTrue(last[2]["link"])


#сайт: страницы, аккаунты

class WebTests(unittest.TestCase):
    def setUp(self):
        with app_module.app.app_context():
            db = app_module.get_db()
            for table in ("completions", "habits", "users", "moods", "user_achievements"):
                db.execute(f"DELETE FROM {table}")
            db.execute("DELETE FROM sqlite_sequence") 
            db.commit()
        app_module.FAILED_LOGINS.clear()
        app_module.today = lambda: TODAY
        self.client = app_module.app.test_client()

    #вспомогательные функции

    def token(self, client):
        with client.session_transaction() as s:
            return s.get("csrf")

    def post(self, url, data=None, client=None, with_token=True):
        """POST с правильным CSRF-токеном (как это делает настоящая форма)."""
        client = client or self.client
        if self.token(client) is None:
            client.get("/login")       
        if self.token(client) is None:
            client.get("/")            
        data = dict(data or {})
        if with_token:
            data["csrf"] = self.token(client)
        return client.post(url, data=data)

    def register(self, username="egor", password="parol12345", password2=None, client=None):
        return self.post("/register", {
            "username": username, "password": password,
            "password2": password if password2 is None else password2,
        }, client)

    def add(self, name="Читать", days=("0", "1", "2", "3", "4", "5", "6"), client=None, **extra):
        data = {"name": name, "color": "#2196f3", "days": list(days)}
        data.update(extra)
        return self.post("/habit/add", data, client)

    def page(self, url, client=None):
        return (client or self.client).get(url).get_data(as_text=True)

    def query(self, sql, args=()):
        with app_module.app.app_context():
            return app_module.get_db().execute(sql, args).fetchall()

    #гости

    def test_guest_sees_landing_and_is_redirected_from_private_pages(self):
        self.assertIn("Создать аккаунт", self.page("/"))
        for url in ("/stats", "/garden", "/achievements", "/habit/1/edit", "/habit/1", "/habit/new",
                    "/settings", "/export.json", "/day/2026-10-13"):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn("/login", r.headers["Location"])
        for url in ("/login", "/register"):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_guest_cannot_post_private_actions(self):
        self.client.get("/login")
        for url in ("/habit/add", "/habit/1/toggle", "/habit/1/delete", "/habit/1/archive",
                    "/day/2026-10-13/mood", "/settings/appearance", "/settings/password",
                    "/settings/delete", "/settings/theme-toggle"):
            r = self.post(url, {"name": "x"})
            self.assertEqual(r.status_code, 302, url)
            self.assertIn("/login", r.headers["Location"])

    #регистрация и вход

    def test_register_login_logout_flow(self):
        self.assertEqual(self.register().status_code, 302)
        page = self.page("/")
        self.assertIn("В саду пока пусто", page)
        self.assertEqual(self.client.get("/register").status_code, 302)

        self.post("/logout")
        self.assertEqual(self.client.get("/stats").status_code, 302)

        bad = self.post("/login", {"username": "egor", "password": "неверный"})
        self.assertEqual(bad.status_code, 200)
        self.assertIn("Неверный логин или пароль", bad.get_data(as_text=True))
        self.assertEqual(self.client.get("/stats").status_code, 302)

        ok = self.post("/login", {"username": "EGOR", "password": "parol12345"})
        self.assertEqual(ok.status_code, 302)
        self.assertEqual(self.client.get("/stats").status_code, 200)

    def test_unknown_user_gets_same_error(self):
        r = self.post("/login", {"username": "nobody", "password": "whatever123"})
        self.assertIn("Неверный логин или пароль", r.get_data(as_text=True))

    def test_password_is_stored_hashed(self):
        self.register(password="parol12345")
        stored = self.query("SELECT password_hash FROM users")[0][0]
        self.assertNotIn("parol12345", stored)
        self.assertGreater(len(stored), 40)

    def test_register_validation(self):
        cases = [
            (dict(password="short"), "не короче 8"),
            (dict(password="parol12345", password2="other12345"), "не совпадают"),
            (dict(username="ab"), "Логин:"),
            (dict(username="имя с пробелом"), "Логин:"),
            (dict(username="<b>x</b>"), "Логин:"),
        ]
        for kwargs, expected in cases:
            r = self.register(**kwargs)
            self.assertEqual(r.status_code, 200, kwargs)
            self.assertIn(expected, r.get_data(as_text=True), kwargs)
        self.assertEqual(self.query("SELECT COUNT(*) FROM users")[0][0], 0)

    def test_duplicate_username_is_rejected_case_insensitively(self):
        self.register("Egor")
        other = app_module.app.test_client()
        r = self.register("egor", client=other)
        self.assertEqual(r.status_code, 200)
        self.assertIn("уже занят", r.get_data(as_text=True))

    def test_login_is_throttled_after_five_failures(self):
        self.register()
        self.post("/logout")
        for _ in range(5):
            self.post("/login", {"username": "egor", "password": "wrong-password"})
        r = self.post("/login", {"username": "egor", "password": "parol12345"})  # даже верный пароль
        self.assertEqual(r.status_code, 429)

    #CSRF

    def test_post_without_valid_csrf_token_is_rejected(self):
        self.register()
        self.client.get("/")
        r = self.post("/habit/add", {"name": "Взлом"}, with_token=False)
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/habit/add", data={"name": "Взлом", "csrf": "подделка"})
        self.assertEqual(r.status_code, 400)
        self.assertNotIn("Взлом", self.page("/garden"))

    #изоляция данных

    def test_users_cannot_see_or_touch_each_others_habits(self):
        alice = self.client
        bob = app_module.app.test_client()
        self.register("alice", client=alice)
        self.add("Секрет Алисы", client=alice)
        self.post("/habit/1/toggle", client=alice)
        self.post("/day/2026-10-13/mood", {"mood": "5", "note": "личная заметка"}, client=alice)
        self.register("bob", client=bob)

        self.assertIn("Секрет Алисы", self.page("/garden", alice))
        for url in ("/garden", "/", "/stats", "/export.json"):
            self.assertNotIn("Секрет Алисы", self.page(url, bob), url)
        self.assertNotIn("личная заметка", self.page("/stats", bob))
        self.assertNotIn("личная заметка", self.page("/day/2026-10-13", bob))
        self.assertIn("10 из 100", self.page("/", alice))
        self.assertIn("0 из 100", self.page("/", bob))

        self.assertEqual(self.post("/habit/1/toggle", client=bob).status_code, 404)
        self.assertEqual(bob.get("/habit/1").status_code, 404)
        self.assertEqual(bob.get("/habit/1/edit").status_code, 404)
        self.assertEqual(self.post("/habit/1/edit", {"name": "Взломано"}, client=bob).status_code, 404)
        self.assertEqual(self.post("/habit/1/archive", client=bob).status_code, 404)
        self.assertEqual(self.post("/habit/1/delete", client=bob).status_code, 404)
        garden = self.page("/garden", alice)
        self.assertIn("Секрет Алисы", garden)
        self.assertNotIn("Взломано", garden)
        self.assertIn("1 из 1", self.page("/", alice))

    #привычки

    def test_all_pages_open_when_empty(self):
        self.register()
        for url in ("/", "/stats", "/garden", "/achievements", "/settings", "/habit/new",
                    "/stats?year=2026&month=2", "/stats?year=abc&month=99"):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_add_toggle_and_stats_flow(self):
        self.register()
        self.assertEqual(self.add().status_code, 302)
        page = self.page("/")
        self.assertIn("Читать", page)
        self.assertIn("0 из 1", page)

        self.post("/habit/1/toggle")
        self.assertIn("1 из 1", self.page("/"))
        self.assertIn("Первый шаг", self.page("/achievements"))

        self.post("/habit/1/toggle")
        self.assertIn("0 из 1", self.page("/"))

        for url in ("/stats", "/garden", "/achievements", "/habit/1"):
            self.assertEqual(self.client.get(url).status_code, 200)

    def test_habit_form_fields_are_saved_and_validated(self):
        self.register()
        self.add("Читать", icon="📚", note="20 минут", plant="sakura", color="custom", color_custom="#123ABC")
        row = self.query("SELECT * FROM habits")[0]
        self.assertEqual((row["icon"], row["note"], row["plant"], row["color"]),
                         ("📚", "20 минут", "sakura", "#123abc"))

        self.add("Бег", icon="не эмодзи", plant="нет-такого", color="javascript:evil", days=["9", "x"])
        row = self.query("SELECT * FROM habits WHERE name = 'Бег'")[0]
        self.assertEqual(row["icon"], "")
        self.assertEqual(row["plant"], "tree")
        self.assertEqual(row["color"], "#22c55e")              
        self.assertEqual(row["weekdays"], "0,1,2,3,4,5,6")  

        for palette_color in (hex_ for _, hex_ in app_module.PALETTE):
            self.assertEqual(app_module.clean_color(palette_color), palette_color)

    def test_empty_name_is_not_saved(self):
        self.register()
        r = self.add(name="   ")
        self.assertEqual(self.query("SELECT COUNT(*) FROM habits")[0][0], 0)
        self.assertIn("new", r.headers["Location"])          

    def test_names_are_escaped(self):
        self.register()
        self.add(name="<script>alert(1)</script>", note="<b>x</b>")
        for url in ("/", "/garden", "/habit/1", "/stats"):
            self.assertNotIn("<script>alert(1)</script>", self.page(url), url)
        self.assertNotIn("<b>x</b>", self.page("/"))

    def test_edit_and_delete(self):
        self.register()
        self.add()
        self.post("/habit/1/toggle")
        self.assertEqual(self.client.get("/habit/1/edit").status_code, 200)
        self.post("/habit/1/edit", {"name": "Читать книгу", "color": "#ff0000", "days": ["0", "2"], "plant": "rose"})
        self.assertIn("Читать книгу", self.page("/garden"))
        self.assertEqual(self.query("SELECT plant FROM habits")[0][0], "rose")
        self.post("/habit/1/delete")
        self.assertNotIn("Читать книгу", self.page("/garden"))
        self.assertEqual(self.query("SELECT COUNT(*) FROM completions")[0][0], 0)

    def test_missing_habit_is_404(self):
        self.register()
        self.assertEqual(self.post("/habit/999/toggle").status_code, 404)
        self.assertEqual(self.client.get("/habit/999/edit").status_code, 404)
        self.assertEqual(self.client.get("/habit/999").status_code, 404)

    def test_rest_day_habit_not_in_today_list(self):
        self.register()
        self.add(name="Спорт", days=("0", "4"))
        page = self.page("/")
        self.assertIn("В этот день отдыхают", page)
        self.assertNotIn("Привычки на сегодня</h2>\n\n      \n        <ul", page)

    def test_habit_page_shows_stats(self):
        self.register()
        self.add(plant="sunflower")
        self.post("/habit/1/toggle")
        page = self.page("/habit/1")
        self.assertIn("Читать", page)
        self.assertIn("Подсолнух", page)
        self.assertIn("лучшая серия", page)
        self.assertIn('class="heatmap"', page)

    def test_stats_page_has_heatmap_and_day_links(self):
        self.register()
        self.add()
        self.post("/habit/1/toggle")
        page = self.page("/stats")
        self.assertIn("Весь год", page)
        self.assertIn('class="heatmap"', page)
        self.assertIn("/day/2026-10-13", page)                 

    #отметка за прошлые дни

    def test_backfill_marks_past_day_and_moves_start_date(self):
        self.register()
        self.add()                                  
        yesterday = days_ago(1).isoformat()
        page = self.page(f"/day/{yesterday}")
        self.assertIn("Вчера", page)
        self.assertIn("сдвинет дату", page)              

        self.post("/habit/1/toggle", {"day": yesterday})
        self.assertEqual(self.query("SELECT day FROM completions")[0][0], yesterday)
        self.assertEqual(self.query("SELECT created FROM habits")[0][0], yesterday)
        self.assertIn("1 из 1", self.page(f"/day/{yesterday}"))
        self.assertIn("0 из 1", self.page("/"))               

    def test_day_window_limits(self):
        self.register()
        self.assertEqual(self.client.get(f"/day/{days_ago(30).isoformat()}").status_code, 200)
        for iso in (days_ago(31).isoformat(), (TODAY + timedelta(days=1)).isoformat(), "вчера", "2026-13-45"):
            self.assertEqual(self.client.get(f"/day/{iso}").status_code, 404, iso)
        self.add()
        r = self.post("/habit/1/toggle", {"day": (TODAY + timedelta(days=1)).isoformat()})
        self.assertEqual(r.status_code, 404)
        r = self.client.get(f"/day/{TODAY.isoformat()}")
        self.assertEqual(r.status_code, 302)                  

    def test_toggle_can_return_to_habit_page_but_not_to_other_sites(self):
        self.register()
        self.add()
        r = self.post("/habit/1/toggle", {"next": "/habit/1"})
        self.assertTrue(r.headers["Location"].endswith("/habit/1"))
        for evil in ("//evil.example", "https://evil.example", "\\\\evil"):
            r = self.post("/habit/1/toggle", {"next": evil})
            self.assertNotIn("evil", r.headers["Location"], evil)


    def test_archive_hides_habit_but_keeps_xp(self):
        self.register()
        self.add("Читать")
        self.add("Спорт")
        self.post("/habit/1/toggle")
        self.post("/habit/1/archive")
        self.assertNotIn("Читать", self.page("/"))
        self.assertIn("Спорт", self.page("/"))
        self.assertIn("Растения на паузе", self.page("/garden"))
        self.assertIn("10 из 100", self.page("/"))       
        self.assertEqual(self.client.get("/habit/1").status_code, 200)

        self.post("/habit/1/archive")                         
        self.assertIn("Читать", self.page("/"))
        self.assertNotIn("Растения на паузе", self.page("/garden"))

    #настроение

    def test_mood_save_validate_and_clear(self):
        self.register()
        today_iso = TODAY.isoformat()
        self.post(f"/day/{today_iso}/mood", {"mood": "4", "note": "Хороший день"})
        self.assertIn("Хороший день", self.page("/"))
        row = self.query("SELECT mood, note FROM moods")[0]
        self.assertEqual((row["mood"], row["note"]), (4, "Хороший день"))

        self.post(f"/day/{today_iso}/mood", {"mood": "9", "note": "x" * 500}) 
        row = self.query("SELECT mood, note FROM moods")[0]
        self.assertIsNone(row["mood"])
        self.assertEqual(len(row["note"]), 200)

        self.post(f"/day/{today_iso}/mood", {"mood": "", "note": ""})
        self.assertEqual(self.query("SELECT COUNT(*) FROM moods")[0][0], 0)

        self.assertEqual(self.post("/day/2026-01-01/mood", {"mood": "3"}).status_code, 404)

    #достижения и уведомления

    def test_achievement_flash_and_persistence(self):
        self.register()
        self.add()
        self.post("/habit/1/toggle")
        page = self.page("/")
        self.assertIn("Достижение: «Первый шаг»", page)
        self.assertIn("+10 XP", page)
        self.assertNotIn("Достижение: «Первый шаг»", self.page("/")) 

        self.post("/habit/1/toggle")                                 
        page = self.page("/achievements")
        self.assertIn("Первый шаг", page)
        self.assertIn("Получено 14 октября", page)
        self.assertEqual(self.query("SELECT COUNT(*) FROM user_achievements WHERE key = 'first'")[0][0], 1)

    def test_level_up_notification(self):
        self.register()
        self.add()
        for ago in range(1, 11):                                 
            self.post("/habit/1/toggle", {"day": days_ago(ago).isoformat()})
        page = self.page("/")
        self.assertIn("Новый уровень: 2", page)
        self.assertIn("Разгон", self.page("/achievements"))

    def test_mood_achievement(self):
        self.register()
        for ago in range(7):
            self.post(f"/day/{days_ago(ago).isoformat()}/mood", {"mood": "4"})
        self.assertEqual(self.query("SELECT COUNT(*) FROM user_achievements WHERE key = 'mood7'")[0][0], 1)

    #настройки

    def test_appearance_settings(self):
        self.register()
        self.assertIn('data-theme="auto"', self.page("/"))
        self.post("/settings/appearance", {"theme": "dark", "accent": "blue"})
        page = self.page("/")
        self.assertIn('data-theme="dark"', page)
        self.assertIn('data-accent="blue"', page)
        self.post("/settings/appearance", {"theme": 'x"><script>', "accent": "не-акцент"}) 
        page = self.page("/")
        self.assertIn('data-theme="dark"', page)
        self.assertIn('data-accent="blue"', page)

    def test_theme_toggle_and_safe_redirect(self):
        self.register()
        r = self.post("/settings/theme-toggle", {"current": "light", "next": "/stats"})
        self.assertTrue(r.headers["Location"].endswith("/stats"))
        self.assertIn('data-theme="dark"', self.page("/"))
        self.post("/settings/theme-toggle", {"current": "dark", "next": "//evil.example"})
        self.assertIn('data-theme="light"', self.page("/"))
        r = self.post("/settings/theme-toggle", {"current": "light", "next": "//evil.example"})
        self.assertNotIn("evil", r.headers["Location"])

    def test_change_password(self):
        self.register()
        self.post("/settings/password", {"current": "неверный", "password": "newpass123", "password2": "newpass123"})
        self.assertIn("Текущий пароль указан неверно", self.page("/"))
        self.post("/settings/password", {"current": "parol12345", "password": "newpass123", "password2": "другой"})
        self.assertIn("Пароли не совпадают", self.page("/"))
        self.post("/settings/password", {"current": "parol12345", "password": "short", "password2": "short"})
        self.assertIn("не короче 8", self.page("/"))

        self.post("/settings/password", {"current": "parol12345", "password": "newpass123", "password2": "newpass123"})
        self.post("/logout")
        self.assertEqual(self.post("/login", {"username": "egor", "password": "parol12345"}).status_code, 200)
        self.assertEqual(self.post("/login", {"username": "egor", "password": "newpass123"}).status_code, 302)

    def test_export_contains_own_data(self):
        self.register()
        self.add("Читать", icon="📚")
        self.post("/habit/1/toggle")
        self.post(f"/day/{TODAY.isoformat()}/mood", {"mood": "5", "note": "ура"})
        r = self.client.get("/export.json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r.headers["Content-Disposition"])
        data = json.loads(r.get_data(as_text=True))
        self.assertEqual(data["username"], "egor")
        self.assertEqual(data["habits"][0]["name"], "Читать")
        self.assertEqual(data["habits"][0]["completions"], [TODAY.isoformat()])
        self.assertEqual(data["moods"][0]["note"], "ура")
        self.assertNotIn("password", json.dumps(data))

    def test_delete_account(self):
        other = app_module.app.test_client()
        self.register("keeper", client=other)
        self.add("Чужая", client=other)

        self.register()
        self.add()
        self.post("/habit/2/toggle")
        self.post(f"/day/{TODAY.isoformat()}/mood", {"mood": "3"})

        self.post("/settings/delete", {"password": "неверный", "confirm": "yes"})   
        self.assertEqual(self.query("SELECT COUNT(*) FROM users")[0][0], 2)
        self.post("/settings/delete", {"password": "parol12345"})                  
        self.assertEqual(self.query("SELECT COUNT(*) FROM users")[0][0], 2)

        r = self.post("/settings/delete", {"password": "parol12345", "confirm": "yes"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual([r_[0] for r_ in self.query("SELECT username FROM users")], ["keeper"])
        self.assertEqual(self.query("SELECT COUNT(*) FROM habits")[0][0], 1)          
        self.assertEqual(self.query("SELECT COUNT(*) FROM completions")[0][0], 0)
        self.assertEqual(self.query("SELECT COUNT(*) FROM moods")[0][0], 0)
        self.assertEqual(self.query("SELECT COUNT(*) FROM user_achievements WHERE user_id = 2")[0][0], 0)
        self.assertEqual(self.client.get("/garden").status_code, 302)
        self.assertEqual(self.post("/login", {"username": "egor", "password": "parol12345"}).status_code, 200)

    def test_custom_404_page(self):
        r = self.client.get("/нет-такой-страницы")
        self.assertEqual(r.status_code, 404)
        self.assertIn("Здесь ничего не растёт", r.get_data(as_text=True))

    #старые базы

    def test_habits_without_owner_go_to_first_user(self):
        with app_module.app.app_context():
            db = app_module.get_db()
            db.execute("INSERT INTO habits (user_id, name, color, weekdays, created) "
                       "VALUES (NULL, 'Старая привычка', '#4caf50', '0,1,2,3,4,5,6', ?)", (days_ago(5).isoformat(),))
            db.commit()
        self.register("first")
        self.assertIn("Старая привычка", self.page("/garden"))
        other = app_module.app.test_client()
        self.register("second", client=other)
        self.assertNotIn("Старая привычка", self.page("/garden", other))

    def test_old_database_is_migrated(self):
        old = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        old.close()
        con = sqlite3.connect(old.name)
        con.executescript("""
            CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                                password_hash TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE habits (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                                 color TEXT NOT NULL, weekdays TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE completions (id INTEGER PRIMARY KEY AUTOINCREMENT, habit_id INTEGER NOT NULL,
                                      day TEXT NOT NULL, UNIQUE (habit_id, day));
            INSERT INTO users (username, password_hash, created) VALUES ('old', 'x', '2026-10-01');
            INSERT INTO habits (name, color, weekdays, created) VALUES ('Из прошлой версии', '#4caf50', '0,1', '2026-10-01');
        """)
        con.commit()
        con.close()

        real = app_module.app.config["DATABASE"]
        app_module.app.config["DATABASE"] = old.name
        try:
            with app_module.app.app_context():
                app_module.init_db()
                app_module.init_db()                  
                db = app_module.get_db()
                habit_cols = {r["name"] for r in db.execute("PRAGMA table_info(habits)")}
                user_cols = {r["name"] for r in db.execute("PRAGMA table_info(users)")}
                self.assertTrue({"user_id", "icon", "note", "plant", "archived"} <= habit_cols)
                self.assertTrue({"theme", "accent"} <= user_cols)
                row = db.execute("SELECT * FROM habits").fetchone()
                self.assertEqual((row["name"], row["plant"], row["archived"]), ("Из прошлой версии", "tree", 0))
                self.assertEqual(db.execute("SELECT theme FROM users").fetchone()[0], "auto")
                tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
                self.assertTrue({"moods", "user_achievements"} <= tables)
        finally:
            app_module.app.config["DATABASE"] = real
            os.unlink(old.name)


if __name__ == "__main__":
    unittest.main()
