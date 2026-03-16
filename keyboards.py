from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Reply-клавиатуры
def customer_menu():
    kb = [
        [KeyboardButton(text="📝 Новая заявка")],
        [KeyboardButton(text="Мои заявки")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def installer_menu():
    kb = [
        [KeyboardButton(text="📋 Мои активные заявки")],
        [KeyboardButton(text="📊 Статистика")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def cancel_keyboard():
    kb = [[KeyboardButton(text="❌ Отмена")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def geo_keyboard():
    kb = [
        [KeyboardButton(text="📍 Отправить геолокацию", request_location=True)],
        [KeyboardButton(text="✍️ Ввести адрес вручную")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# Inline-клавиатуры
def districts_keyboard(districts):
    builder = InlineKeyboardBuilder()
    for d in districts:
        builder.button(text=d.name, callback_data=f"district_{d.id}")
    builder.adjust(2)
    return builder.as_markup()

def group_request_keyboard(request_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Взять", callback_data=f"take_{request_id}")
    builder.button(text="❌ Отказаться", callback_data=f"refuse_{request_id}")
    return builder.as_markup()

def installer_request_actions(request_id, has_coords=False):
    builder = InlineKeyboardBuilder()
    if has_coords:
        builder.button(text="🗺 Открыть на карте", callback_data=f"map_{request_id}")
    builder.button(text="📞 Позвонить", callback_data=f"call_{request_id}")
    builder.button(text="✅ Завершить", callback_data=f"complete_{request_id}")
    builder.adjust(1)
    return builder.as_markup()

def admin_panel():
    builder = InlineKeyboardBuilder()
    builder.button(text="Общая статистика", callback_data="admin_general")
    builder.button(text="По районам", callback_data="admin_districts")
    builder.button(text="По монтажникам", callback_data="admin_installers")
    builder.button(text="За период (заглушка)", callback_data="admin_period")
    builder.adjust(2)
    return builder.as_markup()