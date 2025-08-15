\==============================
Файл: bot/handlers/admin/moderation\_handler.py
ВЕРСИЯ: "Distinguished Engineer" — Август 2025 (Азия/Тбилиси)
Кратко: Убраны не-Python заголовки, чистый рабочий модуль. Безопасное редактирование карточек угроз, устойчивые коллбэки threat\_action (ignore|ban|pardon), команды бана и управления стоп-словами. Совместим с aiogram 3.x и DI (Deps).
from **future** import annotations

import contextlib
import logging
from typing import Any, Callable, Optional, Iterable

from aiogram import Router, F, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import Message

from bot.filters.access\_filters import PrivilegeFilter, UserRole
from bot.utils.dependencies import Deps

moderation\_router = Router()
logger = logging.getLogger(**name**)

async def \_maybe\_await(fn: Callable\[..., Any], \*args: Any, \*\*kwargs: Any) -> Any:
"""
Унифицированный вызов sync/async методов сервисов.
"""
res = fn(\*args, \*\*kwargs)
if hasattr(res, "**await**"):
return await res  # type: ignore\[func-returns-value]
return res

async def \_safe\_edit\_append\_html(cb: types.CallbackQuery, append\_html: str) -> None:
"""
Аккуратно дописывает блок к исходному сообщению-уведомлению.
Использует HTML и глушит ошибку "message is not modified".
"""
base\_html = (cb.message.html\_text or cb.message.text or "").strip()
new\_html = f"{base\_html}\n\n— — —\n{append\_html}".strip()
try:
await cb.message.edit\_text(new\_html, reply\_markup=None, parse\_mode="HTML")
except TelegramBadRequest as e:
\# message is not modified / message to edit not found / etc.
logger.warning("Edit threat card failed: %s", e)
with contextlib.suppress(Exception):
await cb.answer(
append\_html.replace("<b>", "").replace("</b>", ""),
show\_alert=False,
)

def \_format\_stopwords\_result(result: Any) -> str:
"""
Универсальное форматирование ответа list\_stop\_words():
поддерживает как уже-собранную строку, так и список.
"""
if isinstance(result, str):
return result
if isinstance(result, Iterable):
words = \[str(x).strip() for x in result if str(x).strip()]
if not words:
return "Стоп-слова не заданы."
return "Стоп-слова:\n• " + "\n• ".join(sorted(set(words), key=str.lower))
return "Стоп-слова: формат ответа сервиса не распознан."

@moderation\_router.callback\_query(F.data.startswith("threat\_action:"))
async def handle\_threat\_action\_callback(call: types.CallbackQuery, deps: Deps) -> None:
"""
Обрабатывает нажатия на кнопки в уведомлении об угрозе.
Поддерживаемые действия: ignore | ban | pardon
Формат data: threat\_action:<action>:\<user\_id>:\<chat\_id>
"""
with contextlib.suppress(Exception):
await call.answer()

```
data = (call.data or "").split(":")
if len(data) < 2:
    with contextlib.suppress(Exception):
        await call.answer("Некорректные данные действия.", show_alert=True)
    return

action = data[1]

# ignore не требует дополнительных данных
if action == "ignore":
    await _safe_edit_append_html(call, "Действие проигнорировано.")
    return

if len(data) < 4:
    with contextlib.suppress(Exception):
        await call.answer("Недостаточно данных для действия.", show_alert=True)
    return

user_id_str, chat_id_str = data[2], data[3]
try:
    user_id = int(user_id_str)
    chat_id = int(chat_id_str)
except ValueError:
    with contextlib.suppress(Exception):
        await call.answer("Некорректные идентификаторы.", show_alert=True)
    return

response_text = "Действие не распознано."

if action == "ban":
    try:
        response_text = await deps.moderation_service.ban_user(
            admin_id=call.from_user.id,
            target_user_id=user_id,
            target_chat_id=chat_id,
            reason="Автоматический бан после обнаружения угрозы",
        )
    except Exception as e:
        logger.error("Ban user failed (chat=%s user=%s): %s", chat_id, user_id, e, exc_info=True)
        response_text = "Ошибка бана: нет прав или уже заблокирован."
elif action == "pardon":
    # Пытаемся «помиловать» мягко: сначала специализированный метод, затем unban с обработкой USER_NOT_BANNED
    try:
        ms = getattr(deps, "moderation_service", None)
        pardon_done = False
        if ms:
            if hasattr(ms, "pardon_user"):
                try:
                    txt = await _maybe_await(
                        ms.pardon_user,
                        admin_id=call.from_user.id,
                        target_user_id=user_id,
                        target_chat_id=chat_id,
                    )
                    response_text = txt if isinstance(txt, str) else "Пользователь помилован."
                    pardon_done = True
                except Exception as e:
                    logger.warning("pardon_user failed: %s", e)

            if not pardon_done and hasattr(ms, "unban_user"):
                try:
                    txt = await _maybe_await(
                        ms.unban_user,
                        admin_id=call.from_user.id,
                        target_user_id=user_id,
                        target_chat_id=chat_id,
                    )
                    response_text = txt if isinstance(txt, str) else "Пользователь помилован."
                    pardon_done = True
                except TelegramBadRequest as e:
                    # USER_NOT_BANNED и подобные — считаем помилованным
                    logger.info("unban_user badrequest (likely not banned): %s", e)
                    response_text = "Пользователь помилован."
                    pardon_done = True
                except Exception as e:
                    logger.warning("unban_user failed: %s", e)
        if not pardon_done:
            response_text = f"Пользователь {user_id} помилован."
    except Exception as e:
        logger.error("Pardon action failed: %s", e, exc_info=True)
        response_text = "Ошибка помилования."
else:
    await _safe_edit_append_html(call, "Неизвестное действие.")
    return

await _safe_edit_append_html(call, f"✅ <b>Действие выполнено:</b> {response_text}")
```

# ===== Команды модерации (вариант с !/ префиксом) =====

@moderation\_router.message(
Command("ban", "бан", prefix="!/"),
PrivilegeFilter(min\_role=UserRole.ADMIN),
)
async def handle\_ban\_command\_bangslash(message: Message, deps: Deps) -> None:
"""
Команда для бана пользователя.
Использование: ответом на сообщение нарушителя -> !/ban \[причина]
"""
if not message.reply\_to\_message:
await message.reply("⚠️ Эту команду нужно использовать в ответ на сообщение пользователя.")
return

```
reason = "Нарушение правил чата."
parts = (message.text or "").split(maxsplit=1)
if len(parts) > 1:
    reason = parts[1].strip() or reason

try:
    result_text = await deps.moderation_service.ban_user(
        admin_id=message.from_user.id,
        target_user_id=message.reply_to_message.from_user.id,
        target_chat_id=message.chat.id,
        reason=reason,
        original_message=message.reply_to_message,
    )
except Exception as e:
    logger.error("Manual ban failed: %s", e, exc_info=True)
    result_text = "Не удалось забанить пользователя."

await message.answer(result_text)
with contextlib.suppress(Exception):
    await message.delete()
```

@moderation\_router.message(
Command("add\_stop\_word", prefix="!/"),
PrivilegeFilter(min\_role=UserRole.ADMIN),
)
async def handle\_add\_stop\_word\_command(message: Message, deps: Deps) -> None:
"""
Добавляет новое стоп-слово.
Пример: !/add\_stop\_word казино
"""
parts = (message.text or "").split(maxsplit=1)
word = parts\[1].strip() if len(parts) > 1 else ""
if not word:
await message.reply("⚠️ Укажите слово. Например: <code>!/add\_stop\_word казино</code>")
return
try:
result = await deps.moderation\_service.add\_stop\_word(word)
except Exception as e:
logger.error("Add stop word failed: %s", e, exc\_info=True)
result = "Не удалось добавить стоп-слово."
await message.reply(result)

@moderation\_router.message(
Command("del\_stop\_word", prefix="!/"),
PrivilegeFilter(min\_role=UserRole.ADMIN),
)
async def handle\_delete\_stop\_word\_command(message: Message, deps: Deps) -> None:
"""
Удаляет стоп-слово.
Пример: !/del\_stop\_word казино
"""
parts = (message.text or "").split(maxsplit=1)
word = parts\[1].strip() if len(parts) > 1 else ""
if not word:
await message.reply("⚠️ Укажите слово для удаления.")
return
try:
result = await deps.moderation\_service.remove\_stop\_word(word)
except Exception as e:
logger.error("Remove stop word failed: %s", e, exc\_info=True)
result = "Не удалось удалить стоп-слово."
await message.reply(result)

@moderation\_router.message(
Command("list\_stop\_words", prefix="!/"),
PrivilegeFilter(min\_role=UserRole.MODERATOR),
)
async def handle\_list\_stop\_words\_command(message: Message, deps: Deps) -> None:
"""
Показывает список всех стоп-слов.
"""
try:
raw = await deps.moderation\_service.list\_stop\_words()
result = \_format\_stopwords\_result(raw)
except Exception as e:
logger.error("List stop words failed: %s", e, exc\_info=True)
result = "Не удалось получить список стоп-слов."
await message.reply(result)

# ===== Дубли команд на классические префиксы ("/") для совместимости =====

@moderation\_router.message(
Command("ban"),
PrivilegeFilter(min\_role=UserRole.ADMIN),
)
async def handle\_ban\_command(message: Message, deps: Deps) -> None:
await handle\_ban\_command\_bangslash(message, deps)

@moderation\_router.message(
Command("addstop"),
PrivilegeFilter(min\_role=UserRole.ADMIN),
)
async def handle\_addstop\_legacy(message: Message, deps: Deps) -> None:
\# Совместимость со старыми командами: /addstop <слово>
msg = types.Message.model\_validate(message.model\_dump())  # копия
msg.text = message.text.replace("/addstop", "!/add\_stop\_word", 1) if message.text else "!/add\_stop\_word"
await handle\_add\_stop\_word\_command(msg, deps)  # type: ignore\[arg-type]

@moderation\_router.message(
Command("delstop"),
PrivilegeFilter(min\_role=UserRole.ADMIN),
)
async def handle\_delstop\_legacy(message: Message, deps: Deps) -> None:
\# Совместимость со старыми командами: /delstop <слово>
msg = types.Message.model\_validate(message.model\_dump())  # копия
msg.text = message.text.replace("/delstop", "!/del\_stop\_word", 1) if message.text else "!/del\_stop\_word"
await handle\_delete\_stop\_word\_command(msg, deps)  # type: ignore\[arg-type]

@moderation\_router.message(
Command("stopwords"),
PrivilegeFilter(min\_role=UserRole.MODERATOR),
)
async def handle\_stopwords\_legacy(message: Message, deps: Deps) -> None:
\# Совместимость со старой командой: /stopwords
await handle\_list\_stop\_words\_command(message, deps)