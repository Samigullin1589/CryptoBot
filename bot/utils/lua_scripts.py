# =================================================================================
# Файл: bot/utils/lua_scripts.py (ВЕРСИЯ "ГЕНИЙ 2.0" - ОКОНЧАТЕЛЬНАЯ)
# Описание: Коллекция LUA-скриптов для выполнения атомарных операций в Redis.
# =================================================================================

class LuaScripts:
    # ... (существующие скрипты START_MINING_SESSION и END_MINING_SESSION) ...

    LIST_ITEM_FOR_SALE = """
        -- Атомарно выставляет предмет из ангара на рынок
        -- KEYS[1]: user_hangar_key (e.g., game:hangar:user_id)
        -- KEYS[2]: market_listing_data_key (e.g., market:listing:listing_id)
        -- KEYS[3]: market_listings_by_price_key (e.g., market:listings:price)
        -- ARGV[1]: asic_id
        -- ARGV[2]: listing_id
        -- ARGV[3]: seller_id
        -- ARGV[4]: price
        -- ARGV[5]: timestamp

        local asic_data = redis.call('HGET', KEYS[1], ARGV[1])
        if not asic_data then
            return 0 -- Предмет не найден в ангаре
        end
        
        redis.call('HDEL', KEYS[1], ARGV[1])
        redis.call('HMSET', KEYS[2], 'id', ARGV[2], 'seller_id', ARGV[3], 'price', ARGV[4], 'created_at', ARGV[5], 'asic_data', asic_data)
        redis.call('ZADD', KEYS[3], ARGV[4], ARGV[2])
        
        return 1
    """

    CANCEL_LISTING = """
        -- Атомарно снимает лот с продажи и возвращает предмет в ангар
        -- KEYS[1]: market_listing_data_key
        -- KEYS[2]: market_listings_by_price_key
        -- KEYS[3]: user_hangar_key
        -- ARGV[1]: listing_id
        -- ARGV[2]: user_id (для проверки владения)

        local listing_data = redis.call('HGETALL', KEYS[1])
        if #listing_data == 0 or listing_data[4] ~= ARGV[2] then
            return 0 -- Лот не найден или пользователь не является владельцем
        end
        
        local asic_id = cjson.decode(listing_data[10])['id']
        
        redis.call('HSET', KEYS[3], asic_id, listing_data[10])
        redis.call('ZREM', KEYS[2], ARGV[1])
        redis.call('DEL', KEYS[1])
        
        return 1
    """

    BUY_ITEM_FROM_MARKET = """
        -- Атомарно обрабатывает покупку предмета с рынка
        -- KEYS[1]: market_listing_data_key
        -- KEYS[2]: market_listings_by_price_key
        -- KEYS[3]: buyer_profile_key
        -- ARGV[1]: listing_id
        -- ARGV[2]: buyer_id
        -- ARGV[3]: commission_rate

        local listing_data = redis.call('HGETALL', KEYS[1])
        if #listing_data == 0 then return -3 end -- Лот не существует

        local seller_id = listing_data[4]
        if seller_id == ARGV[2] then return -1 end -- Попытка купить свой лот

        local price = tonumber(listing_data[6])
        local buyer_balance = tonumber(redis.call('HGET', KEYS[3], 'balance') or 0)
        if buyer_balance < price then return -2 end -- Недостаточно средств
        
        local asic_data_str = listing_data[10]
        local asic_id = cjson.decode(asic_data_str)['id']
        local seller_profile_key = 'game:profile:' .. seller_id
        local buyer_hangar_key = 'game:hangar:' .. ARGV[2]

        local commission = price * tonumber(ARGV[3])
        local seller_earning = price - commission

        -- Атомарная транзакция
        redis.call('HINCRBYFLOAT', KEYS[3], 'balance', -price)
        redis.call('HINCRBYFLOAT', seller_profile_key, 'balance', seller_earning)
        redis.call('HSET', buyer_hangar_key, asic_id, asic_data_str)
        redis.call('ZREM', KEYS[2], ARGV[1])
        redis.call('DEL', KEYS[1])

        return 1 -- Успешная покупка
    """