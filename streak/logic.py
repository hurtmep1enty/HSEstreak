
import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from plants import DEFAULT_SPECIES, SPECIES

XP_PER_COMPLETION = 10   
XP_PER_LEVEL = 100       


PALETTE = [
    "#e53935", "#d81b60", "#f06292", "#ff8a65",  
    "#fb8c00", "#ffb300", "#fdd835", "#c0ca33",   
    "#7cb342", "#43a047", "#26a69a", "#00897b",   
    "#00acc1", "#039be5", "#1e88e5", "#3949ab",   
    "#5e35b1", "#8e24aa", "#ab47bc", "#ce93d8",   
    "#6d4c41", "#8d6e63", "#546e7a", "#455a64",   
]

MONTHS_SHORT = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]


@dataclass
class Habit:
    id: int
    name: str
    color: str
    days: set        
    created: date    
    species: str = DEFAULT_SPECIES   

    def scheduled_on(self, d):
        """Нужно ли выполнять привычку в день d."""
        return d >= self.created and d.weekday() in self.days


#серии

def habit_streak(habit, done, today):
    streak = 0
    d = today
    if habit.scheduled_on(d) and d not in done:
        d -= timedelta(days=1)
    while d >= habit.created:
        if habit.scheduled_on(d):
            if d in done:
                streak += 1
            else:
                break
        d -= timedelta(days=1)
    return streak


def best_habit_streak(habit, done, today):
    best = current = 0
    d = habit.created
    while d <= today:
        if habit.scheduled_on(d):
            if d in done:
                current += 1
                best = max(best, current)
            elif d != today:      
                current = 0
        d += timedelta(days=1)
    return best


def global_streak(all_days, today):
    streak = 0
    d = today
    if d not in all_days:
        d -= timedelta(days=1)
    while d in all_days:
        streak += 1
        d -= timedelta(days=1)
    return streak


def longest_streak(all_days):
    best = current = 0
    prev = None
    for d in sorted(all_days):
        if prev is not None and d - prev == timedelta(days=1):
            current += 1
        else:
            current = 1
        best = max(best, current)
        prev = d
    return best


#проценты
def completion_counts(habit, done, today, days=7):
    planned = 0
    completed = 0
    for i in range(days):
        d = today - timedelta(days=i)
        if habit.scheduled_on(d):
            planned += 1
            if d in done:
                completed += 1
    return completed, planned


def percent(completed, planned):
    if planned == 0:
        return 0
    return round(completed / planned * 100)


def day_progress(habits, done_map, d):
    planned = 0
    done = 0
    for h in habits:
        if h.scheduled_on(d):
            planned += 1
        if d in done_map.get(h.id, ()):
            done += 1
    return done, planned


def perfect_days(habits, done_map, today, max_days=730):
    if not habits:
        return 0
    start = max(min(h.created for h in habits), today - timedelta(days=max_days))
    count = 0
    d = start
    while d <= today:
        done, planned = day_progress(habits, done_map, d)
        if planned > 0 and done >= planned:
            count += 1
        d += timedelta(days=1)
    return count


#растения

# (сколько отметок нужно, значок, название стадии). Картинки рисует plants.py.
STAGES = [
    (0, "🌰", "Семя"),
    (2, "🌱", "Росток"),
    (5, "🌿", "Побег"),
    (10, "🌷", "Бутон"),
    (20, "🌸", "Цветение"),
    (40, "🌟", "Расцвет"),
]


def is_wilting(habit, done, today):
    last = []
    d = today - timedelta(days=1)
    for _ in range(60):
        if d < habit.created:
            break
        if habit.scheduled_on(d):
            last.append(d)
            if len(last) == 3:
                break
        d -= timedelta(days=1)
    return len(last) == 3 and not any(x in done for x in last)


def plant_stage(total_done, wilting=False):
    idx = 0
    for i, (threshold, _icon, _name) in enumerate(STAGES):
        if total_done >= threshold:
            idx = i
    threshold, icon, name = STAGES[idx]
    if idx + 1 < len(STAGES):
        next_at = STAGES[idx + 1][0]
        progress = int((total_done - threshold) / (next_at - threshold) * 100)
    else:
        next_at = None
        progress = 100
    if wilting:
        icon = "🥀"
        name += " (увядает)"
    return {"index": idx, "icon": icon, "name": name, "next_at": next_at, "progress": progress}


#опыт, уровни

LEVEL_TITLES = ["Семечко", "Росток", "Садовник", "Цветовод", "Агроном",
                "Ботаник", "Мастер сада", "Хранитель рощи", "Лесничий", "Древо жизни"]


def xp_info(total_done):
    xp = total_done * XP_PER_COMPLETION
    level = xp // XP_PER_LEVEL + 1
    return {"xp": xp, "level": level, "xp_into": xp % XP_PER_LEVEL, "title": level_title(level)}


def level_title(level):
    return LEVEL_TITLES[min(level, len(LEVEL_TITLES)) - 1]


# Украшения сада открываются с уровнем: (уровень, ключ, значок, название)
DECORATIONS = [
    (2, "butterfly", "🦋", "Бабочки"),
    (3, "bee", "🐝", "Пчёлы"),
    (4, "cloud", "☁️", "Больше облаков"),
    (5, "ladybug", "🐞", "Божья коровка"),
    (6, "rainbow", "🌈", "Радуга"),
    (8, "bird", "🐦", "Птицы"),
    (10, "fireflies", "✨", "Светлячки"),
]


def decorations(level):
    return [
        {"key": key, "icon": icon, "name": name, "level": need, "unlocked": level >= need}
        for need, key, icon, name in DECORATIONS
    ]


#достижения 
# (id, значок, название, описание, какой показатель смотрим, цель, редкость)
ACHIEVEMENTS = [
    ("first", "👣", "Первый шаг", "Отметить первую привычку", "total_done", 1, "common"),
    ("ten", "✋", "Десяточка", "10 отметок", "total_done", 10, "common"),
    ("fifty", "🎯", "Полсотни", "50 отметок", "total_done", 50, "rare"),
    ("hundred", "💯", "Сотня", "100 отметок", "total_done", 100, "rare"),
    ("year", "🏔️", "Год в деле", "365 отметок", "total_done", 365, "epic"),
    ("garden3", "🪴", "Садовник", "Завести 3 привычки", "habits_count", 3, "common"),
    ("garden6", "🏡", "Огородник", "Завести 6 привычек", "habits_count", 6, "rare"),
    ("streak3", "🔥", "Разогрев", "Серия 3 дня подряд", "longest_streak", 3, "common"),
    ("week", "📅", "Первая неделя", "Серия 7 дней подряд", "longest_streak", 7, "common"),
    ("iron", "🛡️", "Железная дисциплина", "Серия 14 дней подряд", "longest_streak", 14, "rare"),
    ("month", "🌙", "Месяц без пропусков", "Серия 30 дней подряд", "longest_streak", 30, "epic"),
    ("perfect1", "✨", "Идеальный день", "Выполнить всё запланированное за день", "perfect_days", 1, "common"),
    ("perfect7", "🌟", "Семь идеальных", "7 идеальных дней", "perfect_days", 7, "rare"),
    ("perfect30", "👑", "Безупречный", "30 идеальных дней", "perfect_days", 30, "epic"),
    ("level3", "⭐", "Третий уровень", "Достичь 3 уровня", "level", 3, "common"),
    ("level5", "🌠", "Пятый уровень", "Достичь 5 уровня", "level", 5, "rare"),
    ("level10", "🚀", "Десятый уровень", "Достичь 10 уровня", "level", 10, "epic"),
    ("bloom", "🌸", "Первый цветок", "Вырастить растение до стадии «Цветение»", "max_stage", 4, "rare"),
    ("peak", "🏵️", "Расцвет", "Довести растение до последней стадии", "max_stage", 5, "epic"),
    ("botanist", "🔬", "Ботаник", "Вырастить 3 разных вида растений", "species_count", 3, "rare"),
    ("collector", "🌍", "Коллекционер", "Вырастить все виды растений", "species_count", len(SPECIES), "epic"),
]


def unlocked_achievements(stats):
    result = []
    for a_id, icon, title, desc, key, target, rarity in ACHIEVEMENTS:
        value = stats.get(key, 0)
        result.append({
            "id": a_id, "icon": icon, "title": title, "description": desc, "rarity": rarity,
            "value": min(value, target), "target": target,
            "progress": min(100, int(value / target * 100)),
            "unlocked": value >= target,
        })
    return result


#календарь

def month_grid(year, month, habits, done_map, today):
    weeks = []
    for week in calendar.Calendar(firstweekday=0).monthdatescalendar(year, month):
        row = []
        for d in week:
            done, planned = day_progress(habits, done_map, d)
            if d.month != month:
                state = "out"
            elif d > today:
                state = "future"
            elif planned == 0 and done == 0:
                state = "rest"
            elif done == 0:
                state = "empty"
            elif done >= planned:
                state = "full"
            else:
                state = "partial"
            row.append({"date": d, "planned": planned, "done": done, "state": state})
        weeks.append(row)
    return weeks


def heatmap(habits, done_map, today, weeks=26):
    start = today - timedelta(days=today.weekday() + 7 * (weeks - 1)) 
    columns = []
    labels = []
    prev_month = None
    for w in range(weeks):
        col = []
        monday = start + timedelta(days=7 * w)
        for i in range(7):
            d = monday + timedelta(days=i)
            if d > today:
                col.append({"date": d, "cls": "future", "done": 0, "planned": 0})
                continue
            done, planned = day_progress(habits, done_map, d)
            if done == 0:
                cls = "rest" if planned == 0 else "l0"
            else:
                ratio = min(1.0, done / planned) if planned else 1.0
                cls = "l1" if ratio <= 0.25 else "l2" if ratio <= 0.5 else "l3" if ratio < 1 else "l4"
            col.append({"date": d, "cls": cls, "done": done, "planned": planned})
        columns.append(col)
        labels.append(MONTHS_SHORT[monday.month - 1] if monday.month != prev_month else "")
        prev_month = monday.month
    return {"columns": columns, "labels": labels}


#вспомогательное

TIPS = [
    "Лучше пять минут каждый день, чем два часа раз в месяц.",
    "Привяжи новую привычку к старой: после чистки зубов — зарядка.",
    "Пропустил день? Не страшно. Главное — не пропускать два подряд.",
    "Начни с такого маленького шага, чтобы отказаться было стыдно.",
    "Расскажи другу о своей привычке: так выше шанс не бросить.",
    "Подготовь всё с вечера: кроссовки у двери, книга на подушке.",
    "Награждай себя за серии. Хотя бы чаем с любимым печеньем.",
    "Меньше привычек — больше результата. Лучше три живых, чем десять завядших.",
    "Если не получается каждый день, поставь реже. Это не слабость, а план.",
    "Растение растёт незаметно. Привычка тоже. Просто продолжай.",
    "Отмечай сразу после выполнения: приятно и не забудется.",
    "Связывай привычку с местом: читаешь только в кресле, учишь язык только за столом.",
    "Не сравнивай свой первый месяц с чужим пятым годом.",
    "Хороший день начинается с одной маленькой победы.",
    "Если лень, пообещай себе только две минуты. Обычно втягиваешься.",
    "Смотри на календарь: цепочка зелёных дней сама мотивирует не рвать её.",
    "Сон, еда и вода — фундамент всех привычек. Начни с них.",
    "Вернуться после перерыва тоже считается. Сад прощает.",
    "Каждая отметка — голос за того человека, которым ты хочешь стать.",
    "Скучно — значит работает. Привычки строятся на повторении.",
]


def tip_of_the_day(d):
    return TIPS[d.toordinal() % len(TIPS)]


def greeting(hour):
    if 5 <= hour < 12:
        return "Доброе утро"
    if 12 <= hour < 18:
        return "Добрый день"
    if 18 <= hour < 23:
        return "Добрый вечер"
    return "Доброй ночи"


def plural(n, forms):
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return forms[0]
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return forms[1]
    return forms[2]
