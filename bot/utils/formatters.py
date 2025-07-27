# ===============================================================
# Файл: bot/utils/formatters.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Утилиты для форматирования данных в красивые,
# готовые к отправке текстовые сообщения.
# ===============================================================
import logging
from textwrap import dedent
from typing import List, Optional

from bot.utils.models import (
    PriceInfo, HalvingInfo, NetworkStatus, 
    MiningSessionResult, CalculationResult, AsicMiner, 
    AirdropProject, MiningSignal, NewsArticle
)
from bot.utils.text_utils import sanitize_html

logger = logging.getLogger(__name__)

# --- ФОРМАТТЕРЫ ДЛЯ ОСНОВНЫХ КОМАНД ---

def format_price_info(price_info: PriceInfo) -> str:
    """Форматирует информацию о цене монеты."""
    change = price_info.price_change_24h or 0
    emoji = "📈" if change >= 0 else "📉"
    
    text = (
        f"<b>{price_info.name} ({price_info.symbol})</b>\n"
        f"💹 Курс: <b>${price_info.price:,.4f}</b>\n"
        f"{emoji} 24ч: <b>{change:.2f}%</b>\n"
    )
    if price_info.algorithm:
        text += f"⚙️ Алгоритм: <code>{price_info.algorithm}</code>"
    
    return text

def format_news(articles: List[NewsArticle]) -> str:
    """Форматирует список новостей в красивое сообщение."""
    if not articles:
        return "📰 <b>Последние крипто-новости:</b>\n\nНовостей пока нет."

    text_lines = ["📰 <b>Последние крипто-новости:</b>"]
    for article in articles:
        safe_title = sanitize_html(article.title)
        text_lines.append(f"🔹 <a href=\"{article.url}\">{safe_title}</a>")
    
    return "\n\n".join(text_lines)

# --- ФОРМАТТЕРЫ ДЛЯ РЫНОЧНЫХ ДАННЫХ ---

def format_halving_info(halving_info: HalvingInfo) -> str:
    """Форматирует информацию о халвинге Bitcoin."""
    return (
        f"⏳ <b>Обратный отсчет до халвинга Bitcoin</b>\n\n"
        f"◽️ Осталось блоков: <code>{halving_info.remaining_blocks:,}</code>\n"
        f"◽️ Следующий халвинг: примерно <b>{halving_info.estimated_date.strftime('%d %B %Y г.')}</b>\n\n"
        f"Награда за блок уменьшится с <code>{halving_info.current_reward} BTC</code> до <code>{halving_info.next_reward} BTC</code>."
    )

def format_network_status(network_status: NetworkStatus) -> str:
    """Форматирует информацию о текущем статусе сети Bitcoin."""
    return (
        f"📡 <b>Текущий статус сети Bitcoin</b>\n\n"
        f"◽️ Сложность: <code>{network_status.difficulty:,.0f}</code>\n"
        f"◽️ Транзакций в мемпуле: <code>{network_status.mempool_transactions:,}</code>\n"
        f"◽️ Рекомендуемая комиссия (быстрая): <code>{network_status.suggested_fee} сат/vB</code>"
    )

# --- ФОРМАТТЕРЫ ДЛЯ ИГРЫ И ИНСТРУМЕНТОВ ---

def format_mining_session_result(result: MiningSessionResult) -> str:
    """Форматирует отчет о завершенной майнинг-сессии."""
    return (
        f"✅ Майнинг-сессия на <b>{result.asic_name}</b> завершена!\n\n"
        f"📈 Грязный доход: <b>{result.gross_earned:.4f} монет</b>\n"
        f"⚡️ Расход на эл-во ({result.tariff_name}): <b>{result.electricity_cost:.4f} монет</b>\n\n"
        f"💰 Чистая прибыль зачислена на баланс: <b>{result.net_earned:.4f} монет</b>."
    )

def format_calculation_result(result: CalculationResult) -> str:
    """Форматирует результаты расчета доходности из калькулятора."""
    text = dedent(f"""
        📊 <b>Результаты расчета доходности</b>

        <b>Исходные данные:</b>
        - Цена BTC: <code>${result.btc_price_usd:,.2f}</code>
        - Курс USD/RUB: <code>{result.usd_rub_rate:,.2f} ₽</code>
        - Хешрейт сети: <code>{result.network_hashrate_ths / 1_000_000:,.2f} EH/s</code>
        - Награда за блок: <code>{result.block_reward_btc:.4f} BTC</code>

        ---

        <b>💰 Доходы (грязными):</b>
        - В день: <code>${result.gross_revenue_usd_daily:.2f}</code> / <code>{result.gross_revenue_rub_daily:.2f} ₽</code>
        - В месяц: <code>${result.gross_revenue_usd_monthly:.2f}</code> / <code>{result.gross_revenue_rub_monthly:.2f} ₽</code>

        <b>🔌 Расходы:</b>
        - Электричество/день: <code>${result.electricity_cost_usd_daily:.2f}</code>
        - Комиссия пула ({result.pool_commission}%)/день: <code>${result.pool_fee_usd_daily:.2f}</code>
        - <b>Всего расходов/день:</b> <code>${result.total_expenses_usd_daily:.2f}</code>

        ---

        ✅ <b>Чистая прибыль:</b>
        - <b>В день:</b> <code>${result.net_profit_usd_daily:.2f}</code> / <code>{result.net_profit_rub_daily:.2f} ₽</code>
        - <b>В месяц:</b> <code>${result.net_profit_usd_monthly:.2f}</code> / <code>{result.net_profit_rub_monthly:.2f} ₽</code>
        - <b>В год:</b> <code>${result.net_profit_usd_yearly:.2f}</code> / <code>{result.net_profit_rub_yearly:.2f} ₽</code>
    """)
    if result.net_profit_usd_daily < 0:
        text += "\n\n⚠️ <b>Внимание:</b> при текущих параметрах майнинг невыгоден."
    return text.strip()

# --- ФОРМАТТЕРЫ ДЛЯ КРИПТО-ЦЕНТРА ---

AI_DISCLAIMER = "\n\n<i>⚠️ Информация сгенерирована ИИ на основе свежих данных и может содержать неточности. Всегда проводите собственное исследование (DYOR).</i>"

def format_airdrops_list(airdrops: List[AirdropProject]) -> str:
    """Форматирует список Airdrop-проектов."""
    text = "<b>💧 Охота за Airdrop'ами (AI-Анализ)</b>\n\nВыберите проект, чтобы увидеть чеклист:"
    return text + AI_DISCLAIMER

def format_airdrop_details(project: AirdropProject) -> str:
    """Форматирует детальную информацию о проекте Airdrop."""
    text = (
        f"<b>Проект: {project.name}</b> ({project.status})\n\n"
        f"{project.description}\n\n"
        f"<b>Чеклист для получения Airdrop:</b>"
    )
    return text + AI_DISCLAIMER

# --- ИСПРАВЛЕННАЯ ФУНКЦИЯ ---
def format_mining_signals(signals: List[MiningSignal]) -> str:
    """Форматирует список майнинг-сигналов."""
    if not signals:
        text = "<b>⛏️ Сигналы для майнеров (AI)</b>\n\n😕 AI не смог найти актуальных сигналов в свежих данных. Попробуйте позже."
    else:
        text = "<b>⛏️ Сигналы для майнеров (AI)</b>\n"
        for signal in signals:
            text += (
                f"\n➖➖➖➖➖➖➖➖➖➖\n"
                f"<b>{signal.name}</b> (Статус: {signal.status})\n"
                f"<i>{signal.description}</i>\n"
                f"<b>Алгоритм:</b> <code>{signal.algorithm}</code>\n"
                f"<b>Оборудование:</b> {signal.hardware}\n"
                f"<a href='{signal.guide_url or '#'}'>Подробный гайд</a>"
            )
    return text + AI_DISCLAIMER
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---

def format_live_feed(feed: List[NewsArticle]) -> str:
    """Форматирует новостную ленту с AI-выжимкой."""
    if not feed:
        return "😕 Не удалось загрузить и проанализировать ленту новостей. Попробуйте позже."
    
    text = "<b>⚡️ Лента Крипто-Новостей (AI-Анализ)</b>\n"
    for item in feed:
        summary = item.ai_summary or 'Не удалось проанализировать.'
        text += (
            f"\n➖➖➖➖➖➖➖➖➖➖\n"
            f"▪️ <b>Кратко:</b> <i>{summary}</i>\n"
            f"▪️ <a href='{item.url}'>{item.title}</a>"
        )
    return text
