# =================================================================================
# Файл: bot/handlers/public/crypto_center_handler.py (ВЕРСИЯ "Distinguished Engineer" - ПОЛНОСТЬЮ ИСПРАВЛЕННЫЙ)
# Описание: Полнофункциональный обработчик для раздела "Крипто-Центр".
# ИСПРАВЛЕНИЕ: Переход на использование унифицированных фабрик CallbackData.
# =================================================================================
import logging
from math import ceil
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hlink

from bot.utils.dependencies import Deps
from bot.states.crypto_center_states import CryptoCenterStates
from bot.keyboards.callback_factories import MenuCallback, CryptoCenterCallback
from bot.keyboards.crypto_center_keyboards import (
    get_crypto_center_main_menu_keyboard,
    get_airdrop_list_keyboard,
    get_airdrop_details_keyboard,
    get_mining_alpha_keyboard,
    get_news_feed_keyboard,
    PAGE_SIZE
)

router = Router(name=__name__)
logger = logging.getLogger(__name__)

# --- ТОЧКА ВХОДА И ГЛАВНОЕ МЕНЮ ---

@router.callback_query(MenuCallback.filter(F.action == "crypto_center"))
async def crypto_center_entry(call: types.CallbackQuery, state: FSMContext, deps: Deps):
    """Точка входа в Крипто-Центр из главного меню."""
    await state.clear()
    await state.set_state(CryptoCenterStates.main_menu)
    text = (
        "💎 <b>Крипто-Центр</b>\n\n"
        "Это ваш персональный хаб, где AI-аналитик ищет для вас самые "
        "перспективные возможности на рынке."
    )
    await call.message.edit_text(text, reply_markup=get_crypto_center_main_menu_keyboard())
    await call.answer()

@router.callback_query(CryptoCenterCallback.filter(F.action == "main"))
async def crypto_center_main_menu_callback(call: types.CallbackQuery, state: FSMContext, deps: Deps):
    """Возврат в главное меню Крипто-Центра."""
    await crypto_center_entry(call, state, deps)

# --- СЕКЦИЯ AIRDROP ALPHA ---

@router.callback_query(CryptoCenterCallback.filter(F.action == "airdrops_list"))
async def show_airdrop_list(call: types.CallbackQuery, callback_data: CryptoCenterCallback, state: FSMContext, deps: Deps):
    """Отображает список Airdrop-проектов с пагинацией."""
    page = callback_data.page
    await state.set_state(CryptoCenterStates.viewing_airdrops_list)
    await call.message.edit_text("⏳ Ищу самые горячие Airdrop'ы...")

    projects = await deps.crypto_center_service.get_airdrop_alpha(call.from_user.id)
    if not projects:
        await call.message.edit_text("😕 На данный момент AI не нашел подходящих Airdrop-проектов для вашего профиля.", reply_markup=get_crypto_center_main_menu_keyboard())
        return

    total_pages = ceil(len(projects) / PAGE_SIZE)
    paginated_projects = projects[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

    text = "💎 <b>Airdrop Alpha</b>\n\nAI подобрал для вас список потенциальных Airdrop'ов:"
    keyboard = get_airdrop_list_keyboard(paginated_projects, page, total_pages)
    await call.message.edit_text(text, reply_markup=keyboard)
    await call.answer()

@router.callback_query(CryptoCenterCallback.filter(F.action == "airdrop_view"))
async def show_airdrop_details(call: types.CallbackQuery, callback_data: CryptoCenterCallback, state: FSMContext, deps: Deps):
    """Показывает детальную информацию о проекте и чек-лист."""
    project_id = callback_data.project_id
    user_id = call.from_user.id

    await state.set_state(CryptoCenterStates.viewing_airdrop_details)
    await state.update_data(current_airdrop_id=project_id)

    projects = await deps.crypto_center_service.get_airdrop_alpha(user_id)
    project = next((p for p in projects if p.id == project_id), None)

    if not project:
        await call.answer("❌ Проект не найден. Возможно, список обновился.", show_alert=True)
        return

    completed_tasks = await deps.crypto_center_service.get_user_progress(user_id, project_id)
    tasks_text = "\n".join(f"▪️ {task}" for task in project.tasks)
    text = (
        f"💎 <b>{project.name}</b>\n"
        f"<i>Статус: {project.status}</i>\n\n"
        f"{project.description}\n\n"
        f"<b>Чек-лист для получения дропа:</b>\n{tasks_text}"
    )
    keyboard = get_airdrop_details_keyboard(project, completed_tasks)
    await call.message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)
    await call.answer()

@router.callback_query(CryptoCenterCallback.filter(F.action == "airdrop_task"))
async def toggle_airdrop_task(call: types.CallbackQuery, callback_data: CryptoCenterCallback, state: FSMContext, deps: Deps):
    """Отмечает/снимает отметку о выполнении задачи в чек-листе."""
    project_id, task_index = callback_data.project_id, callback_data.task_index
    user_id = call.from_user.id

    await deps.crypto_center_service.toggle_task_status(user_id, project_id, task_index)

    projects = await deps.crypto_center_service.get_airdrop_alpha(user_id)
    project = next((p for p in projects if p.id == project_id), None)
    if project:
        completed_tasks = await deps.crypto_center_service.get_user_progress(user_id, project_id)
        keyboard = get_airdrop_details_keyboard(project, completed_tasks)
        await call.message.edit_reply_markup(reply_markup=keyboard)

    await call.answer("Статус задачи обновлен.")

# --- СЕКЦИЯ MINING ALPHA ---

@router.callback_query(CryptoCenterCallback.filter(F.action == "mining_list"))
async def show_mining_alpha(call: types.CallbackQuery, callback_data: CryptoCenterCallback, state: FSMContext, deps: Deps):
    """Отображает список майнинг-сигналов."""
    page = callback_data.page
    await state.set_state(CryptoCenterStates.viewing_mining_signals)
    await call.message.edit_text("⏳ Анализирую блокчейн в поисках майнинг-возможностей...")

    signals = await deps.crypto_center_service.get_mining_alpha(call.from_user.id)
    if not signals:
        await call.message.edit_text("😕 AI не обнаружил интересных сигналов для майнинга в данный момент.", reply_markup=get_crypto_center_main_menu_keyboard())
        return

    total_pages = ceil(len(signals) / PAGE_SIZE)
    paginated_signals = signals[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

    signals_text = []
    for signal in paginated_signals:
        guide_link = f" ({hlink(signal.get('guide_url', ''), 'гайд')})" if signal.get('guide_url') else ""
        signals_text.append(
            f"🔹 <b>{signal.get('name', 'N/A')} ({signal.get('algorithm', 'N/A')})</b>{guide_link}\n"
            f"   <i>{signal.get('description', '')}</i>"
        )

    text = "⚙️ <b>Mining Alpha</b>\n\nAI обнаружил следующие возможности:\n\n" + "\n\n".join(signals_text)
    keyboard = get_mining_alpha_keyboard(paginated_signals, page, total_pages)
    await call.message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)
    await call.answer()


# --- СЕКЦИЯ LIVE ЛЕНТА ---

@router.callback_query(CryptoCenterCallback.filter(F.action == "news_list"))
async def show_live_feed(call: types.CallbackQuery, callback_data: CryptoCenterCallback, state: FSMContext, deps: Deps):
    """Отображает live-ленту новостей с AI-суммаризацией."""
    page = callback_data.page
    await state.set_state(CryptoCenterStates.viewing_feed)
    await call.message.edit_text("⏳ Собираю и анализирую последнюю информацию...")

    articles = await deps.crypto_center_service.get_live_feed_with_summary()
    if not articles:
        await call.message.edit_text("😕 Не удалось загрузить новостную ленту. Попробуйте позже.", reply_markup=get_crypto_center_main_menu_keyboard())
        return

    total_pages = ceil(len(articles) / PAGE_SIZE)
    paginated_articles = articles[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

    articles_text = []
    for article in paginated_articles:
        summary = f"\n   <b>AI-суть:</b> <i>{article.ai_summary}</i>" if article.ai_summary else ""
        articles_text.append(f"▪️ {hlink(article.title, article.url)} ({article.source}){summary}")

    text = "📰 <b>Live Лента</b>\n\nСамые важные новости с кратким анализом от AI:\n\n" + "\n\n".join(articles_text)
    keyboard = get_news_feed_keyboard(paginated_articles, page, total_pages)
    await call.message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)
    await call.answer()