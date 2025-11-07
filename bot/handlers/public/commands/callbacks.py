# bot/handlers/public/commands/callbacks.py
"""
Обработчики callback-запросов от inline кнопок.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from loguru import logger

router = Router(name="callbacks_router")


@router.callback_query(F.data.startswith("settings_"))
async def handle_settings_callbacks(callback: CallbackQuery):
    """Обработка callback-ов из меню настроек"""
    await callback.answer("Функция в разработке! 🔧")
    logger.debug(f"Settings callback: {callback.data} from user {callback.from_user.id}")


@router.callback_query(F.data.startswith("feedback_"))
async def handle_feedback_callbacks(callback: CallbackQuery):
    """Обработка callback-ов из меню обратной связи"""
    await callback.answer("Напишите ваше сообщение в следующем сообщении")
    logger.debug(f"Feedback callback: {callback.data} from user {callback.from_user.id}")


@router.callback_query(F.data.startswith("invite_"))
async def handle_invite_callbacks(callback: CallbackQuery):
    """Обработка callback-ов реферальной программы"""
    await callback.answer("Статистика обновлена! 📊")
    logger.debug(f"Invite callback: {callback.data} from user {callback.from_user.id}")


@router.callback_query(F.data.startswith("premium_"))
async def handle_premium_callbacks(callback: CallbackQuery):
    """Обработка callback-ов премиум подписки"""
    await callback.answer("Переход к оплате... 💳")
    logger.debug(f"Premium callback: {callback.data} from user {callback.from_user.id}")


@router.callback_query(F.data.startswith("donate_"))
async def handle_donate_callbacks(callback: CallbackQuery):
    """Обработка callback-ов донатов"""
    await callback.answer("Реквизиты скопированы! 📋")
    logger.debug(f"Donate callback: {callback.data} from user {callback.from_user.id}")


@router.callback_query(F.data.startswith("events_"))
async def handle_events_callbacks(callback: CallbackQuery):
    """Обработка callback-ов событий"""
    await callback.answer("Загрузка событий... 🎮")
    logger.debug(f"Events callback: {callback.data} from user {callback.from_user.id}")


@router.callback_query(F.data.startswith("calc_"))
async def handle_calc_callbacks(callback: CallbackQuery):
    """Обработка callback-ов калькулятора"""
    await callback.answer("Введите параметры для расчёта")
    logger.debug(f"Calculator callback: {callback.data} from user {callback.from_user.id}")


@router.callback_query(F.data.startswith("profile_"))
async def handle_profile_callbacks(callback: CallbackQuery):
    """Обработка callback-ов профиля"""
    await callback.answer("Данные обновлены! ✅")
    logger.debug(f"Profile callback: {callback.data} from user {callback.from_user.id}")


@router.callback_query(F.data.startswith("leaderboard_"))
async def handle_leaderboard_callbacks(callback: CallbackQuery):
    """Обработка callback-ов таблицы лидеров"""
    await callback.answer("Обновление рейтинга... 🔄")
    logger.debug(f"Leaderboard callback: {callback.data} from user {callback.from_user.id}")


@router.callback_query(F.data.startswith("faq_"))
async def handle_faq_callbacks(callback: CallbackQuery):
    """Обработка callback-ов FAQ"""
    await callback.answer("Загрузка раздела FAQ...")
    logger.debug(f"FAQ callback: {callback.data} from user {callback.from_user.id}")


@router.callback_query(F.data == "show_faq")
async def handle_show_faq(callback: CallbackQuery):
    """Показать FAQ"""
    from bot.handlers.public.commands.info import handle_faq
    await callback.message.delete()
    await handle_faq(callback.message)
    await callback.answer()


@router.callback_query(F.data == "show_support")
async def handle_show_support(callback: CallbackQuery):
    """Показать поддержку"""
    from bot.handlers.public.commands.technical import handle_support
    await callback.message.delete()
    await handle_support(callback.message)
    await callback.answer()


@router.callback_query(F.data.startswith("support_"))
async def handle_support_callbacks(callback: CallbackQuery):
    """Обработка callback-ов поддержки"""
    await callback.answer("Связываемся с поддержкой... 📞")
    logger.debug(f"Support callback: {callback.data} from user {callback.from_user.id}")