# ======================================================================================
# Файл: bot/jobs/scheduled_tasks.py
# Версия: "Distinguished Engineer" — Август 2025 (Asia/Tbilisi)
# Описание:
#   Централизованный планировщик фоновых задач на APScheduler (AsyncIOScheduler).
#   Поддерживает три типовые задачи:
#     • update_coin_list_job      — обновляет и переиндексирует список монет
#     • warm_price_cache_job      — прогревает кэш котировок (если сервис поддерживает)
#     • prefetch_news_job         — предзагружает свежие новости в кэш
#   Замечание: отправку сообщений намеренно не выполняем внутри задач, чтобы не зависеть
#   от жизненного цикла бота. Эти джобы безопасны для запуска до start_polling.
# ======================================================================================

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

if TYPE_CHECKING:
    from bot.utils.dependencies import Deps
    from aiogram import Dispatcher

logger = logging.getLogger(__name__)


# --------------------------------- helpers ------------------------------------

async def _call_if_exists(obj: object, *names: str, **extra_kwargs: Any) -> bool:
    """
    Пытается вызвать у объекта/сервиса первый попавшийся метод из списка `names`.
    Возвращает True, если какой-то метод найден и успешно вызван (await при необходимости).
    """
    for name in names:
        fn = getattr(obj, name, None)
        if callable(fn):
            try:
                res = fn(**extra_kwargs) if extra_kwargs else fn()
                if hasattr(res, "__await__"):  # coroutine?
                    await res  # type: ignore[misc]
                logger.info("Выполнено: %s.%s()", obj.__class__.__name__, name)
                return True
            except Exception as e:  # noqa: BLE001
                logger.warning("Ошибка при вызове %s.%s(): %s", obj.__class__.__name__, name, e, exc_info=True)
                return False
    return False


def _get_tz() -> str:
    """
    Возвращает строковый идентификатор таймзоны для APScheduler.
    Предпочитаем системную TZ, затем Settings, иначе UTC.
    """
    tz = os.getenv("TZ")
    if tz:
        return tz
    try:
        # Пытаемся взять из настроек, если доступны через импорт
        from bot.config.settings import settings  # type: ignore
        # Возможные варианты хранения TZ в Settings
        for attr in ("TZ", "tz", "time_zone", "timezone"):
            val = getattr(settings, attr, None)
            if isinstance(val, str) and val:
                return val
    except Exception:
        pass
    return "UTC"


# --------------------------------- jobs ---------------------------------------

async def update_coin_list_job(deps: "Deps") -> None:
    """
    Обновляет/индексирует список монет. Поддерживает разные контракты сервисов.
    """
    svc = getattr(deps, "coin_list_service", None)
    if not svc:
        logger.info("CoinListService отсутствует — пропуск обновления списка монет.")
        return

    # Популярные варианты названий методов — пробуем по очереди
    called = await _call_if_exists(
        svc,
        "update_and_index",
        "refresh_and_index",
        "refresh_cache",
        "update_cache",
        "warmup",
        "init",
    )
    if not called:
        # Пробуем «грубую» перезагрузку: fetch + cache (если есть пара методов)
        ok_fetch = await _call_if_exists(svc, "fetch", "load", "reload")
        ok_cache = await _call_if_exists(svc, "cache", "reindex", "rebuild_index")
        logger.info("CoinListService: fetch=%s cache=%s (fallback).", ok_fetch, ok_cache)


async def warm_price_cache_job(deps: "Deps") -> None:
    """
    Прогревает кэш котировок по базовым монетам. Безопасно, если метод отсутствует.
    """
    svc = getattr(deps, "price_service", None)
    if not svc:
        logger.info("PriceService отсутствует — пропуск прогрева кэша котировок.")
        return

    # Частые контракты:
    if not await _call_if_exists(svc, "warmup_cache", "warmup", "prefetch_top", "prefetch"):
        logger.info("PriceService не поддерживает прогрев кэша — пропуск.")


async def prefetch_news_job(deps: "Deps") -> None:
    """
    Предзагружает свежие новости в кэш (агрегация). Без публикации в чат.
    """
    svc = getattr(deps, "news_service", None)
    if not svc:
        logger.info("NewsService отсутствует — пропуск предзагрузки новостей.")
        return

    # Наиболее вероятные контракты:
    if await _call_if_exists(svc, "get_all_latest_news"):
        logger.info("Новости успешно предзагружены через get_all_latest_news().")
        return

    # Фолбэки: собрать по источникам, если сервис предоставляет такие методы.
    if await _call_if_exists(svc, "prefetch", "warmup", "refresh"):
        logger.info("Новости предзагружены через fallback-метод.")
    else:
        logger.info("NewsService не имеет подходящих методов предзагрузки — пропуск.")


# --------------------------- scheduler bootstrap -------------------------------

async def setup_scheduler(deps: "Deps", dp: "Dispatcher") -> None:
    """
    Регистрирует и запускает планировщик. Вызывается из main.py во время старта бота.
    Параметры расписаний берём из Settings, при отсутствии — используем дефолты.
    """
    # Извлекаем интервалы из настроек с безопасными дефолтами
    try:
        coin_hours: int = int(getattr(deps.settings.coin_list_service, "update_interval_hours", 12))
    except Exception:
        coin_hours = 12

    try:
        price_minutes: int = int(getattr(deps.settings.price_service, "refresh_interval_minutes", 5))
    except Exception:
        price_minutes = 5

    try:
        news_minutes: int = int(getattr(deps.settings.news_service, "refresh_interval_minutes", 180))
    except Exception:
        news_minutes = 180

    tz = _get_tz()
    scheduler = AsyncIOScheduler(timezone=tz)

    # Сохраним ссылку в deps.services, чтобы можно было управлять и завершать при необходимости
    try:
        deps.services["scheduler"] = scheduler
    except Exception:
        pass

    # Планируем задачи
    try:
        scheduler.add_job(update_coin_list_job, "interval", hours=max(1, coin_hours), args=[deps], id="coin_list_update", replace_existing=True)
        scheduler.add_job(warm_price_cache_job, "interval", minutes=max(1, price_minutes), args=[deps], id="price_cache_warmup", replace_existing=True)
        scheduler.add_job(prefetch_news_job, "interval", minutes=max(10, news_minutes), args=[deps], id="news_prefetch", replace_existing=True)
    except Exception as e:  # noqa: BLE001
        logger.critical("Ошибка при создании задач в планировщике: %s", e, exc_info=True)
        return

    try:
        scheduler.start()
        logger.info(
            "Планировщик запущен (tz=%s). Задачи: %s",
            tz,
            [job.id for job in scheduler.get_jobs()],
        )
    except Exception as e:  # noqa: BLE001
        logger.critical("Не удалось запустить планировщик APScheduler: %s", e, exc_info=True)
