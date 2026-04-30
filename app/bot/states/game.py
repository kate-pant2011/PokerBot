from aiogram.fsm.state import State, StatesGroup

class CreateGameState(StatesGroup):
    waiting_for_name = State()
    waiting_for_date = State()