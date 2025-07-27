# ===============================================================
# Файл: bot/utils/formatters.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Утилиты для форматирования данных в красивые,
# готовые к отправке текстовые сообщения.
# ===============================================================
from textwrap import dedent
from typing import List, Dict, Any

# --- ИСПРАВЛЕНИЕ: Импортируем правильные модели из правильного места ---
from bot.utils.models import (
    PriceInfo, 
    AsicMiner,
    MiningSessionResult,
    CalculationResult,
    HalvingInfo,
    NetworkStatus,
    NewsArticle
)
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---

# --- Форматтеры для публичных команд ---

def format_price_info(price_info: PriceInfo) -> str:
    """Форматирует информацию о цене монеты."""
    change = price_info.price_change_24h or 0
    emoji = "📈" if change >= 0 else "📉"
    text = (f"<b>{price_info.name} ({price_info.symbol})</b>\n"
            f"💹 Курс: <b>${price_info.price:,.4f}</b>\n"
            f"{emoji} 24ч: <b>{change:.2f}%</b>\n")
    if price_info.algorithm and price_info.algorithm != "Unknown":
        text += f"⚙️ Алгоритм: <code>{price_info.algorithm}</code>"
    return text

def format_top_asics(asics: List[AsicMiner], electricity_cost: float, last_update_minutes: int) -> str:
    """Форматирует топ ASIC-майнеров."""
    text_lines = [f"🏆 <b>Топ-{len(asics)} доходных ASIC</b> (чистыми, при цене э/э ${electricity_cost:.4f}/кВт·ч)\n"]
    for i, miner in enumerate(asics, 1):
        line = (f"{i}. <b>{miner.name}</b>\n"
                f"   Доход: <b>${miner.profitability:.2f}/день</b> | {miner.algorithm}")
        text_lines.append(line)
    
    text_lines.append(f"\n<i>Данные обновлены {last_update_minutes} минут назад.</i>")
    return "\n".join(text_lines)

def format_asic_passport(asic: AsicMiner, electricity_cost: float) -> str:
    """Формирует паспорт для ASIC с расчетом чистой прибыли."""
    # Прибыльность из Redis всегда "грязная", до вычета э/э
    gross_profitability = asic.profitability
    power = asic.power or 0

    # Расчет чистой прибыли происходит в AsicService, сюда приходит уже посчитанная
    net_profit = asic.profitability
    
    # Считаем "грязную" прибыль, прибавляя обратно стоимость электричества
    power_kwh_per_day = (power / 1000) * 24
    daily_cost = power_kwh_per_day * electricity_cost
    gross_profit_from_net = net_profit + daily_cost

    specs_map = {
        "algorithm": "Алгоритм", "hashrate": "Хешрейт",
        "power": "Потребление", "efficiency": "Эффективность"
    }
    
    specs_list = []
    for key, rus_name in specs_map.items():
        value = getattr(asic, key, None)
        if value and value != "N/A":
            unit = " Вт" if key == "power" else ""
            specs_list.append(f" ▫️ <b>{rus_name}:</b> {value}{unit}")

    specs_text = "\n".join(specs_list)

    profit_text = (
        f" ▪️ <b>Доход (грязными):</b> ${gross_profit_from_net:.2f}/день\n"
        f" ▪️ <b>Доход (чистыми):</b> ${net_profit:.2f}/день\n"
        f"    (при цене э/э ${electricity_cost:.4f}/кВт·ч)"
    )

    return (
        f"📋 <b>Паспорт устройства: {asic.name}</b>\n\n"
        f"<b><u>Экономика:</u></b>\n{profit_text}\n\n"
        f"<b><u>Тех. характеристики:</u></b>\n{specs_text}\n"
    )

# --- Форматтеры для Крипто-Центра ---

def format_crypto_feed(feed: List[NewsArticle]) -> str:
    """Форматирует ленту новостей с AI-анализом."""
    text = "<b>⚡️ Лента Крипто-Новостей (AI-Анализ)</b>\n"
    for item in feed:
        summary = item.ai_summary or 'Не удалось проанализировать.'
        text += (f"\n➖➖➖➖➖➖➖➖➖➖\n"
                 f"▪️ <b>Кратко:</b> <i>{summary}</i>\n"
                 f"▪️ <a href='{item.url}'>{item.title}</a>")
    return text

def format_mining_signals(signals: List[Dict[str, Any]]) -> str:
    """Форматирует список майнинг-сигналов."""
    text = "<b>⛏️ Сигналы для майнеров (AI)</b>\n"
    for signal in signals:
        text += (f"\n➖➖➖➖➖➖➖➖➖➖\n"
                 f"<b>{signal.get('name', 'N/A')}</b> (Статус: {signal.get('status', 'N/A')})\n"
                 f"<i>{signal.get('description', '')}</i>\n"
                 f"<b>Алгоритм:</b> <code>{signal.get('algorithm', 'N/A')}</code>\n"
                 f"<b>Оборудование:</b> {signal.get('hardware', 'N/A')}\n"
                 f"<a href='{signal.get('guide_url', '#')}'>Подробный гайд</a>")
    return text

# --- Форматтеры для рыночных данных ---

def format_halving_info(halving_info: HalvingInfo) -> str:
    """Форматирует информацию о халвинге."""
    return (
        f"⏳ <b>Обратный отсчет до халвинга Bitcoin</b>\n\n"
        f"◽️ Осталось блоков: <code>{halving_info.remaining_blocks:,}</code>\n"
        f"◽️ Следующий халвинг: примерно <b>{halving_info.estimated_date.strftime('%d %B %Y г.')}</b>\n\n"
        f"Награда за блок уменьшится с <code>{halving_info.current_reward} BTC</code> до <code>{halving_info.next_reward} BTC</code>."
    )

def format_network_status(network_status: NetworkStatus) -> str:
    """Форматирует информацию о статусе сети Bitcoin."""
    return (
        f"📡 <b>Текущий статус сети Bitcoin</b>\n\n"
        f"◽️ Сложность: <code>{network_status.difficulty:,.0f}</code>\n"
        f"◽️ Транзакций в мемпуле: <code>{network_status.mempool_txs:,}</code>\n"
        f"◽️ Рекомендуемая комиссия (быстрая): <code>{network_status.suggested_fee} сат/vB</code>"
    )

# --- Форматтеры для фоновых задач и игры ---

def format_morning_summary(btc_price: str, eth_price: str, fng_index: str) -> str:
    """Форматирует утреннюю сводку."""
    return (
        "☕️ <b>Доброе утро! Ваша крипто-сводка:</b>\n\n"
        f"<b>Bitcoin (BTC):</b> ${btc_price}\n"
        f"<b>Ethereum (ETH):</b> ${eth_price}\n\n"
        f"<b>Индекс страха и жадности:</b> {fng_index}"
    )

def format_leaderboard(top_users: List[Dict[str, Any]]) -> str:
    """Форматирует еженедельную таблицу лидеров."""
    if not top_users:
        return "🏆 <b>Еженедельный лидерборд майнеров</b>\n\nНа этой неделе у нас пока нет лидеров. Начните играть, чтобы попасть в топ!"

    leaderboard_lines = []
    medals = ["🥇", "🥈", "🥉", "4.", "5."]
    for i, user_data in enumerate(top_users):
        username = f"@{user_data['username']}" if user_data.get('username') else f"User ID {user_data['user_id']}"
        balance = user_data['balance']
        leaderboard_lines.append(f"{medals[i]} {username} - <b>{balance:.2f} монет</b>")
    
    leaderboard_text = "\n".join(leaderboard_lines)
    return (
        "🏆 <b>Еженедельный лидерборд майнеров</b>\n\n"
        "Вот наши лучшие игроки на этой неделе:\n\n"
        f"{leaderboard_text}\n\n"
        "Продолжайте в том же духе! Новый лидерборд — в следующую пятницу."
    )

def format_mining_session_result(result: MiningSessionResult) -> str:
    """Форматирует результат завершенной майнинг-сессии."""
    return (
        f"✅ Майнинг-сессия на <b>{result.asic_name}</b> завершена!\n\n"
        f"📈 Грязный доход: <b>{result.gross_earned:.4f} монет</b>\n"
        f"⚡️ Расход на эл-во ({result.tariff_name}): <b>{result.electricity_cost:.4f} монет</b>\n\n"
        f"💰 Чистая прибыль зачислена на баланс: <b>{result.net_earned:.4f} монет</b>."
    )

# --- Форматтеры для калькулятора ---

def format_calculation_result(result: CalculationResult) -> str:
    """Форматирует результат расчета доходности."""
    calc_data = result.calculation_data
    input_data = result.input_data
    
    # Конвертируем USD в RUB для отображения
    gross_rub_day = calc_data.gross_revenue_usd_daily * input_data.usd_rub_rate
    gross_rub_month = calc_data.gross_revenue_usd_monthly * input_data.usd_rub_rate
    net_rub_day = calc_data.net_profit_usd_daily * input_data.usd_rub_rate
    net_rub_month = calc_data.net_profit_usd_monthly * input_data.usd_rub_rate
    net_rub_year = calc_data.net_profit_usd_yearly * input_data.usd_rub_rate

    result_text = dedent(f"""
        📊 <b>Результаты расчета доходности</b>

        <b>Исходные данные:</b>
        - Цена BTC: <code>${input_data.btc_price_usd:,.2f}</code>
        - Курс USD/RUB: <code>{input_data.usd_rub_rate:,.2f} ₽</code>
        - Хешрейт сети: <code>{input_data.network_hashrate_ths / 1_000_000:,.2f} EH/s</code>
        - Награда за блок: <code>{input_data.block_reward_btc:.4f} BTC</code>

        ---

        <b>💰 Доходы (грязными):</b>
        - В день: <code>${calc_data.gross_revenue_usd_daily:.2f}</code> / <code>{gross_rub_day:.2f} ₽</code>
        - В месяц: <code>${calc_data.gross_revenue_usd_monthly:.2f}</code> / <code>{gross_rub_month:.2f} ₽</code>

        <b>🔌 Расходы:</b>
        - Электричество/день: <code>${calc_data.electricity_cost_usd_daily:.2f}</code>
        - Комиссия пула ({result.pool_commission}%)/день: <code>${calc_data.pool_fee_usd_daily:.2f}</code>
        - <b>Всего расходов/день:</b> <code>${calc_data.total_expenses_usd_daily:.2f}</code>

        ---

        ✅ <b>Чистая прибыль:</b>
        - <b>В день:</b> <code>${calc_data.net_profit_usd_daily:.2f}</code> / <code>{net_rub_day:.2f} ₽</code>
        - <b>В месяц:</b> <code>${calc_data.net_profit_usd_monthly:.2f}</code> / <code>{net_rub_month:.2f} ₽</code>
        - <b>В год:</b> <code>${calc_data.net_profit_usd_yearly:.2f}</code> / <code>{net_rub_year:.2f} ₽</code>
    """)

    if calc_data.net_profit_usd_daily < 0:
        result_text += "\n\n⚠️ <b>Внимание:</b> при текущих параметрах майнинг невыгоден."
        
    return result_text.strip()
