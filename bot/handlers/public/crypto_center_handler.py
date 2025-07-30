# =================================================================================
# Файл: bot/handlers/public/crypto_center_handler.py (ВЕРСИЯ "ГЕНИЙ 2.0" - ГОТОВАЯ)
# Описание: Обработчики для интерактивного интерфейса Крипто-Центра.
# =================================================================================

import logging
from math import ceil
from aiogram import Router, F, types
from aiogram.filters import Command

from bot.services.crypto_center_service import CryptoCenterService
from bot.keyboards.crypto_center_keyboards import (
    get_crypto_center_main_menu_keyboard,
    get_airdrop_list_keyboard,
    get_airdrop_details_keyboard,
    get_mining_alpha_keyboard,
    get_news_feed_keyboard,
    CC_CALLBACK_PREFIX
)

logger = logging.getLogger(__name__)
router = Router()
PAGE_SIZE = 5

@router.message(Command("crypto_center"))
@router.callback_query(F.data == f"{CC_CALLBACK_PREFIX}:main")
async def crypto_center_main_menu(message: types.Message | types.CallbackQuery):
    text = ("🧠 <b>Крипто-Центр 2025</b>\n\n"
            "Ваш персональный AI-ассистент в мире криптовалют. "
            "Анализирует новости и ваш профиль интересов, чтобы находить лучшие возможности.")
    keyboard = get_crypto_center_main_menu_keyboard()

    if isinstance(message, types.CallbackQuery):
        await message.message.edit_text(text, reply_markup=keyboard)
        await message.answer()
    else:
        await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith(f"{CC_CALLBACK_PREFIX}:airdrops:list:"))
async def airdrop_list_handler(callback: types.CallbackQuery, crypto_center_service: CryptoCenterService):
    page = int(callback.data.split(":")[-1])
    projects = await crypto_center_service.get_airdrop_alpha(callback.from_user.id)
    
    if not projects:
        text = "💎 <b>Airdrop Alpha</b>\n\nНа основе анализа новостей и вашего профиля, AI пока не нашел подходящих проектов. Загляните позже!"
        keyboard = get_crypto_center_main_menu_keyboard()
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
        return

    total_pages = ceil(len(projects) / PAGE_SIZE)
    start_index = page * PAGE_SIZE
    end_index = start_index + PAGE_SIZE
    
    text = "💎 <b>Airdrop Alpha (Персональная подборка)</b>\n\nНажмите на проект, чтобы увидеть детали и чек-лист задач."
    keyboard = get_airdrop_list_keyboard(projects[start_index:end_index], page, total_pages)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith(f"{CC_CALLBACK_PREFIX}:airdrops:view:"))
async def airdrop_view_handler(callback: types.CallbackQuery, crypto_center_service: CryptoCenterService):
    project_id = callback.data.split(":")[-1]
    projects = await crypto_center_service.get_airdrop_alpha(callback.from_user.id)
    project = next((p for p in projects if p.id == project_id), None)

    if not project:
        await callback.answer("❌ Проект не найден. Возможно, он устарел.", show_alert=True)
        return

    completed_tasks = await crypto_center_service.get_user_progress(callback.from_user.id, project_id)
    
    text = (f"<b>{project.name}</b>\n\n"
            f"<i>{project.description}</i>\n\n"
            f"<b>Статус:</b> {project.status}\n\n"
            "<b>Чек-лист для выполнения:</b>")
    keyboard = get_airdrop_details_keyboard(project, completed_tasks)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith(f"{CC_CALLBACK_PREFIX}:airdrops:task:"))
async def airdrop_task_toggle_handler(callback: types.CallbackQuery, crypto_center_service: CryptoCenterService):
    parts = callback.data.split(":")
    project_id, task_index = parts[-2], int(parts[-1])
    await crypto_center_service.toggle_task_status(callback.from_user.id, project_id, task_index)
    await airdrop_view_handler(callback, crypto_center_service)

@router.callback_query(F.data.startswith(f"{CC_CALLBACK_PREFIX}:mining:list:"))
async def mining_list_handler(callback: types.CallbackQuery, crypto_center_service: CryptoCenterService):
    page = int(callback.data.split(":")[-1])
    signals = await crypto_center_service.get_mining_alpha(callback.from_user.id)

    if not signals:
        text = "⚙️ <b>Mining Alpha</b>\n\nAI пока не нашел интересных возможностей для майнинга. Загляните позже!"
        keyboard = get_crypto_center_main_menu_keyboard()
        await callback.message.edit_text(text, reply_markup=keyboard)
        return

    total_pages = ceil(len(signals) / PAGE_SIZE)
    start_index = page * PAGE_SIZE
    end_index = start_index + PAGE_SIZE
    paginated_signals = signals[start_index:end_index]

    text = "⚙️ <b>Mining Alpha (Персональная подборка)</b>\n\nСигналы и возможности, найденные AI на основе новостей:"
    for signal in paginated_signals:
        text += f"\n\n🔹 <b>{signal['name']}</b>\n{signal['description']}\n<i>Железо: {signal['hardware']}</i>"

    keyboard = get_mining_alpha_keyboard(paginated_signals, page, total_pages)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith(f"{CC_CALLBACK_PREFIX}:news:list:"))
async def news_list_handler(callback: types.CallbackQuery, crypto_center_service: CryptoCenterService):
    page = int(callback.data.split(":")[-1])
    articles = await crypto_center_service.get_live_feed_with_summary()

    if not articles:
        text = "📰 <b>Live Лента</b>\n\nНовостей пока нет."
        keyboard = get_crypto_center_main_menu_keyboard()
        await callback.message.edit_text(text, reply_markup=keyboard)
        return

    total_pages = ceil(len(articles) / PAGE_SIZE)
    start_index = page * PAGE_SIZE
    end_index = start_index + PAGE_SIZE
    
    text = "📰 <b>Live Лента (с AI-обзором)</b>\n"
    for article in articles[start_index:end_index]:
        text += f"\n\n<a href='{article.url}'><b>{article.title}</b></a>\n"
        if article.ai_summary:
            text += f"<i>AI-кратко: {article.ai_summary}</i>"
        else:
            text += f"<i>{article.body[:150]}...</i>"
    
    keyboard = get_news_feed_keyboard(articles, page, total_pages)
    await callback.message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)
    await callback.answer()