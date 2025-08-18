# ===============================================================
# Файл: bot/filters/threat_filter.py (ПРОДАКШН-ВЕРСИЯ 2025 - ИСПРАВЛЕННАЯ)
# Описание: Интеллектуальный фильтр для обнаружения угроз.
# ИСПРАВЛЕНИЕ: Метод __call__ адаптирован для получения зависимостей
#              через DI-контейнер deps.
# ===============================================================

from typing import Any

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from bot.utils.dependencies import Deps


class ThreatFilter(BaseFilter):
    """
    Универсальный фильтр-детектор угроз.
    Совместим с aiogram 3.x и DI: допускает произвольные аргументы конструктора/вызова,
    чтобы избежать TypeError при различиях в механизмах регистрации фильтров.
    """

    def __init__(self, min_score: float = 1.0, *args: Any, **kwargs: Any) -> None:
        # Дополнительно принимаем *args/**kwargs, чтобы не падать,
        # если Router неожиданно попытается передать параметры в конструктор.
        self.min_score = float(min_score)

    async def __call__(
        self, event: Message | CallbackQuery, **data: Any
    ) -> bool | dict[str, Any]:
        # aiogram может передать либо Message, либо CallbackQuery
        message: Message | None = None
        if isinstance(event, Message):
            message = event
        elif isinstance(event, CallbackQuery):
            message = event.message
        if message is None:
            return False

        text = (getattr(message, "text", None) or "").strip()
        if not text:
            return False

        deps: Deps | None = data.get("deps")
        total_score: float = 0.0
        reasons: list[str] = []

        # 1) Попытка использовать полноценный SecurityService (если он есть в DI)
        if deps and getattr(deps, "security_service", None):
            try:
                verdict = await deps.security_service.analyze_message(text)
                total_score += float(verdict.score)
                if verdict.reasons:
                    reasons.extend(verdict.reasons)
            except Exception:
                # Переходим к эвристикам ниже
                pass

        # 2) Легкие эвристики на случай недоступности сервисов
        if total_score == 0.0:
            lowered = text.lower()
            bad_kw = [
                "http://",
                "https://",
                "casino",
                "airdrop",
                "giveaway",
                "usdt",
                "бинанс промокод",
            ]
            hits = [kw for kw in bad_kw if kw in lowered]
            if hits:
                total_score += 1.0
                reasons.append("Подозрительные ключевые слова: " + ", ".join(hits))

        # 3) Пересланные сообщения — небольшой вклад
        if getattr(message, "forward_date", None):
            total_score += 0.5
            reasons.append("Пересланное сообщение")

        return (
            {"threat_score": total_score, "reasons": reasons}
            if total_score >= self.min_score
            else False
        )
