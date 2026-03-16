from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import ChatMemberUpdatedFilter, IS_NOT_MEMBER, IS_MEMBER
from aiogram.enums import ChatMemberStatus
import logging

from config import GROUP_ID

logger = logging.getLogger(__name__)

router = Router()

# Фильтр для сообщений только из группы монтажников
router.message.filter(F.chat.id == GROUP_ID)


@router.message()
async def handle_group_message(message: Message):
    """
    Обработка всех сообщений в группе
    """
    # Игнорируем служебные сообщения
    if message.new_chat_members:
        await handle_new_member(message)
    elif message.left_chat_member:
        await handle_left_member(message)
    else:
        # Можно добавить логирование или модерацию
        logger.info(f"Сообщение в группе от {message.from_user.id}: {message.text}")


async def handle_new_member(message: Message):
    """
    Обработка нового участника в группе
    """
    for new_member in message.new_chat_members:
        if new_member.id == message.bot.id:
            # Бот добавлен в группу
            await message.answer(
                "👋 Привет! Я бот для управления заявками.\n"
                "Теперь новые заявки будут появляться здесь."
            )
        else:
            # Новый монтажник
            await message.answer(
                f"👋 Добро пожаловать, {new_member.first_name}!\n"
                f"Теперь вы можете брать заявки из этого чата."
            )

async def handle_left_member(message: Message):
    """
    Обработка выхода участника из группы
    """
    if message.left_chat_member.id == message.bot.id:
        logger.warning("Бот удален из группы монтажников")
    else:
        logger.info(f"Монтажник {message.left_chat_member.id} покинул группу")
