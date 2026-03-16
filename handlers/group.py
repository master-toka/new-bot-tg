from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
import logging

from config import GROUP_ID

logger = logging.getLogger(__name__)

# Создаем роутер для группы
router = Router()

# ВАЖНО: Фильтруем ТОЛЬКО сообщения, НЕ callback'и!
# Для сообщений ограничиваем чатом группы
router.message.filter(F.chat.id == GROUP_ID)

# Для callback'ов НЕ применяем фильтр, чтобы они доходили до других хендлеров

@router.message()
async def handle_group_message(message: Message):
    """
    Обработка всех сообщений в группе монтажников
    """
    logger.info(f"📨 Сообщение в группе от {message.from_user.id}: {message.text}")
    
    # Игнорируем служебные сообщения
    if message.new_chat_members:
        await handle_new_member(message)
    elif message.left_chat_member:
        await handle_left_member(message)
    else:
        # Обычное сообщение в группе - просто логируем
        logger.debug(f"Обычное сообщение в группе: {message.text}")

async def handle_new_member(message: Message):
    """
    Обработка нового участника в группе
    """
    for new_member in message.new_chat_members:
        if new_member.id == message.bot.id:
            # Бот добавлен в группу
            await message.answer(
                "👋 <b>Привет! Я бот для управления заявками.</b>\n\n"
                "Теперь новые заявки будут появляться здесь с кнопками для взятия.\n"
                "Чтобы бот работал корректно, назначьте его администратором группы."
            )
            logger.info("✅ Бот добавлен в группу монтажников")
        else:
            # Новый монтажник
            await message.answer(
                f"👋 <b>Добро пожаловать, {new_member.first_name}!</b>\n\n"
                f"Теперь вы можете брать заявки, нажимая кнопки под ними.\n"
                f"После взятия заявки детали придут вам в личные сообщения."
            )
            logger.info(f"👤 Новый монтажник в группе: {new_member.first_name} (ID: {new_member.id})")

async def handle_left_member(message: Message):
    """
    Обработка выхода участника из группы
    """
    if message.left_chat_member.id == message.bot.id:
        logger.warning("⚠️ Бот удален из группы монтажников")
    else:
        logger.info(f"👋 Монтажник {message.left_chat_member.first_name} покинул группу")

@router.callback_query()
async def route_group_callbacks(callback: CallbackQuery):
    """
    Маршрутизация callback'ов из группы - ТОЛЬКО ДЛЯ ЛОГИРОВАНИЯ
    """
    logger.info(f"🔄 Callback в группе: {callback.data} от {callback.from_user.id}")
    logger.info(f"   Чат: {callback.message.chat.id} ({callback.message.chat.type})")
    
    # Проверяем, что это действительно группа монтажников
    if callback.message.chat.id != GROUP_ID:
        logger.warning(f"⚠️ Callback из другого чата: {callback.message.chat.id}")
        return
    
    # Проверяем тип callback_data
    if callback.data.startswith('take_'):
        logger.info(f"✅ Обнаружен callback взятия заявки: {callback.data}")
    elif callback.data.startswith('refuse_'):
        logger.info(f"✅ Обнаружен callback отказа от заявки: {callback.data}")
    else:
        logger.info(f"❓ Неизвестный тип callback: {callback.data}")
    
    # ВАЖНО: Не отвечаем на callback здесь!
    # Просто логируем и пропускаем дальше, чтобы обработали другие хендлеры
    # Не вызываем callback.answer() - это позволит другим хендлерам ответить
