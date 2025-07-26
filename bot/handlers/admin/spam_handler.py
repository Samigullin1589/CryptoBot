# ===============================================================
# Файл: bot/handlers/admin/spam_handler.py (v4 - Финальная)
# Описание: Единый модуль для модерации и антиспама.
# Все команды имеют префикс "!" и обладают полным функционалом.
# ===============================================================
import re
import logging
from datetime import timedelta, datetime

from aiogram import Router, F, Bot, types
from aiogram.filters import Command
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest

from bot.services.user_service import UserService
from bot.services.ai_service import AIService
from bot.filters.admin_filter import IsAdminFilter
from bot.utils.helpers import sanitize_html

admin_spam_router = Router()
logger = logging.getLogger(__name__)

# Ограничиваем все хендлеры в этом роутере:
# 1. Они будут работать только в группах и супергруппах.
# 2. Они будут доступны только администраторам бота.
admin_spam_router.message.filter(
    F.chat.type.in_({'group', 'supergroup'}),
    IsAdminFilter()
)

def parse_duration(text: str) -> timedelta | None:
    match = re.match(r"(\d+)([mhd])", text.lower())
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2)
    if unit == 'm': return timedelta(minutes=value)
    if unit == 'h': return timedelta(hours=value)
    if unit == 'd': return timedelta(days=value)
    return None

# --- ХЕНДЛЕРЫ ДЛЯ МОДЕРАЦИИ И АНТИСПАМА ---

@admin_spam_router.message(Command("ban", "бан", prefix="!/"))
async def handle_ban_user(message: types.Message, bot: Bot, user_service: UserService, ai_service: AIService):
    """
    Ультимативная команда бана: банит, удаляет ВСЕ сообщения, обучает AI, уведомляет.
    """
    if not message.reply_to_message:
        await message.reply("⚠️ Эту команду нужно использовать в ответ на сообщение нарушителя.")
        return

    # --- Сбор данных ---
    target_user = message.reply_to_message.from_user
    spam_message_to_learn = message.reply_to_message
    admin_user = message.from_user
    reason = "Нарушение правил чата."
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        reason = args[1]

    # --- Проверка цели ---
    try:
        target_member = await bot.get_chat_member(message.chat.id, target_user.id)
        if target_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
            await message.reply("😅 Нельзя забанить администратора чата.")
            return
    except TelegramBadRequest:
        pass # OK

    # --- Основная логика ---
    try:
        # 1. Бан с удалением всех сообщений пользователя
        await bot.ban_chat_member(
            chat_id=message.chat.id,
            user_id=target_user.id,
            revoke_messages=True
        )
        
        # 2. Обучение AI на конкретном сообщении
        await ai_service.learn_from_spam(spam_message_to_learn)
        
        # 3. Обновление статуса в нашей БД
        await user_service.update_user_status(user_id=target_user.id, chat_id=message.chat.id, is_banned=True)
        logger.info(f"Admin {admin_user.id} banned {target_user.id} and revoked all messages. Reason: {reason}")
        
        # 4. Уведомление в ЛС (попытка)
        try:
            chat_info = await bot.get_chat(message.chat.id)
            notification_text = (
                f"❗️ Вы были забанены в чате «<b>{sanitize_html(chat_info.title)}</b>».\n\n"
                f"<b>Причина:</b> {sanitize_html(reason)}"
            )
            await bot.send_message(target_user.id, notification_text)
        except Exception as e:
            logger.warning(f"Failed to notify user {target_user.id} about ban: {e}")

        # 5. Публичное уведомление в чате
        target_link = f"<a href='tg://user?id={target_user.id}'>{sanitize_html(target_user.full_name)}</a>"
        public_text = (
            f"Пользователь {target_link} заблокирован.\n\n"
            f"<b>Причина:</b> {sanitize_html(reason)}\n\n"
            "<i>Все сообщения пользователя в этом чате удалены.</i>"
        )
        await bot.send_message(message.chat.id, public_text)

        # 6. Удаление команды администратора
        await message.delete()

    except Exception as e:
        logger.error(f"Failed to ban user {target_user.id}: {e}", exc_info=True)
        await message.reply(f"❌ Не удалось забанить пользователя. Ошибка: {e}")

@admin_spam_router.message(Command("unban", "разбан", prefix="!/"))
async def handle_unban_user(message: types.Message, bot: Bot):
    """
    Универсальная команда разбана. Работает по ID или по ответу.
    """
    target_id = None
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    else:
        args = message.text.split()
        if len(args) > 1 and args[1].isdigit():
            target_id = int(args[1])
    
    if not target_id:
        await message.reply("⚠️ Укажите пользователя: ответьте на сообщение или введите <code>!unban [user_id]</code>.")
        return
        
    try:
        await bot.unban_chat_member(chat_id=message.chat.id, user_id=target_id)
        logger.info(f"Admin {message.from_user.id} unbanned user {target_id} in chat {message.chat.id}")
        await message.reply(f"✅ Пользователь с ID <code>{target_id}</code> был разбанен.")
    except TelegramBadRequest as e:
        if "user not found" in e.message:
            await message.reply("ℹ️ Пользователь не найден в списке забаненных этого чата.")
        else:
            logger.error(f"Failed to unban user: {e}")
            await message.reply(f"❌ Произошла ошибка при попытке разбана: {e.message}")
    except Exception as e:
        logger.error(f"An unexpected error occurred in unban_user: {e}", exc_info=True)
        await message.reply("❌ Произошла непредвиденная ошибка.")


@admin_spam_router.message(Command("warn", "пред", prefix="!/"))
async def handle_warn_user(message: types.Message, bot: Bot, user_service: UserService):
    if not message.reply_to_message:
        await message.reply("⚠️ Эту команду нужно использовать в ответ на сообщение пользователя.")
        return

    target_user = message.reply_to_message.from_user
    admin_user = message.from_user
    reason = "Нарушение правил."
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        reason = args[1]
    
    try:
        penalty = 15
        await user_service.log_violation(
            user_id=target_user.id, 
            chat_id=message.chat.id,
            reason=f"Предупреждение от {admin_user.id}: {reason}",
            penalty=penalty
        )
        updated_profile = await user_service.get_user_profile(target_user.id, message.chat.id)
        
        admin_link = f"<a href='tg://user?id={admin_user.id}'>{sanitize_html(admin_user.full_name)}</a>"
        target_link = f"<a href='tg://user?id={target_user.id}'>{sanitize_html(target_user.full_name)}</a>"
        
        public_text = (
            f"❗️ Администратор {admin_link} вынес предупреждение пользователю {target_link}.\n\n"
            f"<b>Причина:</b> {sanitize_html(reason)}\n"
            f"📉 Рейтинг доверия снижен. Текущий рейтинг: <b>{updated_profile.trust_score}</b>."
        )
        
        await message.reply_to_message.delete()
        await message.delete()
        await bot.send_message(message.chat.id, public_text)
        logger.info(f"Admin {admin_user.id} warned {target_user.id}. Reason: {reason}")
        
    except Exception as e:
        logger.error(f"Failed to warn user {target_user.id}: {e}", exc_info=True)
        await message.reply(f"❌ Не удалось вынести предупреждение. Ошибка: {e}")

@admin_spam_router.message(Command("mute", "мут", prefix="!/"))
async def handle_mute_user(message: types.Message, bot: Bot):
    if not message.reply_to_message:
        await message.reply("⚠️ Эту команду нужно использовать в ответ на сообщение пользователя.")
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.reply("⚠️ Укажите длительность мута. Например: <code>!mute 30m Причина</code>")
        return
        
    duration = parse_duration(args[1])
    if not duration:
        await message.reply("⚠️ Неверный формат времени. Используйте 'm', 'h', 'd'.")
        return

    reason = "Нарушение правил."
    if len(args) > 2:
        reason = args[2]

    target_user = message.reply_to_message.from_user
    admin_user = message.from_user
    mute_end_timestamp = datetime.now() + duration

    try:
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=target_user.id,
            permissions=types.ChatPermissions(),
            until_date=mute_end_timestamp
        )
        
        admin_link = f"<a href='tg://user?id={admin_user.id}'>{sanitize_html(admin_user.full_name)}</a>"
        target_link = f"<a href='tg://user?id={target_user.id}'>{sanitize_html(target_user.full_name)}</a>"

        public_text = (
            f"🔇 Пользователь {target_link} был замучен администратором {admin_link} до {mute_end_timestamp.strftime('%Y-%m-%d %H:%M')}.\n\n"
            f"<b>Причина:</b> {sanitize_html(reason)}"
        )

        await message.reply_to_message.delete()
        await message.delete()
        await bot.send_message(message.chat.id, public_text)
        logger.info(f"Admin {admin_user.id} muted {target_user.id} for {duration}. Reason: {reason}")

    except Exception as e:
        logger.error(f"Failed to mute user {target_user.id}: {e}", exc_info=True)
        await message.reply(f"❌ Не удалось замутить пользователя. Ошибка: {e}")

@admin_spam_router.message(Command("unmute", "размут", prefix="!/"))
async def handle_unmute_user_command(message: types.Message, bot: Bot, user_service: UserService):
    if not message.reply_to_message:
        await message.reply("⚠️ Эту команду нужно использовать в ответ на сообщение пользователя.")
        return

    target_user = message.reply_to_message.from_user
    try:
        chat = await bot.get_chat(message.chat.id)
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=target_user.id,
            permissions=chat.permissions
        )
        await user_service.update_user_mute(user_id=target_user.id, chat_id=message.chat.id, mute_until=0)
        await message.delete()
        await message.answer(f"✅ С пользователя {sanitize_html(target_user.full_name)} сняты ограничения.")
    except Exception as e:
        logger.error(f"Failed to unmute user {target_user.id}: {e}")
        await message.reply(f"❌ Не удалось снять ограничения. Ошибка: {e}")

# --- Управление стоп-словами ---
@admin_spam_router.message(Command("add_stop_word", prefix="!/"))
async def handle_add_stop_word(message: types.Message, ai_service: AIService):
    command_args = message.text.split(maxsplit=1)
    if len(command_args) < 2:
        await message.reply("⚠️ Укажите слово. Например: <code>!add_stop_word казино</code>")
        return
    word = command_args[1].lower().strip()
    success = await ai_service.add_stop_word(word)
    if success:
        await message.reply(f"✅ Слово '<code>{word}</code>' добавлено в стоп-лист.")
    else:
        await message.reply(f"⚠️ Слово '<code>{word}</code>' уже было в стоп-листе.")

@admin_spam_router.message(Command("del_stop_word", prefix="!/"))
async def handle_delete_stop_word(message: types.Message, ai_service: AIService):
    command_args = message.text.split(maxsplit=1)
    if len(command_args) < 2:
        await message.reply("⚠️ Укажите слово для удаления.")
        return
    word = command_args[1].lower().strip()
    success = await ai_service.remove_stop_word(word)
    if success:
        await message.reply(f"✅ Слово '<code>{word}</code>' удалено.")
    else:
        await message.reply(f"⚠️ Слово '<code>{word}</code>' не найдено в стоп-листе.")

@admin_spam_router.message(Command("list_stop_words", prefix="!/"))
async def handle_list_stop_words(message: types.Message, ai_service: AIService):
    words = await ai_service.get_all_stop_words()
    if not words:
        await message.reply("🚫 Стоп-лист пуст.")
        return
    text = "📜 Текущие стоп-слова:\n\n" + "\n".join([f"• <code>{word}</code>" for word in words])
    await message.reply(text)
