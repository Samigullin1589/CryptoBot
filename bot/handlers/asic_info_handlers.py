import logging
from datetime import datetime, timezone
import redis.asyncio as redis
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config.settings import settings
from bot.services.admin_service import AdminService
from bot.services.asic_service import AsicService
from bot.services.user_service import UserService

router = Router()
logger = logging.getLogger(__name__)

# --- Вспомогательная функция для форматирования ---

def format_asic_passport(data: dict, electricity_cost: float = 0.0) -> str:
    """Формирует красивый текстовый паспорт для ASIC с расчетом чистой прибыли."""
    name = data.get('name', "Неизвестно")
    # Прибыльность из Redis всегда "грязная", до вычета э/э
    gross_profitability = float(data.get('profitability', 0.0))
    power = int(data.get('power', 0))

    # Рассчитываем чистую прибыль
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
        if value and value != "N/A":
            unit = " Вт" if key == "power" else ""
            specs_list.append(f"  ▫️ <b>{rus_name}:</b> {value}{unit}")

    specs_text = "\n".join(specs_list)

    # Формируем блок с доходностью
    profit_text = (
        f"  ▪️ <b>Доход (грязными):</b> ${gross_profitability:.2f}/день\n"
        f"  ▪️ <b>Доход (чистыми):</b> ${net_profit:.2f}/день\n"
        f"     (при цене э/э ${electricity_cost:.4f}/кВт·ч)"
    )

    text = (
        f"📋 <b>Паспорт устройства: {name}</b>\n\n"
        f"<b><u>Экономика:</u></b>\n{profit_text}\n\n"
        f"<b><u>Технические характеристики:</u></b>\n{specs_text}\n"
    )
    return text

# --- Хендлеры ---

@router.message(Command("top_asics"))
async def top_asics_handler(message: Message, asic_service: AsicService, admin_service: AdminService, redis_client: redis.Redis):
    """
    Выдает топ-10 самых доходных ASIC с учетом стоимости электроэнергии пользователя.
    """
    await admin_service.track_command_usage("/top_asics")
    
    # Получаем персональную стоимость э/э для пользователя
    user_service = UserService(redis_client)
    electricity_cost = await user_service.get_user_electricity_cost(message.from_user.id)
    
    msg = await message.answer("🔍 Собираю данные о самых доходных устройствах... Это может занять несколько секунд.")

    top_miners, last_update_time = await asic_service.get_top_asics(count=10, electricity_cost=electricity_cost)

    if not top_miners:
        await msg.edit_text("😕 Не удалось получить данные о майнерах. База данных пуста или источники недоступны. Попробуйте позже.")
        return

    response_lines = [f"🏆 <b>Топ-10 доходных ASIC</b> (чистыми, при цене э/э ${electricity_cost:.4f}/кВт·ч)\n"]
    
    for i, miner in enumerate(top_miners, 1):
        line = (
            f"{i}. <b>{miner.name}</b>\n"
            f"   Доход: <b>${miner.profitability:.2f}/день</b> | {miner.algorithm}"
        )
        response_lines.append(line)
    
    if last_update_time:
        now = datetime.now(timezone.utc)
        minutes_ago = int((now - last_update_time).total_seconds() / 60)
        response_lines.append(f"\n<i>Данные обновлены {minutes_ago} минут назад.</i>")
    else:
        response_lines.append("\n<i>Время последнего обновления неизвестно.</i>")

    await msg.edit_text("\n".join(response_lines), disable_web_page_preview=True)


@router.message(Command("asic"))
async def asic_passport_handler(message: Message, asic_service: AsicService, admin_service: AdminService, redis_client: redis.Redis):
    """
    Обрабатывает команду /asic [модель] и выдает паспорт устройства из кэша Redis.
    """
    await admin_service.track_command_usage("/asic")
    
    try:
        model_query = message.text.split(maxsplit=1)[1]
    except IndexError:
        await message.reply("Пожалуйста, укажите модель ASIC после команды.\n"
                            "Например: <code>/asic s19k pro</code>")
        return

    found_asic_dict = await asic_service.find_asic_by_query(model_query)
            
    if found_asic_dict:
        user_service = UserService(redis_client)
        electricity_cost = await user_service.get_user_electricity_cost(message.from_user.id)
        response_text = format_asic_passport(found_asic_dict, electricity_cost)
        await message.answer(response_text, disable_web_page_preview=True)
    else:
        await message.answer(f"😕 Модель, похожая на '<code>{model_query}</code>', не найдена в нашей базе. "
                             "База данных обновляется автоматически. Проверьте название или попробуйте позже.")


@router.message(Command("set_cost"))
async def set_electricity_cost_handler(message: Message):
    """
    Отправляет пользователю инлайн-клавиатуру для выбора тарифа на электроэнергию.
    """
    builder = InlineKeyboardBuilder()
    for tariff_name in settings.ELECTRICITY_TARIFFS.keys():
        builder.button(text=tariff_name, callback_data=f"set_tariff:{tariff_name}")
    
    builder.adjust(1) # Располагаем кнопки по одной в строке

    await message.answer(
        "Выберите ваш тариф на электроэнергию. Это повлияет на расчет чистой доходности во всех командах.",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("set_tariff:"))
async def process_tariff_selection(callback: CallbackQuery, redis_client: redis.Redis):
    """
    Обрабатывает выбор тарифа пользователем.
    """
    try:
        tariff_name = callback.data.split(":")[1]
    except IndexError:
        await callback.answer("Ошибка! Не удалось определить тариф.", show_alert=True)
        return

    tariff_info = settings.ELECTRICITY_TARIFFS.get(tariff_name)
    if not tariff_info:
        await callback.answer("Ошибка! Такой тариф не найден в настройках.", show_alert=True)
        return

    cost = tariff_info["cost_per_hour"]
    
    user_service = UserService(redis_client)
    await user_service.set_user_electricity_cost(callback.from_user.id, cost)
    
    await callback.message.edit_text(
        f"✅ Ваш тариф изменен на '<b>{tariff_name}</b>'.\n"
        f"Новая стоимость электроэнергии для расчетов: <b>${cost:.4f}/кВт·ч</b>."
    )
    await callback.answer("Настройки сохранены!")
