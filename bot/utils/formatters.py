# =================================================================================
# Файл: bot/utils/formatters.py (ВЕРСИЯ "Distinguished Engineer" - ПОЛНАЯ РЕАЛИЗАЦИЯ)
# Описание: Вспомогательные функции для форматирования данных в текст.
# ИСПРАВЛЕНИЕ: Полностью переписан без заглушек. Обновлены все функции
#              для работы с новыми структурами данных.
# =================================================================================
from typing import List, Dict, Any
from datetime import datetime, timezone

from bot.utils.models import AsicMiner, NewsArticle, Coin, CalculationResult

# --- Форматтеры для раздела ASIC ---
def format_asic_list(asics: List[AsicMiner], page: int, total_pages: int) -> str:
    if not asics:
        return "Нет доступных ASIC для отображения."

    header = "⚙️ <b>Топ ASIC по чистой прибыли (Net Profit)</b>\n\n"
    body = []
    for asic in asics:
        profit_str = f"{asic.net_profit:+.2f}$/день" if hasattr(asic, 'net_profit') and asic.net_profit is not None else "N/A"
        power_str = f"{asic.power}W" if asic.power else "N/A"
        body.append(
            f"🔹 <b>{asic.name}</b>\n"
            f"   - Прибыль: <b>{profit_str}</b>\n"
            f"   - Потребление: {power_str}"
        )
    
    footer = f"\n\n📄 Страница {page + 1} из {total_pages}"
    return header + "\n".join(body) + footer

def format_asic_passport(asic: AsicMiner, electricity_cost: float) -> str:
    specs_map = {
        "algorithm": "Алгоритм", "hashrate": "Хешрейт",
        "power": "Потребление"
    }
    specs_list = []
    for key, rus_name in specs_map.items():
        value = getattr(asic, key, None)
        if value and value != "N/A":
            unit = " Вт" if key == "power" else ""
            specs_list.append(f" ▫️ <b>{rus_name}:</b> {value}{unit}")
    specs_text = "\n".join(specs_list)

    profit_text = (
        f" ▪️ <b>Доход (грязными):</b> ${getattr(asic, 'gross_profit', 0.0):.2f}/день\n"
        f" ▪️ <b>Затраты на э/э:</b> ${getattr(asic, 'electricity_cost_per_day', 0.0):.2f}/день\n"
        f" ▪️ <b>Доход (чистыми):</b> ${getattr(asic, 'net_profit', 0.0):.2f}/день\n"
        f" <i>(при цене э/э ${electricity_cost:.4f}/кВт·ч)</i>"
    )

    return (
        f"📋 <b>Паспорт устройства: {asic.name}</b>\n\n"
        f"<b><u>Экономика:</u></b>\n{profit_text}\n\n"
        f"<b><u>Тех. характеристики:</u></b>\n{specs_text}\n"
    )

# --- Форматтеры для раздела новостей ---
def format_news_list(articles: List[NewsArticle], page: int, total_pages: int) -> str:
    if not articles:
        return "Нет доступных новостей."

    header = "📰 <b>Последние новости из мира криптовалют</b>\n\n"
    body = []
    for article in articles:
        dt_object = datetime.fromtimestamp(article.timestamp, tz=timezone.utc)
        time_str = dt_object.strftime('%d.%m.%Y %H:%M')
        body.append(
            f"▪️ <a href='{article.url}'>{article.title}</a>\n"
            f"  <I>({article.source} - {time_str})</I>"
        )
    
    footer = f"\n\n📄 Страница {page + 1} из {total_pages}"
    return header + "\n".join(body) + footer

# --- Форматтеры для раздела курсов ---
def format_price_info(coin: Coin, price_data: Dict[str, Any]) -> str:
    price = price_data.get('price')
    price_str = f"{price:,.4f}".rstrip('0').rstrip('.') if price else "N/A"
    return (
        f"💹 <b>Курс {coin.name} ({coin.symbol.upper()})</b>\n\n"
        f"<b>Цена:</b> ${price_str}"
    )

# --- Форматтеры для рыночных данных ---
def format_halving_info(halving_data: Dict[str, Any]) -> str:
    """Форматирует информацию о халвинге Bitcoin."""
    progress = halving_data.get('progressPercent', 0)
    remaining_blocks = halving_data.get('remainingBlocks', 0)
    estimated_date = halving_data.get('estimated_date', 'неизвестно')
    
    return (
        f"⏳ <b>Халвинг Bitcoin</b>\n\n"
        f"Прогресс до следующего халвинга: <b>{progress:.2f}%</b>\n"
        f"Осталось блоков: <b>{remaining_blocks:,}</b>\n"
        f"Ориентировочная дата халвинга: <b>{estimated_date}</b>"
    )

def format_network_status(network_data: Dict[str, Any]) -> str:
    """Форматирует информацию о состоянии сети Bitcoin."""
    hashrate_ehs = network_data.get('hashrate_ehs', 0.0)
    difficulty_change = network_data.get('difficulty_change', 0.0)
    estimated_retarget_date = network_data.get('estimated_retarget_date', 'N/A')
    
    change_sign = "+" if difficulty_change > 0 else ""
    
    return (
        f"📡 <b>Статус сети Bitcoin</b>\n\n"
        f"Хешрейт: <b>{hashrate_ehs:.2f} EH/s</b>\n"
        f"След. изменение сложности: <b>~{change_sign}{difficulty_change:.2f}%</b>\n"
        f"<i>(Ориентировочно {estimated_retarget_date})</i>"
    )

# --- Форматтер для калькулятора ---
def format_calculation_result(result: CalculationResult) -> str:
    net_profit_weekly = result.net_profit_usd_daily * 7
    net_profit_monthly = result.net_profit_usd_daily * 30.44
    net_profit_yearly = result.net_profit_usd_daily * 365.25
    net_profit_rub_daily = result.net_profit_usd_daily * result.usd_rub_rate
    profit_color_emoji = "🟢" if result.net_profit_usd_daily > 0 else "🔴"

    return (
        f"📊 <b>Результаты расчета доходности</b>\n\n"
        f"<b><u>Доходы:</u></b>\n"
        f"▫️ Грязный доход: <b>${result.gross_revenue_usd_daily:,.2f}</b> / день\n\n"
        f"<b><u>Расходы:</u></b>\n"
        f"▫️ Электроэнергия: ${result.electricity_cost_usd_daily:,.2f} / день\n"
        f"▫️ Комиссия пула: ${result.pool_fee_usd_daily:,.2f} / день\n"
        f"▫️ <b>Итого расходов:</b> ${result.total_expenses_usd_daily:,.2f} / день\n\n"
        f"<b><u>{profit_color_emoji} Чистая прибыль:</u></b>\n"
        f"💵 <b>${result.net_profit_usd_daily:,.2f} / день</b>\n"
        f"💵 ${net_profit_weekly:,.2f} / неделя\n"
        f"💵 ${net_profit_monthly:,.2f} / месяц\n"
        f"💵 ${net_profit_yearly:,.2f} / год\n\n"
        f"🇷🇺 В рублях: ≈ {net_profit_rub_daily:,.2f} ₽ / день\n\n"
        f"<i>Расчеты основаны на текущем курсе BTC ≈ ${int(result.btc_price_usd):,} и сложности сети. "
        f"Реальная доходность может отличаться.</i>"
    )