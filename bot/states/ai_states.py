# bot/states/ai_states.py
from aiogram.fsm.state import State, StatesGroup

class AIConsultantState(StatesGroup):
    waiting_question = State()