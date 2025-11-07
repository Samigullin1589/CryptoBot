# 📝 Шпаргалка по командам для деплоя на Render

## 🔧 Git команды

### Первоначальная настройка
```bash
# Инициализация репозитория (если еще не создан)
git init

# Добавление remote
git remote add origin https://github.com/ВАШ_USERNAME/CryptoBot.git

# Проверка remote
git remote -v
```

### Добавление файлов для деплоя
```bash
# Добавить конфигурационные файлы
git add render.yaml runtime.txt

# Или добавить все изменения
git add .

# Проверить статус
git status

# Закоммитить
git commit -m "Add Render deployment configuration"

# Запушить в GitHub
git push origin main
```

### Обновление после изменений
```bash
# Посмотреть изменения
git diff

# Добавить изменения
git add .

# Закоммитить с описанием
git commit -m "Update bot handlers"

# Запушить (автоматически задеплоится на Render)
git push origin main
```

### Откат изменений
```bash
# Посмотреть историю коммитов
git log --oneline

# Откатить к предыдущему коммиту (локально)
git reset --soft HEAD~1

# Откатить файл к предыдущему состоянию
git checkout -- имя_файла

# Force push (если нужно откатить на сервере)
git push --force origin main
```

---

## 🌐 Работа с Render

### Через Web Dashboard

#### Создание сервиса
1. Dashboard → New + → Blueprint
2. Выбрать репозиторий
3. Apply

#### Управление переменными окружения
1. Dashboard → Ваш сервис → Environment
2. Add Environment Variable
3. Key: `BOT_TOKEN`, Value: `ваш_токен`
4. Save Changes

#### Просмотр логов
1. Dashboard → Ваш сервис → Logs
2. Фильтр по уровню: Info / Warning / Error
3. Скачать логи: Download Logs

#### Ручной деплой
1. Dashboard → Ваш сервис → Manual Deploy
2. Deploy latest commit / Clear build cache & deploy

#### Перезапуск сервиса
1. Dashboard → Ваш сервис → Manual Deploy
2. Restart

---

## 🔍 Проверка статуса

### Проверка health endpoint
```bash
# Локально
curl http://localhost:10000/health

# На Render
curl https://ваше-приложение.onrender.com/health
```

### Проверка бота в Telegram
```bash
# Отправьте команды:
/start
/help
/ping
```

---

## 🐛 Диагностика проблем

### Просмотр логов
```bash
# В Render Dashboard → Logs

# Или сохраните в файл и изучите локально
# (кнопка Download Logs в дашборде)
```

### Проверка переменных окружения
```bash
# В Render Dashboard → Environment
# Убедитесь, что все переменные установлены правильно

# BOT_TOKEN - без пробелов
# ADMIN_IDS - через запятую без пробелов
# REDIS_URL - должна быть автоматической
```

### Тестирование локально с production настройками
```bash
# Создайте .env файл с production переменными
export BOT_TOKEN=ваш_токен
export ADMIN_IDS=123456789
export REDIS_URL=redis://localhost:6379
export ENVIRONMENT=production

# Запустите бота
python -m bot.main

# В другом терминале проверьте health
curl http://localhost:10000/health
```

---

## 🚀 Автоматизация

### GitHub Actions для автотестов

Создайте `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/
```

### Pre-commit хук

Создайте `.git/hooks/pre-commit`:

```bash
#!/bin/bash

echo "Running pre-commit checks..."

# Проверка на наличие .env файлов
if git diff --cached --name-only | grep -q ".env$"; then
    echo "ERROR: Attempting to commit .env file!"
    exit 1
fi

# Запуск тестов
python -m pytest tests/
if [ $? -ne 0 ]; then
    echo "ERROR: Tests failed!"
    exit 1
fi

echo "All checks passed!"
```

Сделайте исполняемым:
```bash
chmod +x .git/hooks/pre-commit
```

---

## 📦 Управление зависимостями

### Обновление requirements.txt
```bash
# Сгенерировать из текущего окружения
pip freeze > requirements.txt

# Или вручную указать только прямые зависимости
# requirements.txt:
aiogram>=3.0.0
redis>=4.5.0
aiohttp>=3.8.0
python-dotenv>=1.0.0
```

### Виртуальное окружение
```bash
# Создать venv
python -m venv venv

# Активировать (Linux/Mac)
source venv/bin/activate

# Активировать (Windows)
venv\Scripts\activate

# Установить зависимости
pip install -r requirements.txt

# Деактивировать
deactivate
```

---

## 🔒 Безопасность

### .gitignore (обязательно!)
```bash
# Добавьте в .gitignore:
.env
.env.*
*.log
*.db
__pycache__/
*.pyc
.venv/
venv/
```

### Проверка, что .env не закоммичен
```bash
# Проверить текущий коммит
git diff --cached

# Удалить файл из staging
git reset HEAD .env

# Удалить из истории Git (если случайно закоммитили)
git filter-branch --index-filter \
  "git rm -rf --cached --ignore-unmatch .env" HEAD
```

---

## 📊 Мониторинг

### Простой uptime мониторинг

Используйте бесплатный сервис:
- UptimeRobot: https://uptimerobot.com
- Настройте проверку: `https://ваше-приложение.onrender.com/health`
- Интервал: 5 минут
- Алерт: Email/Telegram при падении

### Логирование в файл (локально)
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
```

---

## 🔄 Обновление бота

### Стандартный процесс обновления
```bash
# 1. Внесите изменения в код
# 2. Протестируйте локально
python -m bot.main

# 3. Закоммитьте
git add .
git commit -m "Add new feature: X"

# 4. Запушьте (автодеплой на Render)
git push origin main

# 5. Проверьте логи в Render Dashboard
# 6. Протестируйте в Telegram
```

### Hotfix (срочное исправление)
```bash
# 1. Создайте hotfix ветку
git checkout -b hotfix/critical-bug

# 2. Исправьте баг
# 3. Закоммитьте
git add .
git commit -m "Fix critical bug"

# 4. Смержите в main
git checkout main
git merge hotfix/critical-bug

# 5. Запушьте
git push origin main

# 6. Удалите hotfix ветку
git branch -d hotfix/critical-bug
```

---

## 🎯 Полезные алиасы Git

Добавьте в `~/.gitconfig`:

```bash
[alias]
    st = status
    co = checkout
    br = branch
    ci = commit
    ca = commit -a
    cam = commit -am
    df = diff
    lg = log --oneline --graph --decorate
    last = log -1 HEAD
    unstage = reset HEAD --
```

Использование:
```bash
git st          # вместо git status
git co main     # вместо git checkout main
git lg          # красивый лог
git cam "msg"   # commit all с сообщением
```

---

## 💡 Советы и трюки

### Быстрая проверка готовности
```bash
# Создайте alias в ~/.bashrc или ~/.zshrc
alias check-deploy="python check_deploy_ready.py"

# Использование:
check-deploy
```

### Быстрый деплой
```bash
# Создайте скрипт deploy.sh:
#!/bin/bash
git add .
git commit -m "Deploy: $(date '+%Y-%m-%d %H:%M:%S')"
git push origin main
echo "✓ Deployed! Check Render Dashboard for logs."

# Использование:
chmod +x deploy.sh
./deploy.sh
```

### Откат к предыдущей версии
```bash
# В Render Dashboard:
# Manual Deploy → Redeploy (выберите предыдущий коммит)

# Или через Git:
git revert HEAD
git push origin main
```

---

## 🆘 Экстренные команды

### Бот упал - быстрое восстановление
```bash
# 1. Перезапустите через Render Dashboard
# 2. Проверьте логи
# 3. Если не помогло - откатите к последней рабочей версии:
git revert HEAD
git push origin main
```

### Redis очистка (если нужно)
```python
# Подключитесь к Redis и очистите все данные
import redis
r = redis.from_url(REDIS_URL)
r.flushdb()  # Осторожно! Удаляет ВСЕ данные
```

### Полная переустановка
```bash
# В Render Dashboard:
# Settings → Delete Service
# Затем создайте заново через Blueprint
```

---

## ✅ Ежедневная рутина

```bash
# Утренняя проверка
1. Зайти в Render Dashboard
2. Проверить статус сервисов (должны быть зеленые)
3. Проглядеть логи на ошибки
4. Проверить бота в Telegram: /start

# При внесении изменений
1. Тестировать локально
2. git add . && git commit -m "..."
3. git push
4. Проверить деплой в Render
5. Проверить в Telegram
```

---

**Удачи! 🚀**