from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def customer_menu():
    """Меню для заказчика"""
    kb = [
        [KeyboardButton(text="📝 Новая заявка")],
        [KeyboardButton(text="📋 Мои заявки")],
        [KeyboardButton(text="ℹ️ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def installer_menu():
    """Меню для монтажника"""
    kb = [
        [KeyboardButton(text="📋 Мои активные заявки")],
        [KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="ℹ️ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def cancel_keyboard():
    """Клавиатура отмены"""
    kb = [[KeyboardButton(text="❌ Отмена")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def geo_keyboard():
    """Клавиатура для выбора способа ввода адреса"""
    kb = [
        [KeyboardButton(text="📍 Отправить геолокацию", request_location=True)],
        [KeyboardButton(text="✍️ Ввести адрес вручную")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def districts_keyboard(districts):
    """Инлайн клавиатура с районами"""
    builder = InlineKeyboardBuilder()
    for district in districts:
        builder.button(text=district.name, callback_data=f"district_{district.id}")
    builder.adjust(2)
    return builder.as_markup()

def group_request_keyboard(request_id):
    """Клавиатура для заявки в группе"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Взять", callback_data=f"take_{request_id}")
    builder.button(text="❌ Отказаться", callback_data=f"refuse_{request_id}")
    return builder.as_markup()

def installer_request_actions(request_id, has_coords=False):
    """Клавиатура действий для монтажника в ЛС"""
    builder = InlineKeyboardBuilder()
    if has_coords:
        builder.button(text="🗺 Открыть на карте", callback_data=f"map_{request_id}")
    builder.button(text="📞 Позвонить", callback_data=f"call_{request_id}")
    builder.button(text="✅ Завершить", callback_data=f"complete_{request_id}")
    builder.adjust(1)
    return builder.as_markup()

def admin_panel():
    """Панель администратора"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Общая статистика", callback_data="admin_general")
    builder.button(text="📍 По районам", callback_data="admin_districts")
    builder.button(text="👥 По монтажникам", callback_data="admin_installers")
    builder.button(text="📅 За период", callback_data="admin_period")
    builder.adjust(2)
    return builder.as_markup()
