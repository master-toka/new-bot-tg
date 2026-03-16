import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, LOG_FORMAT, LOG_LEVEL, ADMIN_ID, GROUP_ID
from database import init_db, get_db, close_db
from handlers import common, customer, installer, admin, group
from utils.init_districts import init_districts  # Добавлен импорт

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT
)
logger = logging.getLogger(__name__)

# Проверка конфигурации при запуске
def check_config():
    """
    Проверка наличия необходимых конфигурационных параметров
    """
    errors = []
    
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN не настроен")
    if not ADMIN_ID:
        errors.append("ADMIN_ID не настроен")
    if not GROUP_ID:
        errors.append("GROUP_ID не настроен")
    
    if errors:
        error_text = "\n".join(errors)
        logger.error(f"Ошибки конфигурации:\n{error_text}")
        return False
    
    logger.info("Конфигурация проверена успешно")
    logger.info(f"ADMIN_ID: {ADMIN_ID}")
    logger.info(f"GROUP_ID: {GROUP_ID}")
    return True

async def on_startup(bot: Bot):
    """
    Действия при запуске бота
    """
    logger.info("Бот запускается...")
    
    # Инициализация базы данных
    try:
        await init_db()
        logger.info("База данных инициализирована")
        
        # Инициализация районов
        async for session in get_db():
            try:
                await init_districts(session)
                logger.info("Районы инициализированы")
            except Exception as e:
                logger.error(f"Ошибка при инициализации районов: {e}")
            break
            
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")
        raise
    
    # Проверяем, является ли бот администратором группы
    try:
        chat_member = await bot.get_chat_member(GROUP_ID, bot.id)
        if chat_member.status not in ['administrator', 'creator']:
            logger.warning(f"Бот не является администратором группы {GROUP_ID}")
            logger.warning("Некоторые функции могут работать некорректно")
    except Exception as e:
        logger.error(f"Не удалось проверить права бота в группе: {e}")
    
    # Отправляем уведомление админу о запуске
    try:
        await bot.send_message(
            ADMIN_ID,
            "✅ Бот успешно запущен!\n"
            f"Группа монтажников: {GROUP_ID}"
        )
        logger.info("Уведомление о запуске отправлено админу")
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление админу: {e}")
    
    logger.info("Бот готов к работе")

async def on_shutdown(bot: Bot):
    """
    Действия при остановке бота
    """
    logger.info("Бот останавливается...")
    
    # Отправляем уведомление админу о остановке
    try:
        await bot.send_message(
            ADMIN_ID,
            "🛑 Бот остановлен"
        )
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление о остановке: {e}")
    
    # Закрываем соединения с БД
    try:
        await close_db()
        logger.info("Соединения с БД закрыты")
    except Exception as e:
        logger.error(f"Ошибка при закрытии соединений с БД: {e}")
    
    # Закрываем все сессии
    await bot.session.close()
    logger.info("Бот остановлен")

async def main():
    """
    Главная функция запуска бота
    """
    # Проверяем конфигурацию
    if not check_config():
        logger.error("Ошибка конфигурации. Бот не может быть запущен.")
        return
    
    # Инициализируем бота и диспетчер
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрируем роутеры
    dp.include_router(common.router)
    dp.include_router(customer.router)
    dp.include_router(installer.router)
    dp.include_router(admin.router)
    dp.include_router(group.router)
    
    # Регистрируем функции запуска и остановки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Запускаем бота
    try:
        logger.info("Запуск polling...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Критическая ошибка при работе бота: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Необработанная ошибка: {e}")
