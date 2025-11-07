# 🔧 Troubleshooting Guide - Решение проблем на Render

## 🚨 Частые проблемы и решения

---

### 1️⃣ Бот не запускается / Build Failed

#### Симптомы:
- Build fails в логах
- Статус "Build failed" в Render
- Ошибки установки зависимостей

#### Решения:

**A. Проблемы с requirements.txt**
```bash
# Проверьте версии пакетов
pip freeze > requirements.txt

# Убедитесь, что все зависимости указаны
# Минимальный набор для Telegram бота:
aiogram>=3.0.0
aiohttp>=3.8.0
redis>=4.5.0
python-dotenv>=1.0.0
```

**B. Несовместимость Python версий**
```bash
# Проверьте runtime.txt
echo "python-3.11.9" > runtime.txt

# Или используйте другую поддерживаемую версию:
# python-3.9.18
# python-3.10.13
# python-3.11.9
```

**C. Проблемы с системными зависимостями**
```yaml
# В render.yaml добавьте:
buildCommand: |
  apt-get update && apt-get install -y libmagic1 &&
  pip install -r requirements.txt
```

---

### 2️⃣ Health Check Failing

#### Симптомы:
- "Health check failing" в логах
- Бот перезапускается каждые несколько минут
- Статус нестабилен

#### Решения:

**A. Проверьте health_check_server.py**
```python
import os
from aiohttp import web

async def health(request):
    """Endpoint для health check"""
    return web.Response(text='OK', status=200)

async def start_health_server():
    """Запуск health check сервера"""
    app = web.Application()
    app.router.add_get('/health', health)
    
    port = int(os.getenv('PORT', 10000))
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"Health check server started on port {port}")
```

**B. Запуск в main.py**
```python
import asyncio
from bot.health_check_server import start_health_server

async def main():
    # ВАЖНО: Запускаем health server ПЕРВЫМ
    asyncio.create_task(start_health_server())
    
    # Даём серверу время запуститься
    await asyncio.sleep(1)
    
    # Затем запускаем бота
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
```

**C. Проверьте render.yaml**
```yaml
services:
  - type: web
    healthCheckPath: /health  # Должно совпадать с роутом
```

**D. Тестирование локально**
```bash
# Установите PORT и запустите
export PORT=10000
python -m bot.main

# В другом терминале проверьте:
curl http://localhost:10000/health
# Должно вернуть: OK
```

---

### 3️⃣ Redis Connection Error

#### Симптомы:
- `redis.exceptions.ConnectionError`
- `Failed to connect to Redis`
- Бот не сохраняет состояния

#### Решения:

**A. Проверьте переменную REDIS_URL**
```bash
# В Render Dashboard → Environment:
# REDIS_URL должна быть автоматической:
fromService:
  type: redis
  name: cryptobot-redis
  property: connectionString

# НЕ добавляйте её вручную!
```

**B. Убедитесь, что Redis создан**
```yaml
# В render.yaml должен быть:
services:
  - type: redis
    name: cryptobot-redis
    region: frankfurt
    plan: starter
```

**C. Проверьте подключение в коде**
```python
import redis.asyncio as redis
import os

async def check_redis():
    try:
        r = redis.from_url(os.getenv('REDIS_URL'))
        await r.ping()
        print("✓ Redis connected")
        return True
    except Exception as e:
        print(f"✗ Redis error: {e}")
        return False
```

**D. Временное решение (не для production!)**
```python
# Если Redis недоступен, используйте memory storage
from aiogram.fsm.storage.memory import MemoryStorage

# Вместо RedisStorage:
storage = MemoryStorage()
```

---

### 4️⃣ Бот не отвечает на команды

#### Симптомы:
- Бот онлайн, но не отвечает
- Нет ошибок в логах
- Команды игнорируются

#### Решения:

**A. Проверьте BOT_TOKEN**
```bash
# В Render → Environment
# BOT_TOKEN должен быть БЕЗ пробелов и переносов строк
BOT_TOKEN=1234567890:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
```

**B. Убедитесь, что бот не запущен в другом месте**
```bash
# Остановите локальную версию бота
# Проверьте другие серверы (Heroku, VPS и т.д.)
# Только ОДНА инстанция должна быть активна!
```

**C. Проверьте allowed_updates**
```python
# В main.py:
await dp.start_polling(
    bot,
    allowed_updates=['message', 'callback_query']
)
```

**D. Логирование**
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Добавьте логи в хендлеры:
@router.message(Command('start'))
async def cmd_start(message: Message):
    logging.info(f"Start command from {message.from_user.id}")
    await message.answer("Привет!")
```

---

### 5️⃣ Out of Memory / Crashed

#### Симптомы:
- "Out of memory" в логах
- Внезапные крэши
- Memory usage растет

#### Решения:

**A. Оптимизируйте использование памяти**
```python
# Используйте генераторы вместо списков:
# Плохо:
all_users = [user for user in fetch_all_users()]

# Хорошо:
for user in fetch_users_generator():
    process(user)

# Очищайте кеш:
import gc
gc.collect()
```

**B. Ограничьте размер данных в Redis**
```python
# Устанавливайте TTL для ключей:
await redis.setex(key, 3600, value)  # 1 час

# Используйте maxmemory-policy:
# В render.yaml:
maxmemoryPolicy: allkeys-lru
```

**C. Upgrade плана**
```
Starter: 512MB RAM
Standard: 2GB RAM
```

---

### 6️⃣ Slow Response / Timeout

#### Симптомы:
- Медленные ответы бота
- Timeout ошибки
- Задержки в обработке

#### Решения:

**A. Асинхронная обработка**
```python
# Используйте asyncio для долгих операций:
import asyncio

async def slow_operation():
    await asyncio.sleep(5)
    return "Result"

# В хендлере:
async def handler(message: Message):
    await message.answer("Обрабатываю...")
    result = await slow_operation()
    await message.answer(result)
```

**B. Кеширование**
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_cached_data(key: str):
    # Тяжелая операция
    return data
```

**C. Background tasks**
```python
# Для долгих операций используйте Celery или APScheduler:
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
scheduler.add_job(heavy_task, 'interval', minutes=5)
scheduler.start()
```

---

### 7️⃣ Environment Variables Not Working

#### Симптомы:
- `None` в переменных окружения
- Дефолтные значения вместо реальных
- KeyError для переменных

#### Решения:

**A. Проверьте синтаксис в Render**
```bash
# Правильно:
BOT_TOKEN=123456:ABC-DEF
ADMIN_IDS=123456789,987654321

# Неправильно:
BOT_TOKEN = 123456:ABC-DEF  # Без пробелов!
ADMIN_IDS = [123456789]     # Без скобок!
```

**B. Безопасное получение переменных**
```python
import os

# С дефолтным значением:
token = os.getenv('BOT_TOKEN', '')

# С проверкой:
token = os.environ.get('BOT_TOKEN')
if not token:
    raise ValueError("BOT_TOKEN not set!")

# Для списков:
admin_ids = [
    int(id.strip()) 
    for id in os.getenv('ADMIN_IDS', '').split(',') 
    if id.strip()
]
```

**C. Загрузка .env в development**
```python
from dotenv import load_dotenv
import os

if os.getenv('ENVIRONMENT') != 'production':
    load_dotenv()
```

---

### 8️⃣ Auto-Deploy Not Working

#### Симптомы:
- Push в GitHub не триггерит деплой
- Изменения не применяются
- Старая версия работает

#### Решения:

**A. Проверьте Auto-Deploy**
```bash
# В Render Dashboard:
Settings → Build & Deploy → Auto-Deploy: ON
```

**B. Проверьте branch**
```bash
# Убедитесь, что пушите в правильную ветку:
git push origin main  # Не master!

# Проверьте настройки в render.yaml:
branch: main
```

**C. Manual Deploy**
```bash
# В Render Dashboard:
Manual Deploy → Deploy latest commit
```

---

## 🔍 Диагностика проблем

### Чек-лист для диагностики:

```bash
# 1. Проверьте логи в Render Dashboard → Logs
# 2. Проверьте статус сервисов
# 3. Проверьте переменные окружения
# 4. Проверьте health check endpoint
# 5. Тестируйте локально с теми же переменными

# Локальный тест с production конфигом:
export BOT_TOKEN=your_token
export ADMIN_IDS=123456
export REDIS_URL=redis://localhost:6379
export ENVIRONMENT=production
python -m bot.main
```

---

## 📊 Полезные команды

### Просмотр логов в реальном времени:
```bash
# В Render Dashboard → Logs
# Или используйте Render CLI:
render logs -f
```

### Перезапуск сервиса:
```bash
# Render Dashboard → Manual Deploy → Restart
```

### Проверка Redis:
```bash
# Используйте Redis CLI (если доступен):
redis-cli -u $REDIS_URL ping
```

---

## 🆘 Если ничего не помогает

1. **Проверьте статус Render**
   - https://status.render.com

2. **Обратитесь в поддержку**
   - support@render.com
   - community.render.com

3. **Создайте issue в GitHub**
   - Приложите логи
   - Опишите шаги воспроизведения

4. **Попробуйте другой регион**
   ```yaml
   region: oregon  # Вместо frankfurt
   ```

---

## ✅ Превентивные меры

### Мониторинг
```bash
# Используйте UptimeRobot или аналог
# Проверяйте /health каждые 5 минут
```

### Алерты
```bash
# Настройте в Render:
Settings → Notifications → Webhook
```

### Резервное копирование
```bash
# Регулярно бэкапьте Redis:
# Используйте Redis persistence или экспорт данных
```

---

**Удачи! 🚀**