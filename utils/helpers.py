import json
import logging
from typing import List, Optional, Any, Dict
from aiogram.types import Message
import re

logger = logging.getLogger(__name__)

def extract_phone_number(text: str) -> Optional[str]:
    """
    Извлечение номера телефона из текста
    """
    # Паттерн для российских номеров
    phone_pattern = r'(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}'
    
    match = re.search(phone_pattern, text)
    if match:
        # Очищаем номер от лишних символов
        phone = re.sub(r'[\s\-\(\)]', '', match.group())
        # Приводим к формату +7
        if phone.startswith('8'):
            phone = '+7' + phone[1:]
        elif not phone.startswith('+'):
            phone = '+7' + phone
        return phone
    
    return None

def validate_phone(phone: str) -> bool:
    """
    Проверка корректности номера телефона
    """
    # Убираем все кроме цифр и +
    cleaned = re.sub(r'[^\d\+]', '', phone)
    
    # Проверяем формат
    if cleaned.startswith('+7'):
        return len(cleaned) == 12 and cleaned[1:].isdigit()
    elif cleaned.startswith('8'):
        return len(cleaned) == 11 and cleaned.isdigit()
    else:
        return False

def format_phone(phone: str) -> str:
    """
    Форматирование номера телефона для отображения
    """
    cleaned = re.sub(r'[^\d]', '', phone)
    if len(cleaned) == 11:
        return f"+7 ({cleaned[1:4]}) {cleaned[4:7]}-{cleaned[7:9]}-{cleaned[9:11]}"
    return phone

def parse_coordinates(text: str) -> Optional[tuple]:
    """
    Парсинг координат из текста
    """
    # Паттерн для координат (широта, долгота)
    coord_pattern = r'(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)'
    
    match = re.search(coord_pattern, text)
    if match:
        try:
            lat = float(match.group(1))
            lon = float(match.group(2))
            
            # Проверяем валидность координат
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return (lat, lon)
        except ValueError:
            pass
    
    return None

def split_message(text: str, max_length: int = 4096) -> List[str]:
    """
    Разделение длинного сообщения на части
    """
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current_part = ""
    
    for line in text.split('\n'):
        if len(current_part) + len(line) + 1 <= max_length:
            current_part += line + '\n'
        else:
            if current_part:
                parts.append(current_part.strip())
            current_part = line + '\n'
    
    if current_part:
        parts.append(current_part.strip())
    
    return parts

def extract_message_id(callback_data: str, prefix: str) -> Optional[int]:
    """
    Извлечение ID из callback_data
    """
    try:
        if callback_data.startswith(prefix):
            return int(callback_data.replace(prefix, ''))
    except (ValueError, AttributeError):
        pass
    return None

def json_serialize_photos(photos: List[str]) -> str:
    """
    Сериализация списка фото в JSON
    """
    try:
        return json.dumps(photos, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Ошибка сериализации фото: {e}")
        return "[]"

def json_deserialize_photos(photos_json: str) -> List[str]:
    """
    Десериализация JSON с фото
    """
    try:
        if photos_json:
            return json.loads(photos_json)
    except Exception as e:
        logger.error(f"Ошибка десериализации фото: {e}")
    return []

async def try_delete_message(message: Message):
    """
    Безопасное удаление сообщения
    """
    try:
        await message.delete()
    except Exception as e:
        logger.debug(f"Не удалось удалить сообщение: {e}")

def escape_markdown(text: str) -> str:
    """
    Экранирование специальных символов для Markdown
    """
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text