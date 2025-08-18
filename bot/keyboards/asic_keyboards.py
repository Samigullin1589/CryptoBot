# ===============================================================
# Файл: bot/keyboards/asic_keyboards.py
# Описание: Генераторы клавиатур для раздела ASIC-майнеров.
# ИСПРАВЛЕНИЕ: Переход на использование фабрик CallbackData.
# ===============================================================

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.utils.models import AsicMiner
from bot.utils.text_utils import normalize_asic_name
from .callback_factories import AsicCallback, MenuCallback

PAGE_SIZE = 5


def get_top_asics_keyboard(asics: list[AsicMiner], page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start_offset = (page - 1) * PAGE_SIZE
    end_offset = start_offset + PAGE_SIZE

    for asic in asics[start_offset:end_offset]:
        asic_id = normalize_asic_name(asic.name)
        builder.button(
            text=f"{asic.name} - ${asic.net_profit:.2f}/день",
            callback_data=AsicCallback(action="passport", asic_id=asic_id).pack(),
        )

    nav_row = []
    if page > 1:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=AsicCallback(action="page", page=page - 1).pack(),
            )
        )
    if end_offset < len(asics):
        nav_row.append(
            InlineKeyboardButton(
                text="Вперед ➡️",
                callback_data=AsicCallback(action="page", page=page + 1).pack(),
            )
        )

    if nav_row:
        builder.row(*nav_row)

    builder.row(
        InlineKeyboardButton(
            text="💡 Указать цену э/э",
            callback_data=AsicCallback(action="set_cost").pack(),
        ),
        InlineKeyboardButton(
            text="⬅️ В меню", callback_data=MenuCallback(level=0, action="main").pack()
        ),
    )

    builder.adjust(1)
    return builder.as_markup()


def get_asic_passport_keyboard(page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="⬅️ Назад к списку",
        callback_data=AsicCallback(action="page", page=page).pack(),
    )
    return builder.as_markup()
