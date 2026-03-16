from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Optional
from config import DISTRICTS

def get_role_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура выбора роли при регистрации
    """
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="🔧 Заказчик",
        callback_data="role_customer"
    ))
    builder.add(InlineKeyboardButton(
        text="🛠 Монтажник",
        callback_data="role_installer"
    ))
    
    builder.adjust(2)
    
    return builder.as_markup()

def get_district_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура выбора района
    """
    builder = InlineKeyboardBuilder()
    
    for district in DISTRICTS:
        builder.add(InlineKeyboardButton(
            text=district,
            callback_data=f"district_{district}"
        ))
    
    builder.adjust(2)
    
    return builder.as_markup()

def get_request_action_keyboard(request_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура для заявки в группе
    """
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="✅ Взять",
        callback_data=f"take_{request_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Отказаться",
        callback_data=f"refuse_{request_id}"
    ))
    
    builder.adjust(2)
    
    return builder.as_markup()

def get_installer_request_keyboard(request_id: int, has_coords: bool = False) -> InlineKeyboardMarkup:
    """
    Клавиатура для работы с заявкой в ЛС монтажника
    """
    builder = InlineKeyboardBuilder()
    
    if has_coords:
        builder.add(InlineKeyboardButton(
            text="🗺 Открыть на карте",
            url=f"https://yandex.ru/maps/?pt={request_id}"  # Здесь будет реальная логика
        ))
    
    builder.add(InlineKeyboardButton(
        text="✅ Завершить",
        callback_data=f"complete_{request_id}"
    ))
    
    if has_coords:
        builder.adjust(1, 1)
    else:
        builder.adjust(1)
    
    return builder.as_markup()

def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура админ-панели
    """
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="📊 Общая статистика",
        callback_data="admin_stats_general"
    ))
    builder.add(InlineKeyboardButton(
        text="📍 По районам",
        callback_data="admin_stats_districts"
    ))
    builder.add(InlineKeyboardButton(
        text="👥 По монтажникам",
        callback_data="admin_stats_installers"
    ))
    builder.add(InlineKeyboardButton(
        text="📅 За период",
        callback_data="admin_stats_period"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Отказы",
        callback_data="admin_stats_refusals"
    ))
    
    builder.adjust(1)
    
    return builder.as_markup()

def get_back_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура с кнопкой назад
    """
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="admin_back"
    ))
    
    return builder.as_markup()

def get_confirmation_keyboard(request_id: int, action: str) -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения действия
    """
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="✅ Подтвердить",
        callback_data=f"confirm_{action}_{request_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Отмена",
        callback_data=f"cancel_{action}_{request_id}"
    ))
    
    builder.adjust(2)
    
    return builder.as_markup()