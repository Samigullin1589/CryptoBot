# Используем официальный образ Python 3.11
FROM python:3.11-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Обновляем список пакетов и устанавливаем системные зависимости для Playwright
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk-bridge2.0-0 \
    libcups2 \
    libatspi2.0-0 \
    libdrm2 \
    libgbm1 \
    libasound2 \
    libx11-6 \
    libxext6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    libglib2.0-0 \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл с зависимостями и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем браузер для Playwright
RUN python -m playwright install chromium

# Копируем весь остальной код нашего бота в контейнер
COPY . .

# Указываем команду, которая будет запускать бота
CMD ["python", "-m", "bot.main"]