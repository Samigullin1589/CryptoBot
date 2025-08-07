# =================================================================================
# Файл: bot/utils/keys.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Централизованная фабрика для генерации всех ключей Redis.
# Этот подход устраняет дублирование и обеспечивает консистентность.
# =================================================================================

class KeyFactory:
    """Генерирует стандартизированные ключи для Redis."""

    # --- Пользователи ---
    @staticmethod
    def user_profile(user_id: int) -> str:
        return f"user:profile:{user_id}"

    @staticmethod
    def all_users_set() -> str:
        return "users:all"

    # --- История диалогов ---
    @staticmethod
    def conversation_history(user_id: int, chat_id: int) -> str:
        return f"conversation:{user_id}:{chat_id}"

    # --- Достижения ---
    @staticmethod
    def user_achievements(user_id: int) -> str:
        return f"achievements:{user_id}"

    @staticmethod
    def user_event_counters(user_id: int) -> str:
        return f"achievements:counters:{user_id}"

    # --- Игра ---
    @staticmethod
    def user_game_profile(user_id: int) -> str:
        return f"game:profile:{user_id}"

    @staticmethod
    def active_session(user_id: int) -> str:
        return f"game:session:{user_id}"

    @staticmethod
    def user_hangar(user_id: int) -> str:
        return f"game:hangar:{user_id}"
        
    @staticmethod
    def game_stats() -> str:
        return "game:stats"

    # --- Рынок ---
    @staticmethod
    def market_listings_by_price() -> str:
        return "market:listings:price"

    @staticmethod
    def market_listing_data(listing_id: str) -> str:
        return f"market:listing:{listing_id}"

    # --- Новости ---
    @staticmethod
    def news_deduplication_set() -> str:
        return "news:dedup_hashes"

    # --- ASIC ---
    @staticmethod
    def asic_hash(normalized_name: str) -> str:
        return f"asic:{normalized_name}"

    @staticmethod
    def asics_sorted_set() -> str:
        return "asics:sorted_by_profit"
        
    @staticmethod
    def asics_last_update() -> str:
        return "asics:last_update"
        
    @staticmethod
    def asics_update_lock() -> str:
        return "lock:asics_update"
