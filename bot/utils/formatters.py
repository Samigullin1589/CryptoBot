# =================================================================================
# Файл: bot/utils/formatters.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ ОБЪЕДИНЕННАЯ)
# Описание: Вспомогательные функции для форматирования данных в текст.
# ИСПРАВЛЕНИЕ: Добавлены недостающие функции format_halving_info и format_network_status
# для устранения ImportError и обеспечения полной функциональности.
# =================================================================================
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from bot.utils.models import AsicMiner, NewsArticle, Coin

# --- Форматтеры для раздела ASIC ---

def format_asic_list(asics: List[AsicMiner], page: int, total_pages: int) -> str:
    """Форматирует список ASIC-майнеров для вывода в сообщении."""
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
    """Формирует текстовый паспорт для ASIC с расчетом чистой прибыли."""
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
    """Форматирует список новостей для вывода в сообщении."""
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
    """Форматирует информацию о цене монеты."""
    price = price_data.get('price')
    price_str = f"{price:,.4f}".rstrip('0').rstrip('.') if price else "N/A"
    return (
        f"💹 <b>Курс {coin.name} ({coin.symbol.upper()})</b>\n\n"
        f"<b>Цена:</b> ${price_str}"
    )

# --- НЕДОСТАЮЩИЕ ФОРМАТТЕРЫ ДЛЯ РЫНОЧНЫХ ДАННЫХ ---

def format_halving_info(halving_data: Dict[str, Any]) -> str:
    """
    Форматирует информацию о халвинге Bitcoin.
    """
    progress = halving_data.get('progressPercent', 0)
    remaining_blocks = halving_data.get('remainingBlocks', 0)
    # Предполагаем, что сервис вернет уже отформатированную дату
    estimated_date = halving_data.get('estimated_date', 'неизвестно')
    
    return (
        f"⏳ <b>Халвинг Bitcoin</b>\n\n"
        f"Прогресс до следующего халвинга: <b>{progress:.2f}%</b>\n"
        f"Осталось блоков: <b>{remaining_blocks:,}</b>\n"
        f"Ориентировочная дата: <b>{estimated_date}</b>"
    )

def format_network_status(network_data: Dict[str, Any]) -> str:
    """
    Форматирует информацию о статусе сети Bitcoin.
    """
    hashrate_ehs = network_data.get('hashrate_ehs', 0.0)
    
    return (
        f"📡 <b>Статус сети Bitcoin</b>\n\n"
        f"Хешрейт: <b>{hashrate_ehs:.2f} EH/s</b>"
    )