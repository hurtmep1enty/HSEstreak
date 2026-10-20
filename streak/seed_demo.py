
import app as app_module
from demo import DEMO_LOGIN, DEMO_PASSWORD, seed

with app_module.app.app_context():
    if seed(app_module.get_db(), app_module.today()):
        print(f"Готово. Войди на сайте: логин {DEMO_LOGIN}, пароль {DEMO_PASSWORD}")
    else:
        print("Демо-аккаунт уже существует. Удали streak.db, если хочешь начать заново.")
