import os
from typing import Final, List
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

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

# Список районов города
DISTRICTS: Final[List[str]] = [
    "Центральный",
    "Северный",
    "Северо-Западный",
    "Северо-Восточный",
    "Южный",
    "Юго-Западный",
    "Юго-Восточный",
    "Западный",
    "Восточный",
    "Пригородный"
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