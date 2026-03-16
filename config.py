import os
from typing import Final, List
from dotenv import load_dotenv
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения из .env файла
load_dotenv()
logger.info("Загрузка .env файла...")

# Проверка наличия обязательных переменных
BOT_TOKEN: Final[str] = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")

try:
    ADMIN_ID: Final[int] = int(os.getenv('ADMIN_ID', 0))
except ValueError:
    raise ValueError("ADMIN_ID должен быть числом")

try:
    GROUP_ID: Final[int] = int(os.getenv('GROUP_ID', 0))
except ValueError:
    raise ValueError("GROUP_ID должен быть числом")

GEOCODER_API_KEY: Final[str] = os.getenv('GEOCODER_API_KEY', '')

DATABASE_URL: Final[str] = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///montage_bot.db')

# СПИСОК РАЙОНОВ - исправленный под ваши требования
DISTRICTS: Final[List[str]] = [
    "Центр",
    "Шишковка", 
    "Восточный",
    "Верхняя Березовка",
    "100-е квартала",
    "Восточные ворота",
    "Комушка",
    "Вахмистрово",
    "Зверосовхоз",
    "Южлаг",
    "Другой"
]

# Константы для статусов заявок
REQUEST_STATUS_NEW: Final[str] = "new"
REQUEST_STATUS_IN_PROGRESS: Final[str] = "in_progress"
REQUEST_STATUS_COMPLETED: Final[str] = "completed"
REQUEST_STATUS_CANCELLED: Final[str] = "cancelled"

# Роли пользователей
ROLE_CUSTOMER: Final[str] = "customer"
ROLE_INSTALLER: Final[str] = "installer"

# Логирование
LOG_FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL: Final[str] = "INFO"
