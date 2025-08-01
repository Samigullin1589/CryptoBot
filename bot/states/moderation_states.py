# ===============================================================
# Файл: bot/states/moderation_states.py (НОВЫЙ ФАЙЛ)
# Описание: Состояния (FSM) для интерактивных команд модерации.
# Позволяет создавать сложные сценарии, например, с подтверждением
# действий или вводом дополнительных данных.
# ===============================================================
from aiogram.fsm.state import State, StatesGroup

class ModerationStates(StatesGroup):
    """
    Состояния для процессов модерации.
    """
    # Пример состояния для будущего расширения
    confirm_ban_reason = State()
    
    # Сюда можно будет добавлять другие состояния:
    # - confirm_broadcast
    # - manage_user_by_id
