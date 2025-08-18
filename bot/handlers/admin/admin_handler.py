from __future__ import annotations

import contextlib
import logging

from aiogram import Router, types as tg
from aiogram.filters import Command

router = Router(name=__name__)
log = logging.getLogger(__name__)


# ---------- utils ----------


async def _resolve_target_id(bot, message: tg.Message) -> int | None:
    """
    Пытается получить целевой user_id:
      1) reply_to_message.from_user.id
      2) entity 'text_mention' (там уже есть id)
      3) аргумент-число (user_id)
      4) @username -> bot.get_chat('@username') (сработает, если юзер писал боту/в чате)
    """
    # 1) reply
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id

    text = message.text or ""
    entities = message.entities or []

    # 2) text_mention
    for ent in entities:
        if ent.type == "text_mention" and ent.user:
            return ent.user.id

    # 3) number id
    parts = text.split()
    if len(parts) >= 2:
        candidate = parts[1].strip()
        if candidate.isdigit() or (
            candidate.startswith("-") and candidate[1:].isdigit()
        ):
            try:
                return int(candidate)
            except Exception:
                pass
        # 4) @username
        if candidate.startswith("@"):
            with contextlib.suppress(Exception):
                chat = await bot.get_chat(candidate)
                if chat and chat.id:
                    return chat.id

    return None


def _is_admin(user_id: int, chat_member: tg.ChatMember) -> bool:
    status = getattr(chat_member, "status", "")
    return status in ("creator", "administrator")


# ---------- commands ----------


@router.message(Command("ban"))
async def cmd_ban(m: tg.Message, **data) -> None:
    bot = m.bot
    deps = data.get("deps")
    chat = m.chat
    if not chat:
        return

    # проверка, что команду дал админ
    member = await bot.get_chat_member(chat.id, m.from_user.id)
    if not _is_admin(m.from_user.id, member):
        await m.reply("⛔ Только администраторы могут банить.")
        return

    target_id = await _resolve_target_id(bot, m)
    if target_id is None:
        await m.reply(
            "⚠️ Эту команду лучше использовать в ответ на сообщение пользователя или укажите @username/ID."
        )
        return

    with contextlib.suppress(Exception):
        await bot.ban_chat_member(chat_id=chat.id, user_id=target_id)

    # сбросим счётчики безопасности
    if getattr(deps, "security_service", None):
        with contextlib.suppress(Exception):
            await deps.security_service.pardon_user(m.from_user.id, target_id, chat.id)

    await m.reply(f"⛔ Пользователь <code>{target_id}</code> заблокирован.")


@router.message(Command("unban"))
async def cmd_unban(m: tg.Message) -> None:
    bot = m.bot
    chat = m.chat
    if not chat:
        return
    member = await bot.get_chat_member(chat.id, m.from_user.id)
    if not _is_admin(m.from_user.id, member):
        await m.reply("⛔ Только администраторы.")
        return
    target_id = await _resolve_target_id(bot, m)
    if target_id is None:
        await m.reply("Укажите @username/ID или ответьте на сообщение.")
        return
    with contextlib.suppress(Exception):
        await bot.unban_chat_member(chat.id, target_id, only_if_banned=True)
    await m.reply(f"✅ Разбанил <code>{target_id}</code>.")


@router.message(Command("mute"))
async def cmd_mute(m: tg.Message) -> None:
    bot = m.bot
    chat = m.chat
    if not chat:
        return
    member = await bot.get_chat_member(chat.id, m.from_user.id)
    if not _is_admin(m.from_user.id, member):
        await m.reply("⛔ Только администраторы.")
        return

    parts = (m.text or "").split()
    minutes = 60
    if len(parts) >= 2 and parts[1].isdigit():
        minutes = max(1, int(parts[1]))
        # для target сдвигаем индекс
        parts = [parts[0]] + parts[2:]
        m.text = " ".join(parts)  # чтобы _resolve_target_id прочитал @username/ID

    target_id = await _resolve_target_id(bot, m)
    if target_id is None:
        await m.reply("Укажите @username/ID или ответьте на сообщение.")
        return

    until_date = tg.utils.datetime.datetime.now(
        tg.utils.datetime.timezone.utc
    ) + tg.utils.timedelta(minutes=minutes)
    with contextlib.suppress(Exception):
        await bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=target_id,
            permissions=tg.ChatPermissions(can_send_messages=False),
            until_date=until_date,
        )
    await m.reply(
        f"🔇 Пользователь <code>{target_id}</code> заглушен на {minutes} мин."
    )


@router.message(Command("warn"))
async def cmd_warn(m: tg.Message, **data) -> None:
    bot = m.bot
    deps = data.get("deps")
    chat = m.chat
    if not chat:
        return
    member = await bot.get_chat_member(chat.id, m.from_user.id)
    if not _is_admin(m.from_user.id, member):
        await m.reply("⛔ Только администраторы.")
        return
    target_id = await _resolve_target_id(bot, m)
    if target_id is None:
        await m.reply("Укажите @username/ID или ответьте на сообщение.")
        return
    if getattr(deps, "security_service", None):
        with contextlib.suppress(Exception):
            await deps.security_service.register_violation(
                target_id, chat.id, reason="manual_warn", weight=1
            )
    await m.reply(f"⚠️ Вынесено предупреждение <code>{target_id}</code>.")


@router.message(Command("pardon"))
async def cmd_pardon(m: tg.Message, **data) -> None:
    bot = m.bot
    deps = data.get("deps")
    chat = m.chat
    if not chat:
        return
    member = await bot.get_chat_member(chat.id, m.from_user.id)
    if not _is_admin(m.from_user.id, member):
        await m.reply("⛔ Только администраторы.")
        return
    target_id = await _resolve_target_id(bot, m)
    if target_id is None:
        await m.reply("Укажите @username/ID или ответьте на сообщение.")
        return
    if getattr(deps, "security_service", None):
        with contextlib.suppress(Exception):
            await deps.security_service.pardon_user(m.from_user.id, target_id, chat.id)
    await m.reply(f"🕊 Счётчики нарушений для <code>{target_id}</code> очищены.")
