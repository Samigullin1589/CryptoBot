# bot/handlers/public/common_handler.py
# Версия: ИСПРАВЛЕННАЯ (28.10.2025)
# ИСПРАВЛЕНО: Метод get_consultant_answer → правильный метод из AIContentService

import asyncio
import logging
import re
from typing import Optional, Tuple

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatType

from bot.filters.not_command_filter import NotCommandFilter
from bot.utils.dependencies import Deps

logger = logging.getLogger(__name__)

router = Router(name="public_common")


# ------------------------- Режим ИИ по команде /ask -------------------------

class AIConsultantState(StatesGroup):
    waiting_question = State()


@router.message(F.chat.type == ChatType.PRIVATE, Command("ask"))
async def cmd_ask(message: Message, state: FSMContext):
    """Вход в режим вопроса к ИИ (только по явной команде, только в ЛС)."""
    await state.set_state(AIConsultantState.waiting_question)
    await message.answer("Напишите свой вопрос для ИИ одним сообщением:")


@router.message(F.chat.type == ChatType.PRIVATE, AIConsultantState.waiting_question, F.text)
async def handle_ai_question(message: Message, state: FSMContext, deps: Deps):
    """Обрабатываем вопрос к ИИ только когда пользователь в соответствующем состоянии (ЛС)."""
    user_text = (message.text or "").strip()

    # История (если есть сервис)
    history = []
    if hasattr(deps, "user_service") and message.from_user:
        try:
            # Используем правильный метод для получения истории
            history = await deps.user_service.get_conversation_history(
                message.from_user.id, 
                message.chat.id
            )
        except Exception as e:
            logger.debug(f"Failed to get conversation history: {e}")
            history = []

    # Запрос к ИИ
    try:
        # ✅ ИСПРАВЛЕНО: Используем правильный метод generate_text вместо get_consultant_answer
        ai_answer = await deps.ai_content_service.generate_text(
            prompt=user_text,
            history=history if history else None
        )
        
        ai_answer = ai_answer or "Не удалось получить ответ от AI."
        
        # Сохраняем в историю если есть user_service
        if hasattr(deps, "user_service") and message.from_user:
            try:
                await deps.user_service.add_to_conversation_history(
                    message.from_user.id,
                    message.chat.id,
                    user_text,
                    ai_answer
                )
            except Exception as e:
                logger.debug(f"Failed to save to conversation history: {e}")
        
        await message.answer(f"Ваш вопрос:\n«{user_text}»\n\nОтвет AI-Консультанта:\n{ai_answer}")
    except Exception as e:
        logger.error("AI answer failed: %s", e, exc_info=True)
        await message.answer("Произошла ошибка при обращении к AI.")
    finally:
        await state.clear()


# ------------------------- Команда /check (разрешена и в группах) -------------------------

@router.message(Command("check"))
async def cmd_check(message: Message, command: CommandObject, deps: Deps):
    """
    Проверка пользователя: /check @username
    Также можно ответить /check на сообщение нужного пользователя.
    Доступно в ЛС и в группах.
    """
    args = (command.args or "").strip()
    target = args

    # Если аргумента нет — пробуем взять из ответа
    if not target and message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        target = f"@{u.username}" if u.username else str(u.id)

    if not target:
        await message.answer("Укажите пользователя: /check @username\nМожно также ответить на его сообщение и набрать /check.")
        return

    # Нормализуем: обрежем ссылку t.me и оставим username/id
    target = target.replace("https://t.me/", "").replace("http://t.me/", "").strip()
    if target.startswith("@"):
        target_username = target[1:]
    else:
        target_username = target

    try:
        await message.answer(f"Проверяю @{target_username}…")
    except Exception:
        pass

    # Если подключены сервисы безопасности/верификации — пытаемся вызвать
    svc = getattr(deps, "verification_service", None) or getattr(deps, "security_service", None)
    result_text = None
    if svc:
        for name in ("check_user", "verify_user", "check", "verify"):
            if hasattr(svc, name):
                try:
                    call = getattr(svc, name)
                    res = call(username=target_username)
                    res = await res if asyncio.iscoroutine(res) else res

                    # Строка — отдаем как есть
                    if isinstance(res, str):
                        result_text = res
                        break

                    # Словарь — собираем удобный формат
                    if isinstance(res, dict):
                        # ожидаемые поля, но не требуемые
                        verified = bool(res.get("verified") or res.get("safe") or res.get("ok"))
                        score = res.get("score")
                        reason = res.get("reason") or res.get("details")
                        profile = res.get("profile") or {}
                        uid = profile.get("id") or res.get("user_id")
                        name = profile.get("name") or res.get("name")
                        uname = profile.get("username") or target_username
                        country = profile.get("country") or "-"
                        passport_ok = profile.get("passport_ok")
                        deposit = profile.get("deposit")

                        header = "Команда /check\nВерифицированный" if verified else "Команда /check\nНе верифицированный"
                        curator = "Бот-куратор @НашБот\n--------------------"
                        status_line = "✅ ПРОВЕРЕННЫЙ ПОСТАВЩИК ✅" if verified else "⚠️ НЕ ПРОВЕРЕН ⚠️\nПри переводе предоплаты есть риск потерять денежные средства"
                        passport_line = "✅ Проверен ✅" if passport_ok else "⚠️ НЕ ПРОВЕРЕН ⚠️"
                        deposit_line = f"${deposit}" if isinstance(deposit, (int, float, str)) and str(deposit) else "Отсутствует"

                        lines = [
                            header,
                            "",
                            curator,
                            "Статус :",
                            status_line,
                            "",
                            "Пользователь",
                            f"Идентификатор пользователя: {uid or '-'}",
                            f"Имя: {name or '-'}",
                            f"Имя пользователя:\n@{uname}" if uname else "Имя пользователя:\n-",
                            "",
                            f"Страна: {country}",
                            f"Паспорт : {passport_line}",
                            f"Депозит : {deposit_line}",
                        ]

                        # добавим краткие детали, если есть
                        if score is not None or reason:
                            tail = []
                            if score is not None:
                                tail.append(f"рейтинг: {score}")
                            if reason:
                                tail.append(f"детали: {reason}")
                            lines += ["", "—", "", ("; ".join(tail))]

                        result_text = "\n".join(lines)
                        break

                    # Иное — нейтральный ответ
                    result_text = "Готово."
                    break

                except TypeError:
                    # возможно метод принимает user_id
                    try:
                        user_id = int(target_username)
                        res = getattr(svc, name)(user_id=user_id)
                        res = await res if asyncio.iscoroutine(res) else res
                        result_text = res if isinstance(res, str) else "Готово."
                        break
                    except Exception as e:
                        logger.debug("verification call (id) failed: %s", e)
                except Exception as e:
                    logger.debug("verification call failed: %s", e)

    if not result_text:
        result_text = "Проверка выполнена (заглушка). Подключите реализацию в security/verification сервисе к команде /check."

    await message.answer(result_text)


# ------------------------- Вспомогательные утилиты -------------------------

# Более строгий токен монеты: латиница/цифры/дефис, 2–10 символов (типично BTC, ETH, ALEO)
_COIN_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-]{1,9}$")


def _looks_like_coin_token(text: str) -> bool:
    t = text.strip()
    if not t or " " in t:
        return False
    return bool(_COIN_TOKEN_RE.match(t))


async def _maybe_call(func, *args, **kwargs):
    res = func(*args, **kwargs)
    if asyncio.iscoroutine(res):
        return await res
    return res


async def _resolve_coin(deps: Deps, query: str) -> Tuple[Optional[str], Optional[str]]:
    cls = getattr(deps, "coin_list_service", None)
    candidates = [
        ("resolve_query", {"query": query}),
        ("resolve", {"query": query}),
        ("get_coin_by_query", {"query": query}),
        ("find", {"text": query}),
        ("get", {"query": query}),
    ]
    for name, kwargs in candidates:
        if cls and hasattr(cls, name):
            try:
                obj = await _maybe_call(getattr(cls, name), **kwargs)
                if not obj:
                    continue
                coin_id = getattr(obj, "id", None) or (obj.get("id") if isinstance(obj, dict) else None)
                symbol = getattr(obj, "symbol", None) or (obj.get("symbol") if isinstance(obj, dict) else None)
                symbol = symbol or getattr(obj, "ticker", None) or (obj.get("ticker") if isinstance(obj, dict) else None)
                if coin_id or symbol:
                    return (str(coin_id) if coin_id else None), (str(symbol).upper() if symbol else None)
            except Exception as e:
                logger.debug("coin_list_service.%s failed: %s", name, e)
    return None, query.upper()


async def _fetch_usd_price(deps: Deps, symbol: str) -> Optional[float]:
    ps = getattr(deps, "price_service", None)
    mds = getattr(deps, "market_data_service", None)

    ps_candidates = [
        ("get_price", {"symbol": symbol, "fiat": "usd"}),
        ("get_price", {"coin": symbol, "fiat": "usd"}),
        ("get_prices", {"symbols": [symbol], "fiat": "usd"}),
        ("fetch_prices", {"symbols": [symbol], "fiat": "usd"}),
    ]
    for name, kwargs in ps_candidates:
        if ps and hasattr(ps, name):
            try:
                res = await _maybe_call(getattr(ps, name), **kwargs)
                if isinstance(res, (int, float)):
                    return float(res)
                if isinstance(res, dict):
                    val = res.get(symbol) or res.get(symbol.upper()) or res.get(symbol.lower())
                    if isinstance(val, (int, float)):
                        return float(val)
                    if isinstance(val, dict):
                        return float(val.get("usd") or val.get("USD") or val.get("price") or 0) or None
            except Exception as e:
                logger.debug("price_service.%s failed: %s", name, e)

    mds_candidates = [
        ("get_price", {"symbol": symbol, "fiat": "usd"}),
        ("get_prices", {"symbols": [symbol], "fiat": "usd"}),
        ("fetch_price", {"symbol": symbol, "fiat": "usd"}),
    ]
    for name, kwargs in mds_candidates:
        if mds and hasattr(mds, name):
            try:
                res = await _maybe_call(getattr(mds, name), **kwargs)
                if isinstance(res, (int, float)):
                    return float(res)
                if isinstance(res, dict):
                    val = res.get(symbol) or res.get(symbol.upper()) or res.get(symbol.lower())
                    if isinstance(val, (int, float)):
                        return float(val)
                    if isinstance(val, dict):
                        return float(val.get("usd") or val.get("USD") or val.get("price") or 0) or None
            except Exception as e:
                logger.debug("market_data_service.%s failed: %s", name, e)

    return None


async def _reply_with_price(message: Message, symbol: str, price_usd: float) -> None:
    text = f"Курс {symbol}: ${price_usd:,.2f} (USD)"
    try:
        await message.answer(text)
    except Exception as e:
        logger.error("Failed to send price reply: %s", e, exc_info=True)


def _user_in_price_context(deps: Deps, user_id: int) -> bool:
    us = getattr(deps, "user_state_service", None)
    if not us:
        return False
    for name in ("get_current_section", "get_section", "get_user_section", "get_mode"):
        if hasattr(us, name):
            try:
                section = getattr(us, name)(user_id)
                if asyncio.iscoroutine(section):
                    return False
                section_str = (str(section) if section is not None else "").lower()
                if section_str in {"price", "prices", "курс", "курсы", "market_price"}:
                    return True
            except Exception:
                pass
    return False


def _extract_price_query(text: str) -> Optional[str]:
    """
    Строгий детект запроса цены:
      - чистый токен монеты (BTC)
      - или фраза вида: 'курс BTC' / 'Курс btc'
    НЕ реагируем на одиночный знак '$' и длинные строки.
    """
    t = text.strip()
    if len(t) > 32:  # слишком длинно для короткого «курса»
        return None
    if _looks_like_coin_token(t):
        return t
    m = re.search(r"(?:^|\s)(?:курс)\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9\-]{1,9})", t, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    return None


# ------------------------- Глушилка объявлений/прайсов (молчаливо) -------------------------

AD_LIKE = re.compile(
    r'(?:\+7|8)\d{10}|@\w+|[$€₽]|S\d{2}\s?[A-Z]+|L7|M50|M30s\+\+|XP\s?\d+th|j\s?pro\+|S21|M60|M64|Avalon',
    re.IGNORECASE,
)

@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}), F.text.regexp(AD_LIKE), NotCommandFilter())
async def ignore_ads_like_group(_: Message):
    """В группах: объявления/прайсы игнорируем полностью (без ответов)."""
    return


# ------------------------------ Общий текстовый обработчик ------------------------------

# Только ЛС, и без команд
@router.message(F.chat.type == ChatType.PRIVATE, F.text, NotCommandFilter())
async def handle_text_common(message: Message, deps: Deps) -> None:
    """
    Поведение в ЛС:
      1) Если пользователь в разделе «Курс» ИЛИ текст похож на запрос цены — отвечаем курсом монеты.
      2) Иначе — не запускаем ИИ автоматически. Бот молчит.
    """
    user_text = (message.text or "").strip()

    # 1) Курс монеты (раздел «Курс» или явный запрос)
    in_price_ctx = _user_in_price_context(deps, message.from_user.id if message.from_user else 0)
    price_query = _extract_price_query(user_text)

    if in_price_ctx or price_query:
        query = price_query or user_text
        coin_id, symbol = await _resolve_coin(deps, query)
        symbol_for_fetch = symbol or (coin_id or "").upper()
        if symbol_for_fetch:
            price = await _fetch_usd_price(deps, symbol_for_fetch)
            if price is not None:
                await _reply_with_price(message, symbol_for_fetch, price)
            # если цены нет — молчим, чтобы не спамить
        return

    # 2) Никакого автозапуска ИИ: молчим
    return