# ===============================================================
# Файл: bot/utils/formatters.py (НОВЫЙ ФАЙЛ)
# Описание: Утилиты для форматирования данных в текст для Telegram.
# ===============================================================
from bot.utils.models import AsicMiner, PriceInfo

def format_asic_passport(asic: AsicMiner, electricity_cost: float) -> str:
    """Формирует текстовый паспорт для ASIC с расчетом чистой прибыли."""
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
        f" ▪️ <b>Доход (грязными):</b> ${asic.gross_profit:.2f}/день\n"
        f" ▪️ <b>Затраты на э/э:</b> ${asic.electricity_cost_per_day:.2f}/день\n"
        f" ▪️ <b>Доход (чистыми):</b> ${asic.net_profit:.2f}/день\n"
        f" <i>(при цене э/э ${electricity_cost:.4f}/кВт·ч)</i>"
    )

    return (
        f"📋 <b>Паспорт устройства: {asic.name}</b>\n\n"
        f"<b><u>Экономика:</u></b>\n{profit_text}\n\n"
        f"<b><u>Тех. характеристики:</u></b>\n{specs_text}\n"
    )

def format_price_info(price_info: PriceInfo) -> str:
    """Форматирует информацию о цене монеты."""
    change_24h = price_info.price_change_percentage_24h or 0
    emoji = "📈" if change_24h >= 0 else "📉"
    
    market_cap_text = f"Капитализация: <b>${price_info.market_cap:,.0f}</b>" if price_info.market_cap else ""
    
    return (
        f"💎 <b>{price_info.name} ({price_info.symbol.upper()})</b>\n\n"
        f"<b>Цена:</b> ${price_info.current_price:,.4f}\n"
        f"<b>Изменение (24ч):</b> {change_24h:.2f}% {emoji}\n\n"
        f"{market_cap_text}"
    )
