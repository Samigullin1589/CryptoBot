# ===============================================================
# Файл: bot/utils/keys.py (ПРОДАКШН-ВЕРСИЯ 2025 - ОКОНЧАТЕЛЬНАЯ v9)
# ===============================================================

class KeyFactory:
    """Создает стандартизированные ключи для Redis."""

    # --- User Service ---
    @staticmethod
    def user_profile(user_id: int) -> str:
        return f"user:profile:{user_id}"
    @staticmethod
    def user_info(user_id: int) -> str:
        return f"user:info:{user_id}"
    @staticmethod
    def known_users_set() -> str:
        return "users:known"
    @staticmethod
    def user_first_seen_zset() -> str:
        return "stats:user:first_seen"
    @staticmethod
    def user_last_activity_zset() -> str:
        return "stats:user:activity"

    # --- Admin Service ---
    @staticmethod
    def stats_actions_zset() -> str:
        return "stats:actions"

    # --- ASIC Service ---
    @staticmethod
    def asics_sorted_set() -> str:
        return "asics:sorted_by_profit"
    @staticmethod
    def asic_hash(normalized_name: str) -> str:
        return f"asic:{normalized_name}"
    @staticmethod
    def asics_last_update() -> str:
        return "asics:last_update_ts"

    # --- Mining Game ---
    @staticmethod
    def game_profile(user_id: int) -> str:
        return f"game:profile:{user_id}"
    @staticmethod
    def game_active_session(user_id: int) -> str:
        return f"game:session:{user_id}"
    @staticmethod
    def game_global_stats() -> str:
        return "game:stats"
    @staticmethod
    def game_referred_users_set() -> str:
        return "game:referred_users"
    
    # --- CoinList Service ---
    @staticmethod
    def coin_info_hash(coin_id: str) -> str:
        return f"coin:info:{coin_id}"
    @staticmethod
    def coin_search_index_hash() -> str:
        return "coins:search_index"
        
    # --- Price Service ---
    @staticmethod
    def price_cache(coin_id: str) -> str:
        return f"price:cache:{coin_id}"

    # --- Market Data Service ---
    @staticmethod
    def fng_index_cache() -> str:
        return "market:cache:fng_index"
    @staticmethod
    def halving_info_cache() -> str:
        return "market:cache:halving_info"
    @staticmethod
    def btc_network_status_cache() -> str:
        return "market:cache:btc_network_status"
        
    # --- News Service ---
    @staticmethod
    def news_deduplication_set() -> str:
        return "news:seen_hashes"
        
    # --- CryptoCenter Service ---
    @staticmethod
    def airdrop_alpha_cache() -> str:
        return "crypto_center:cache:airdrops"
    @staticmethod
    def mining_alpha_cache() -> str:
        return "crypto_center:cache:mining"
    @staticmethod
    def live_feed_cache() -> str:
        return "crypto_center:cache:feed"
    @staticmethod
    def user_airdrop_progress(user_id: int, airdrop_id: str) -> str:
        return f"user:{user_id}:airdrop_progress:{airdrop_id}"

    # --- Stop Word Service ---
    @staticmethod
    def stop_words_set() -> str:
        return "moderation:stop_words"
