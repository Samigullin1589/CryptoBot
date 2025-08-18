# =================================================================================
# Файл: bot/services/event_service.py
# Версия: "Distinguished Engineer" — ПРОДАКШН (Aug 16, 2025)
# Описание:
#   Единый сервис событий/баффов проекта (например, бусты для майнинга, акции и т.п.).
#   - Поддержка статической конфигурации из JSON-файла (settings.events.config_path)
#   - Поддержка динамических "кастомных" событий в Redis (админом из панели)
#   - Быстрые методы для бизнес-логики:
#       • get_active_events(now)
#       • get_multiplier(domain="mining", now)
#       • list_events(), upsert_event(...), cancel_event(event_id)
#   - Безопасные парсеры дат, таймзона UTC, устойчивость к ошибкам
#   - Совместимо с DI: __init__(settings, redis, http_session=None)
# =================================================================================
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp
from redis.asyncio import Redis

from bot.config.settings import Settings

logger = logging.getLogger(__name__)


# ------------------------------- Модель события --------------------------------

@dataclass
class EventItem:
    id: str
    name: str
    domain: str           # "mining" | "market" | "quiz" | "all" ...
    multiplier: float     # например 1.10 = +10%
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    meta: Optional[Dict[str, Any]] = None

    def is_active(self, now: Optional[datetime] = None) -> bool:
        _now = now or datetime.now(timezone.utc)
        if self.starts_at and _now < self.starts_at:
            return False
        if self.ends_at and _now > self.ends_at:
            return False
        return True


# ------------------------------ Вспомогательные --------------------------------

def _to_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _parse_dt(val: Any) -> Optional[datetime]:
    """
    Поддерживаем:
      - ISO 8601 строки ( '2025-08-16T12:00:00Z', '2025-08-16 12:00:00' )
      - Unix epoch (int/float)
      - None
    Возвращаем UTC-aware datetime | None.
    """
    if val is None or val == "":
        return None
    try:
        if isinstance(val, (int, float)):
            return datetime.fromtimestamp(float(val), tz=timezone.utc)
        if isinstance(val, str):
            s = val.strip()
            # Нормализация суффикса Z
            if s.endswith("Z"):
                s = s[:-1]
                dt = datetime.fromisoformat(s)
                return _to_utc(dt)
            try:
                dt = datetime.fromisoformat(s)
                return _to_utc(dt)
            except Exception:
                pass
            # Популярные форматы
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(s, fmt)
                    return _to_utc(dt)
                except Exception:
                    continue
    except Exception:
        return None
    return None


def _coerce_event(d: Dict[str, Any]) -> Optional[EventItem]:
    try:
        return EventItem(
            id=str(d.get("id") or d["name"]).strip(),
            name=str(d.get("name") or d.get("title") or d.get("id")).strip(),
            domain=str(d.get("domain", "all")).strip().lower(),
            multiplier=float(d.get("multiplier", 1.0)),
            starts_at=_parse_dt(d.get("starts_at")),
            ends_at=_parse_dt(d.get("ends_at")),
            meta=d.get("meta") if isinstance(d.get("meta"), dict) else None,
        )
    except Exception as e:
        logger.warning("Некорректное событие в конфиге: %s (raw=%s)", e, d)
        return None


# --------------------------------- Сервис --------------------------------------

class EventService:
    """
    Сервис событий.
    Хранение:
      • Статический конфиг (JSON-файл) — используется как базовый список событий.
      • Динамические события в Redis: HASH key="events:custom" (field=id, value=json).
    Предоставляет агрегированные "активные" события и эффективный множитель по домену.
    """

    def __init__(
        self,
        settings: Settings,
        redis: Redis,
        http_session: Optional[aiohttp.ClientSession] = None,
    ) -> None:
        self.settings = settings
        self.redis = redis
        self.session = http_session  # на будущее (вебхуки/загрузки по URL)
        self._static_events_cache: List[EventItem] = []
        self._static_loaded_from: Optional[str] = None  # путь файла, из которого грузили
        self._static_mtime: Optional[float] = None
        self._cache_key_custom = "events:custom"
        self._cache_key_snapshot = "events:snapshot"  # аггрегированный снапшот (опц.)

    # ------------------------------ Жизненный цикл ------------------------------

    async def aclose(self) -> None:
        """Нечего закрывать — метод для симметрии с другими сервисами."""
        return None

    # ------------------------------ Загрузка конфига ----------------------------

    def _static_config_path(self) -> str:
        # settings.events.config_path ожидается как относительный путь внутри проекта
        return str(getattr(self.settings.events, "config_path", "data/events_config.json"))

    def _need_reload_static(self) -> bool:
        path = self._static_config_path()
        try:
            st = os.stat(path)
        except Exception:
            # файла нет — если ранее уже загружали другое, не перезагружаем
            return self._static_loaded_from != path or not self._static_events_cache
        mtime = st.st_mtime
        return (self._static_loaded_from != path) or (self._static_mtime != mtime)

    def _load_static_sync(self) -> List[EventItem]:
        path = self._static_config_path()
        if not os.path.exists(path):
            logger.info("EventService: статический файл %s не найден — базовых событий нет.", path)
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                items = raw.get("events") or raw.get("items") or []
            elif isinstance(raw, list):
                items = raw
            else:
                items = []
            result: List[EventItem] = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                e = _coerce_event(it)
                if e:
                    result.append(e)
            # обновим маркеры
            st = os.stat(path)
            self._static_loaded_from = path
            self._static_mtime = st.st_mtime
            return result
        except Exception as e:
            logger.error("EventService: не удалось прочитать %s: %s", path, e, exc_info=True)
            return []

    async def _ensure_static_loaded(self) -> None:
        if not self._need_reload_static():
            return
        # читаем синхронно (файл локальный и небольшой)
        self._static_events_cache = self._load_static_sync()

    # ------------------------------ Динамика (Redis) ---------------------------

    async def _read_custom_events(self) -> List[EventItem]:
        """
        Читает динамические события из Redis HASH events:custom (field=id -> json).
        """
        try:
            raw = await self.redis.hgetall(self._cache_key_custom)
            if not raw:
                return []
            out: List[EventItem] = []
            for _id, s in raw.items():
                try:
                    d = json.loads(s)
                    e = _coerce_event(d)
                    if e:
                        out.append(e)
                except Exception:
                    continue
            return out
        except Exception as e:
            logger.warning("EventService: не удалось прочитать кастомные события: %s", e)
            return []

    async def list_events(self, include_inactive: bool = True, now: Optional[datetime] = None) -> List[EventItem]:
        """
        Возвращает объединённый список (static + custom).
        """
        await self._ensure_static_loaded()
        custom = await self._read_custom_events()
        all_events = self._merge_events(self._static_events_cache, custom)
        if include_inactive:
            return all_events
        _now = now or datetime.now(timezone.utc)
        return [e for e in all_events if e.is_active(_now)]

    async def upsert_event(
        self,
        *,
        event_id: str,
        name: str,
        domain: str,
        multiplier: float,
        starts_at: Optional[Any] = None,
        ends_at: Optional[Any] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> EventItem:
        """
        Создаёт или обновляет кастомное событие (в Redis).
        """
        e = EventItem(
            id=str(event_id),
            name=name,
            domain=domain.lower().strip(),
            multiplier=float(multiplier),
            starts_at=_parse_dt(starts_at),
            ends_at=_parse_dt(ends_at),
            meta=meta if isinstance(meta, dict) else None,
        )
        d = {
            "id": e.id,
            "name": e.name,
            "domain": e.domain,
            "multiplier": e.multiplier,
            "starts_at": e.starts_at.isoformat() if e.starts_at else None,
            "ends_at": e.ends_at.isoformat() if e.ends_at else None,
            "meta": e.meta or {},
        }
        try:
            await self.redis.hset(self._cache_key_custom, e.id, json.dumps(d, ensure_ascii=False))
        except Exception as ex:
            logger.error("EventService: upsert_event(%s) failed: %s", e.id, ex, exc_info=True)
        return e

    async def cancel_event(self, event_id: str) -> bool:
        """Удаляет кастомное событие из Redis."""
        try:
            removed = await self.redis.hdel(self._cache_key_custom, event_id)
            return bool(removed)
        except Exception as e:
            logger.error("EventService: cancel_event(%s) failed: %s", event_id, e)
            return False

    # ------------------------------ Агрегация ----------------------------------

    def _merge_events(self, a: List[EventItem], b: List[EventItem]) -> List[EventItem]:
        """
        Сливает два списка с приоритетом B (custom) по id.
        """
        by_id: Dict[str, EventItem] = {e.id: e for e in a}
        for e in b:
            by_id[e.id] = e
        return list(by_id.values())

    async def get_active_events(self, now: Optional[datetime] = None) -> List[EventItem]:
        """Активные на текущий момент события (static+custom)."""
        _now = now or datetime.now(timezone.utc)
        all_events = await self.list_events(include_inactive=False, now=_now)
        return [e for e in all_events if e.is_active(_now)]

    async def get_multiplier(self, domain: str = "mining", now: Optional[datetime] = None) -> float:
        """
        Эффективный множитель для домена.
        Стартовое значение — settings.events.default_multiplier (по умолчанию 1.0).
        Далее перемножаем все активные события, у которых domain == {domain} или "all".
        """
        base = float(getattr(self.settings.events, "default_multiplier", 1.0) or 1.0)
        _now = now or datetime.now(timezone.utc)
        events = await self.get_active_events(_now)
        m = base
        dom = (domain or "mining").strip().lower()
        for e in events:
            if e.domain in (dom, "all"):
                try:
                    m *= float(e.multiplier or 1.0)
                except Exception:
                    continue
        # защита от нолей/NaN
        if not (m > 0):
            m = 1.0
        return float(round(m, 6))

    # ------------------------------ Снапшот (опц.) -----------------------------

    async def build_snapshot(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Полезно для /admin:compact dump.
        """
        _now = now or datetime.now(timezone.utc)
        active = await self.get_active_events(_now)
        all_events = await self.list_events(include_inactive=True)
        data = {
            "now": _now.isoformat(),
            "active": [e.__dict__ | {
                "starts_at": e.starts_at.isoformat() if e.starts_at else None,
                "ends_at": e.ends_at.isoformat() if e.ends_at else None,
            } for e in active],
            "all": [e.__dict__ | {
                "starts_at": e.starts_at.isoformat() if e.starts_at else None,
                "ends_at": e.ends_at.isoformat() if e.ends_at else None,
            } for e in all_events],
        }
        try:
            await self.redis.set(self._cache_key_snapshot, json.dumps(data, ensure_ascii=False), ex=300)
        except Exception:
            pass
        return data


__all__ = ["EventService", "EventItem"]