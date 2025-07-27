# ===============================================================
# Файл: bot/utils/formatters.py (ОБНОВЛЕНИЕ)
# Описание: Добавлена функция format_price_info для единообразного
# отображения информации о курсе криптовалют.
# ===============================================================
from typing import Dict, Any

from bot.services.asic_service import AsicService # Для доступа к бизнес-логике расчета
from bot.services.price_service import CryptoCoin # Модель данных монеты

def format_asic_passport(data: Dict[str, Any], electricity_cost: float = 0.0) -> str:
    """
    Формирует красивый и информативный текстовый паспорт для ASIC.
    
    :param data: Словарь с данными об ASIC из Redis/API.
    :param electricity_cost: Персональная стоимость электроэнергии пользователя.
    :return: Отформатированная строка для отправки в Telegram.
    """
    name = data.get('name', "Неизвестная модель")
    gross_profitability = float(data.get('profitability', 0.0))
    power = int(data.get('power', 0))

    # Расчет чистой прибыли делегируется соответствующему сервису
    net_profit = AsicService.calculate_net_profit(gross_profitability, power, electricity_cost)

    specs_map = {
        "algorithm": "Алгоритм",
        "hashrate": "Хешрейт",
        "power": "Потребление",
        "efficiency": "Эффективность"
    }
    
    specs_list = []
    for key, rus_name in specs_map.items():
        value = data.get(key)
        if value and str(value).strip() and value != "N/A":
            unit = " Вт" if key == "power" else ""
            specs_list.append(f"  ▫️ <b>{rus_name}:</b> {value}{unit}")

    specs_text = "\n".join(specs_list) if specs_list else "  ▫️ Характеристики не найдены."

    # Формируем блок с экономикой
    profit_text = (
        f"  ▪️ <b>Доход (грязными):</b> ${gross_profitability:.2f}/день\n"
        f"  ▪️ <b>Доход (чистыми):</b> ${net_profit:.2f}/день\n"
        f"  <i>*расчет при цене э/э ${electricity_cost:.4f}/кВт·ч</i>"
    )

    text = (
        f"📋 <b>Паспорт устройства: {name}</b>\n\n"
        f"<b><u>Экономика:</u></b>\n{profit_text}\n\n"
        f"<b><u>Технические характеристики:</u></b>\n{specs_text}\n"
    )
    return text

def format_price_info(coin: CryptoCoin) -> str:
    """
    Формирует текстовое представление информации о курсе монеты.
    
    :param coin: Объект CryptoCoin с данными о монете.
    :return: Отформатированная строка.
    """
    change = coin.price_change_24h or 0
    emoji = "📈" if change >= 0 else "📉"
    
    text = (
        f"<b>{coin.name} ({coin.symbol})</b>\n"
        f"💹 Курс: <b>${coin.price:,.4f}</b>\n"
        f"{emoji} 24ч: <b>{change:.2f}%</b>\n"
    )
    if coin.algorithm:
        text += f"⚙️ Алгоритм: <code>{coin.algorithm}</code>"
    
    return text
