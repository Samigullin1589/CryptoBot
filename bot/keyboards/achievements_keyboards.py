# =================================================================================
# Файл: bot/keyboards/achievements_keyboards.py (ВЕРСИЯ "ГЕНИЙ 2.0" - ОКОНЧАТЕЛЬНАЯ)
# Описание: Клавиатуры для отображения достижений.
# =================================================================================
from typing import List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.utils.models import Achievement

def get_achievements_list_keyboard(all_achievements: List[Achievement], unlocked_ids: set) -> InlineKeyboardMarkup:
    """Создает клавиатуру со списком всех достижений и отмечает разблокированные."""
    buttons = []
    for ach in sorted(all_achievements, key=lambda x: x.id):
        icon = "🏆" if ach.id in unlocked_ids else "🔒"
        text = f"{icon} {ach.name}"
        # Для простоты делаем некликабельными, но можно добавить callback для показа описания
        buttons.append([InlineKeyboardButton(text=text, callback_data="do_nothing")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)