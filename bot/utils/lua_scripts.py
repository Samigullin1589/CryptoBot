# =================================================================================
# Файл: bot/utils/lua_scripts.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ ПОЛНАЯ)
# Описание: Коллекция LUA-скриптов для выполнения атомарных операций в Redis.
# ИСПРАВЛЕНИЕ: Добавлены недостающие скрипты START_MINING_SESSION и END_MINING_SESSION.
# =================================================================================

class LuaScripts:
    """
    Хранит LUA-скрипты как строковые константы для предзагрузки в Redis.
    Использование LUA-скриптов гарантирует атомарность сложных операций.
    """

    START_MINING_SESSION = """
        -- Атомарно начинает сессию майнинга: перемещает ASIC из ангара в сессию.
        -- KEYS[1]: active_session_key (e.g., game:session:user_id)
        -- KEYS[2]: user_hangar_key (e.g., game:hangar:user_id)
        -- KEYS[3]: global_stats_key (e.g., game:stats)
        -- ARGV[1]: asic_id
        -- ARGV[2]: asic_name
        -- ARGV[3]: asic_power
        -- ARGV[4]: asic_profitability
        -- ARGV[5]: start_time_unix
        -- ARGV[6]: end_time_iso
        -- ARGV[7]: tariff_name
        -- ARGV[8]: tariff_cost_per_kwh

        -- 1. Проверяем, есть ли ASIC в ангаре
        local asic_data = redis.call('HGET', KEYS[2], ARGV[1])
        if not asic_data then
            return 0 -- ASIC не найден
        end

        -- 2. Перемещаем ASIC из ангара в активную сессию
        redis.call('HDEL', KEYS[2], ARGV[1])
        redis.call('HMSET', KEYS[1],
            'asic_id', ARGV[1],
            'asic_name', ARGV[2],
            'asic_power', ARGV[3],
            'asic_profitability', ARGV[4],
            'start_time_unix', ARGV[5],
            'end_time_iso', ARGV[6],
            'tariff_name', ARGV[7],
            'tariff_cost_per_kwh', ARGV[8],
            'asic_data_json', asic_data
        )
        
        -- 3. Обновляем глобальную статистику
        redis.call('HINCRBY', KEYS[3], 'active_sessions', 1)

        return 1 -- Успех
    """

    END_MINING_SESSION = """
        -- Атомарно завершает сессию: рассчитывает прибыль, возвращает ASIC в ангар.
        -- KEYS[1]: active_session_key
        -- KEYS[2]: user_game_profile_key
        -- KEYS[3]: user_hangar_key
        -- KEYS[4]: global_stats_key
        -- ARGV[1]: current_time_unix
        -- ARGV[2]: session_duration_seconds
        -- ARGV[3]: profit_multiplier
        -- ARGV[4]: cost_multiplier

        -- 1. Проверяем, существует ли сессия
        if redis.call('EXISTS', KEYS[1]) == 0 then
            return nil
        end

        -- 2. Получаем данные сессии
        local session_data = redis.call('HGETALL', KEYS[1])
        local asic_id, asic_name, power, profitability, tariff_name, tariff_cost, asic_data_json
        for i=1, #session_data, 2 do
            if session_data[i] == 'asic_id' then asic_id = session_data[i+1] end
            if session_data[i] == 'asic_name' then asic_name = session_data[i+1] end
            if session_data[i] == 'asic_power' then power = tonumber(session_data[i+1]) end
            if session_data[i] == 'asic_profitability' then profitability = tonumber(session_data[i+1]) end
            if session_data[i] == 'tariff_name' then tariff_name = session_data[i+1] end
            if session_data[i] == 'tariff_cost_per_kwh' then tariff_cost = tonumber(session_data[i+1]) end
            if session_data[i] == 'asic_data_json' then asic_data_json = session_data[i+1] end
        end

        -- 3. Расчеты
        local power_kwh = (power / 1000) * (tonumber(ARGV[2]) / 3600)
        local total_electricity_cost = (power_kwh * tariff_cost) * tonumber(ARGV[4])
        local gross_earned = (profitability / 24) * (tonumber(ARGV[2]) / 3600) * tonumber(ARGV[3])
        local net_earned = gross_earned - total_electricity_cost

        -- 4. Обновляем профиль пользователя
        redis.call('HINCRBYFLOAT', KEYS[2], 'balance', net_earned)
        redis.call('HINCRBYFLOAT', KEYS[2], 'total_earned', gross_earned)
        
        -- 5. Возвращаем ASIC в ангар
        redis.call('HSET', KEYS[3], asic_id, asic_data_json)
        
        -- 6. Удаляем сессию и обновляем глобальную статистику
        redis.call('DEL', KEYS[1])
        redis.call('HINCRBY', KEYS[4], 'active_sessions', -1)

        -- 7. Возвращаем результат в виде JSON
        local result = {
            result = {
                asic_name = asic_name,
                user_tariff_name = tariff_name,
                gross_earned = gross_earned,
                total_electricity_cost = total_electricity_cost,
                net_earned = net_earned
            }
        }
        return cjson.encode(result)
    """

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
        
        local asic_data_str = listing_data[10]
        local asic_id = cjson.decode(asic_data_str)['id']
        
        redis.call('HSET', KEYS[3], asic_id, asic_data_str)
        redis.call('ZREM', KEYS[2], ARGV[1])
        redis.call('DEL', KEYS[1])
        
        return 1
    """

    BUY_ITEM_FROM_MARKET = """
        -- Атомарно обрабатывает покупку предмета с рынка
        -- KEYS[1]: market_listing_data_key
        -- KEYS[2]: market_listings_by_price_key
        -- KEYS[3]: buyer_profile_key
        -- KEYS[4]: buyer_hangar_key
        -- KEYS[5]: seller_profile_key
        -- ARGV[1]: listing_id
        -- ARGV[2]: buyer_id
        -- ARGV[3]: seller_id
        -- ARGV[4]: commission_rate

        local listing_data_raw = redis.call('HGETALL', KEYS[1])
        if #listing_data_raw == 0 then return -3 end -- Лот не существует

        -- Преобразуем массив в словарь
        local listing_data = {}
        for i=1, #listing_data_raw, 2 do
            listing_data[listing_data_raw[i]] = listing_data_raw[i+1]
        end

        if listing_data['seller_id'] == ARGV[2] then return -1 end -- Попытка купить свой лот

        local price = tonumber(listing_data['price'])
        local buyer_balance = tonumber(redis.call('HGET', KEYS[3], 'balance') or 0)
        if buyer_balance < price then return -2 end -- Недостаточно средств
        
        local asic_data_str = listing_data['asic_data']
        local asic_id = cjson.decode(asic_data_str)['id']

        local commission = price * tonumber(ARGV[4])
        local seller_earning = price - commission

        -- Атомарная транзакция
        redis.call('HINCRBYFLOAT', KEYS[3], 'balance', -price)
        redis.call('HINCRBYFLOAT', KEYS[5], 'balance', seller_earning)
        redis.call('HSET', KEYS[4], asic_id, asic_data_str)
        redis.call('ZREM', KEYS[2], ARGV[1])
        redis.call('DEL', KEYS[1])

        return 1 -- Успешная покупка
    """
