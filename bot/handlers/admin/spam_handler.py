# ===============================================================
# Файл: bot/handlers/admin/spam_handler.py (v7 - Фикс удаления)
# Описание: Улучшена логика удаления команды администратора,
# чтобы избежать проблем с race condition.
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

# Фильтры применяются к каждой команде индивидуально
def parse_duration(text: str) -> timedelta | None:
    match = re.match(r"(\d+)([mhd])", text.lower())
    if not match: return None
    value, unit = int(match.group(1)), match.group(2)
    if unit == 'm': return timedelta(minutes=value)
    if unit == 'h': return timedelta(hours=value)
    if unit == 'd': return timedelta(days=value)
    return None

@admin_spam_router.message(Command("ban", "бан", prefix="!/"), IsAdminFilter())
async def handle_ban_user(message: types.Message, bot: Bot, user_service: UserService, ai_service: AIService):
    """
    Универсальная команда бана.
    - В группе (ответом): !ban [причина]
    - Из ЛС или в группе: !ban <chat_id> <user_id> [причина]
    """
    admin_user = message.from_user
    target_user_id: int | None = None
    target_chat_id: int | None = None
    reason = "Нарушение правил чата."
    spam_message_to_learn: types.Message | None = None

    # --- Определение режима работы ---
    if message.reply_to_message and message.chat.type != 'private':
        # <<< ИЗМЕНЕНИЕ: Сначала пытаемся удалить команду админа >>>
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"Could not delete admin's command message {message.message_id}: {e}")
            try:
                await bot.send_message(admin_user.id, f"ℹ️ Не удалось удалить вашу команду <code>!ban</code> в чате. Возможно, у меня недостаточно прав или прошло слишком много времени.")
            except Exception:
                pass # Если не можем уведомить, ничего страшного
        # <<< КОНЕЦ ИЗМЕНЕНИЯ >>>

        target_user_id = message.reply_to_message.from_user.id
        target_chat_id = message.chat.id
        spam_message_to_learn = message.reply_to_message
        args = message.text.split(maxsplit=1)
        if len(args) > 1: reason = args[1]

    else: # Режим бана из ЛС
        args = message.text.split()[1:]
        if len(args) < 2:
            await message.reply("⚠️ Неверный формат. Используйте:\n- В группе (ответом): <code>!ban [причина]</code>\n- Из ЛС: <code>!ban [chat_id] [user_id] [причина]</code>")
            return
        chat_id_str, user_id_str = args[0], args[1]
        if not (chat_id_str.replace('-', '').isdigit() and user_id_str.isdigit()):
            await message.reply("⚠️ Chat ID и User ID должны быть числами.")
            return
        target_chat_id, target_user_id = int(chat_id_str), int(user_id_str)
        if len(args) > 2: reason = " ".join(args[2:])

    # --- Проверка прав бота ---
    try:
        bot_member = await bot.get_chat_member(target_chat_id, bot.id)
        if not bot_member.status == ChatMemberStatus.ADMINISTRATOR or not bot_member.can_restrict_members:
            await message.reply(f"❌ Я не администратор в чате <code>{target_chat_id}</code> или у меня нет права банить.")
            return
        can_delete = bot_member.can_delete_messages
    except Exception as e:
        logger.error(f"Could not get bot status in chat {target_chat_id}: {e}")
        await message.reply(f"❌ Не удалось проверить мой статус в чате <code>{target_chat_id}</code>.")
        return

    # --- Проверка цели ---
    try:
        target_member = await bot.get_chat_member(target_chat_id, target_user_id)
        if target_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
            await message.reply("😅 Нельзя забанить администратора чата.")
            return
    except TelegramBadRequest as e:
        if "user not found" in e.message.lower(): pass
        else: raise e

    # --- Основные действия ---
    try:
        await bot.ban_chat_member(chat_id=target_chat_id, user_id=target_user_id, revoke_messages=True)
        
        if spam_message_to_learn: await ai_service.learn_from_spam(spam_message_to_learn)
        
        await user_service.update_user_status(user_id=target_user_id, chat_id=target_chat_id, is_banned=True)
        logger.info(f"Admin {admin_user.id} banned {target_user_id} in chat {target_chat_id}. Reason: {reason}")
        
        try:
            chat_info = await bot.get_chat(target_chat_id)
            await bot.send_message(target_user_id, f"❗️ Вы были забанены в чате «<b>{sanitize_html(chat_info.title)}</b>».\n\n<b>Причина:</b> {sanitize_html(reason)}")
        except Exception:
            logger.warning(f"Failed to notify user {target_user_id} about ban.")

        try:
            user_info = await bot.get_chat(target_user_id)
            target_link = f"<a href='tg://user?id={user_info.id}'>{sanitize_html(user_info.full_name or f'User {user_info.id}')}</a>"
        except Exception:
            target_link = f"Пользователь с ID <code>{target_user_id}</code>"
        
        if can_delete:
            deletion_info = "<i>Последние сообщения пользователя в этом чате были удалены.</i>"
        else:
            deletion_info = "<i>У меня нет прав на удаление сообщений, поэтому они остались в чате.</i>"

        public_text = (
            f"Пользователь {target_link} заблокирован.\n\n"
            f"<b>Причина:</b> {sanitize_html(reason)}\n\n"
            f"{deletion_info}"
        )
        await bot.send_message(target_chat_id, public_text)

        if message.chat.type == 'private':
            await message.reply(f"✅ Пользователь <code>{target_user_id}</code> успешно забанен в чате <code>{target_chat_id}</code>.")

    except Exception as e:
        logger.error(f"Failed to ban user {target_user_id}: {e}", exc_info=True)
        await message.reply(f"❌ Не удалось забанить пользователя. Ошибка: {e}")

# --- ОСТАЛЬНЫЕ КОМАНДЫ (РАБОТАЮТ ТОЛЬКО В ГРУППАХ) ---
GROUP_ONLY_FILTER = F.chat.type.in_({'group', 'supergroup'})

@admin_spam_router.message(Command("unban", "разбан", prefix="!/"), IsAdminFilter(), GROUP_ONLY_FILTER)
async def handle_unban_user(message: types.Message, bot: Bot):
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
            await message.reply(f"❌ Ошибка при разбане: {e.message}")

@admin_spam_router.message(Command("warn", "пред", prefix="!/"), IsAdminFilter(), GROUP_ONLY_FILTER)
async def handle_warn_user_command(message: types.Message, bot: Bot, user_service: UserService):
    if not message.reply_to_message:
        await message.reply("⚠️ Эту команду нужно использовать в ответ на сообщение пользователя.")
        return
    
    try:
        await message.delete()
    except Exception: pass

    target_user, admin_user = message.reply_to_message.from_user, message.from_user
    reason = "Нарушение правил."
    args = message.text.split(maxsplit=1)
    if len(args) > 1: reason = args[1]
    await user_service.log_violation(user_id=target_user.id, chat_id=message.chat.id, reason=f"Предупреждение от {admin_user.id}: {reason}", penalty=15)
    updated_profile = await user_service.get_user_profile(target_user.id, message.chat.id)
    admin_link, target_link = f"<a href='tg://user?id={admin_user.id}'>{sanitize_html(admin_user.full_name)}</a>", f"<a href='tg://user?id={target_user.id}'>{sanitize_html(target_user.full_name)}</a>"
    public_text = f"❗️ Администратор {admin_link} вынес предупреждение пользователю {target_link}.\n\n<b>Причина:</b> {sanitize_html(reason)}\n📉 Рейтинг доверия снижен. Текущий рейтинг: <b>{updated_profile.trust_score}</b>."
    await bot.send_message(message.chat.id, public_text)
    await message.reply_to_message.delete()


@admin_spam_router.message(Command("mute", "мут", prefix="!/"), IsAdminFilter(), GROUP_ONLY_FILTER)
async def handle_mute_user_command(message: types.Message, bot: Bot):
    if not message.reply_to_message:
        await message.reply("⚠️ Эту команду нужно использовать в ответ на сообщение пользователя.")
        return
    
    try:
        await message.delete()
    except Exception: pass
        
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.answer("⚠️ Укажите длительность мута. Например: <code>!mute 30m Причина</code>")
        return
    duration = parse_duration(args[1])
    if not duration:
        await message.answer("⚠️ Неверный формат времени. Используйте 'm', 'h', 'd'.")
        return
    reason = "Нарушение правил."
    if len(args) > 2: reason = args[2]
    target_user, admin_user = message.reply_to_message.from_user, message.from_user
    mute_end_timestamp = datetime.now() + duration
    await bot.restrict_chat_member(chat_id=message.chat.id, user_id=target_user.id, permissions=types.ChatPermissions(), until_date=mute_end_timestamp)
    admin_link, target_link = f"<a href='tg://user?id={admin_user.id}'>{sanitize_html(admin_user.full_name)}</a>", f"<a href='tg://user?id={target_user.id}'>{sanitize_html(target_user.full_name)}</a>"
    public_text = f"🔇 Пользователь {target_link} был замучен администратором {admin_link} до {mute_end_timestamp.strftime('%Y-%m-%d %H:%M')}.\n\n<b>Причина:</b> {sanitize_html(reason)}"
    await bot.send_message(message.chat.id, public_text)
    await message.reply_to_message.delete()


@admin_spam_router.message(Command("unmute", "размут", prefix="!/"), IsAdminFilter(), GROUP_ONLY_FILTER)
async def handle_unmute_user_command(message: types.Message, bot: Bot, user_service: UserService):
    if not message.reply_to_message:
        await message.reply("⚠️ Эту команду нужно использовать в ответ на сообщение пользователя.")
        return
    target_user = message.reply_to_message.from_user
    chat = await bot.get_chat(message.chat.id)
    await bot.restrict_chat_member(chat_id=message.chat.id, user_id=target_user.id, permissions=chat.permissions)
    await user_service.update_user_mute(user_id=target_user.id, chat_id=message.chat.id, mute_until=0)
    await message.delete()
    await message.answer(f"✅ С пользователя {sanitize_html(target_user.full_name)} сняты ограничения.")


@admin_spam_router.message(Command("add_stop_word", prefix="!/"), IsAdminFilter())
async def handle_add_stop_word_command(message: types.Message, ai_service: AIService):
    command_args = message.text.split(maxsplit=1)
    if len(command_args) < 2:
        await message.reply("⚠️ Укажите слово. Например: <code>!add_stop_word казино</code>")
        return
    word = command_args[1].lower().strip()
    success = await ai_service.add_stop_word(word)
    if success: await message.reply(f"✅ Слово '<code>{word}</code>' добавлено в стоп-лист.")
    else: await message.reply(f"⚠️ Слово '<code>{word}</code>' уже было в стоп-листе.")


@admin_spam_router.message(Command("del_stop_word", prefix="!/"), IsAdminFilter())
async def handle_delete_stop_word_command(message: types.Message, ai_service: AIService):
    command_args = message.text.split(maxsplit=1)
    if len(command_args) < 2:
        await message.reply("⚠️ Укажите слово для удаления.")
        return
    word = command_args[1].lower().strip()
    success = await ai_service.remove_stop_word(word)
    if success: await message.reply(f"✅ Слово '<code>{word}</code>' удалено.")
    else: await message.reply(f"⚠️ Слово '<code>{word}</code>' не найдено в стоп-листе.")


@admin_spam_router.message(Command("list_stop_words", prefix="!/"), IsAdminFilter())
async def handle_list_stop_words_command(message: types.Message, ai_service: AIService):
    words = await ai_service.get_all_stop_words()
    if not words:
        await message.reply("🚫 Стоп-лист пуст.")
        return
    text = "📜 Текущие стоп-слова:\n\n" + "\n".join([f"• <code>{word}</code>" for word in words])
    await message.reply(text)
