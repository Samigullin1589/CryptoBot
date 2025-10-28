# bot/handlers/public/common_handler.py
# Версия: ПРАВИЛЬНАЯ с get_text_response (28.10.2025)

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
            history = await deps.user_service.get_conversation_history(
                message.from_user.id, 
                message.chat.id
            )
        except Exception as e:
            logger.debug(f"Failed to get conversation history: {e}")
            history = []

    # ✅ ПРАВИЛЬНЫЙ ЗАПРОС К ИИ через get_text_response
    try:
        # Формируем промпт с историей если есть
        full_prompt = user_text
        system_prompt = None
        
        if history:
            # Добавляем историю в контекст
            history_context = "\n".join([
                f"Пользователь: {h['user']}\nАссистент: {h['assistant']}" 
                for h in history[-5:]  # Последние 5 сообщений
            ])
            system_prompt = (
                "Ты — AI-консультант по майнингу и криптовалютам. "
                "Вот предыдущие сообщения в этом разговоре:\n\n"
                f"{history_context}\n\n"
                "Отвечай на основе контекста разговора."
            )
        else:
            system_prompt = "Ты — AI-консультант по майнингу и криптовалютам."
        
        # ✅ ПРАВИЛЬНЫЙ МЕТОД: get_text_response
        ai_answer = await deps.ai_content_service.get_text_response(
            prompt=full_prompt,
            system_prompt=system_prompt
        )
        
        ai_answer = ai_answer or "Не удалось получить ответ от AI."
        
        # Сохраняем в историю
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


# ------------------------- Команда /check (БЕЗ ЗАГЛУШЕК!) -------------------------

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
    
    # Определяем username или ID
    username = None
    user_id = None
    
    if target.startswith("@"):
        username = target[1:]
    elif target.isdigit():
        user_id = int(target)
    else:
        username = target

    try:
        await message.answer(f"Проверяю @{username or user_id}…")
    except Exception:
        pass

    # 🎯 ГЛАВНОЕ: Проверяем через verification_service
    svc = getattr(deps, "verification_service", None)
    result_text = None
    
    if svc and hasattr(svc, "check_user"):
        try:
            # Вызываем метод check_user
            result_text = await svc.check_user(username=username, user_id=user_id)
        except Exception as e:
            logger.error(f"Ошибка при вызове verification_service.check_user: {e}", exc_info=True)
            result_text = None

    # ⚠️ FALLBACK: Если сервис недоступен или вернул None
    if not result_text:
        # Пытаемся найти пользователя хотя бы через user_service
        user_service = getattr(deps, "user_service", None)
        if user_service:
            try:
                user = None
                if username:
                    user = await user_service.get_user_by_username(username)
                elif user_id:
                    user = await user_service.get_user(user_id)
                
                if user:
                    # Форматируем базовый ответ
                    vd = user.verification_data
                    header = "✅ ПРОВЕРЕННЫЙ ПОСТАВЩИК ✅" if vd.is_verified else "⚠️ НЕ ПРОВЕРЕН ⚠️\nПри переводе предоплаты есть риск потерять денежные средства"
                    passport_line = "✅ Проверен ✅" if vd.passport_verified else "⚠️ НЕ ПРОВЕРЕН ⚠️"
                    deposit_line = f"${vd.deposit:,.0f}".replace(",", " ") if vd.deposit > 0 else "Отсутствует"
                    
                    result_text = (
                        f"Команда /check\n"
                        f"{'Верифицированный' if vd.is_verified else 'Не верифицированный'}\n\n"
                        f"Бот-куратор @НашБот\n"
                        f"--------------------\n"
                        f"Статус :\n{header}\n\n"
                        f"Пользователь\n"
                        f"Идентификатор пользователя: {user.id}\n"
                        f"Имя: {user.first_name}\n"
                        f"Имя пользователя:\n@{user.username or '-'}\n\n"
                        f"Страна: -\n"
                        f"Паспорт : {passport_line}\n"
                        f"Депозит : {deposit_line}"
                    )
                else:
                    result_text = f"❌ Пользователь @{username or user_id} не найден в базе данных."
            except Exception as e:
                logger.error(f"Ошибка при получении пользователя из user_service: {e}")
                result_text = None
    
    # Если всё провалилось - критическая ошибка
    if not result_text:
        result_text = "❌ Ошибка: сервис верификации недоступен. Обратитесь к администратору."

    await message.answer(result_text)


# ------------------------- Вспомогательные утилиты -------------------------

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