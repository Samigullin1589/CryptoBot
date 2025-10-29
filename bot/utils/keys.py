# src/bot/utils/keys.py
class KeyFactory:
    """Генерирует стандартизированные ключи для Redis."""

    # --- Пользователи ---
    @staticmethod
    def user_profile(user_id: int) -> str:
        return f"user:profile:{user_id}"

    @staticmethod
    def all_users_set() -> str:
        return "users:all"
        
    @staticmethod
    def username_to_id_map() -> str:
        """HASH для сопоставления username -> user_id."""
        return "map:username_to_id"

    # --- Профиль интересов ... и другие ключи ---
    @staticmethod
    def user_interest_profile(user_id: int) -> str:
        return f"user:interest_profile:{user_id}"

    @staticmethod
    def conversation_history(user_id: int, chat_id: int) -> str:
        return f"conversation:{user_id}:{chat_id}"

    @staticmethod
    def user_achievements(user_id: int) -> str:
        return f"achievements:{user_id}"

    @staticmethod
    def user_event_counters(user_id: int) -> str:
        return f"achievements:counters:{user_id}"

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
        
    @staticmethod
    def game_leaderboard() -> str:
        return "game:leaderboard"

    @staticmethod
    def market_listings_by_price() -> str:
        return "market:listings:price"

    @staticmethod
    def market_listing_data(listing_id: str) -> str:
        return f"market:listing:{listing_id}"

    @staticmethod
    def news_deduplication_set() -> str:
        return "news:dedup_hashes"
        
    @staticmethod
    def personalized_alpha_cache(user_id: int, alpha_type: str) -> str:
        return f"cache:crypto_center:alpha:{user_id}:{alpha_type}"

    @staticmethod
    def live_feed_cache() -> str:
        return "cache:crypto_center:live_feed"

    @staticmethod
    def user_airdrop_progress(user_id: int, airdrop_id: str) -> str:
        return f"crypto_center:progress:{user_id}:{airdrop_id}"

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
    
    @staticmethod
    def get_coin_price_key(coin_id: str) -> str:
        """Ключ для кэша цены монеты."""
        return f"price:coin:{coin_id}"