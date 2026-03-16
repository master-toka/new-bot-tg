from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from typing import List

def get_customer_main_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура главного меню для заказчика
    """
    builder = ReplyKeyboardBuilder()
    
    builder.add(KeyboardButton(text="📝 Новая заявка"))
    builder.add(KeyboardButton(text="📋 Мои заявки"))
    builder.add(KeyboardButton(text="ℹ️ Помощь"))
    
    builder.adjust(2, 1)
    
    return builder.as_markup(resize_keyboard=True)

def get_installer_main_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура главного меню для монтажника
    """
    builder = ReplyKeyboardBuilder()
    
    builder.add(KeyboardButton(text="📋 Мои заявки"))
    builder.add(KeyboardButton(text="ℹ️ Помощь"))
    
    builder.adjust(2)
    
    return builder.as_markup(resize_keyboard=True)

def get_admin_main_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура главного меню для администратора
    """
    builder = ReplyKeyboardBuilder()
    
    builder.add(KeyboardButton(text="📋 Мои заявки"))
    builder.add(KeyboardButton(text="👑 Админ панель"))
    builder.add(KeyboardButton(text="ℹ️ Помощь"))
    
    builder.adjust(2, 1)
    
    return builder.as_markup(resize_keyboard=True)

def get_contact_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура для запроса номера телефона
    """
    builder = ReplyKeyboardBuilder()
    
    builder.add(KeyboardButton(text="📱 Отправить номер", request_contact=True))
    builder.add(KeyboardButton(text="⬅️ Отмена"))
    
    builder.adjust(1)
    
    return builder.as_markup(resize_keyboard=True)

def get_location_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура для отправки геолокации
    """
    builder = ReplyKeyboardBuilder()
    
    builder.add(KeyboardButton(text="📍 Отправить геолокацию", request_location=True))
    builder.add(KeyboardButton(text="✏️ Ввести адрес вручную"))
    builder.add(KeyboardButton(text="⬅️ Отмена"))
    
    builder.adjust(1)
    
    return builder.as_markup(resize_keyboard=True)

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура с кнопкой отмены
    """
    builder = ReplyKeyboardBuilder()
    
    builder.add(KeyboardButton(text="⬅️ Отмена"))
    
    return builder.as_markup(resize_keyboard=True)

def get_done_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура с кнопкой готово для завершения загрузки фото
    """
    builder = ReplyKeyboardBuilder()
    
    builder.add(KeyboardButton(text="✅ Готово"))
    builder.add(KeyboardButton(text="⬅️ Отмена"))
    
    builder.adjust(2)
    
    return builder.as_markup(resize_keyboard=True)

# Клавиатура для удаления reply-кнопок
remove_keyboard = ReplyKeyboardRemove()