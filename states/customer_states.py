from aiogram.fsm.state import State, StatesGroup

class RequestStates(StatesGroup):
    """
    Состояния FSM для процесса создания заявки
    """
    waiting_description = State()
    waiting_photos = State()
    waiting_address = State()
    waiting_address_manual = State()
    waiting_phone = State()
    waiting_district = State()

class RefusalStates(StatesGroup):
    """
    Состояния FSM для процесса отказа от заявки
    """
    waiting_reason = State()
