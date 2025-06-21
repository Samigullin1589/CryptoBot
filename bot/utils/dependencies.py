# Этот модуль действует как общий контейнер для зависимостей,
# доступных во всем приложении.

from typing import Optional
from aiogram import Bot
from bot.services.asic_service import AsicService
from bot.services.news_service import NewsService

# Определяем "пустые" переменные, которые будут заполнены при старте бота
bot: Optional = None
asic_service: Optional = None
news_service: Optional = None