from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from sqlalchemy import select

from database import get_db
from models import User, UserRole
from keyboards.reply import (
    get_customer_main_keyboard, 
    get_installer_main_keyboard,
    get_admin_main_keyboard
)
from keyboards.inline import get_role_keyboard
from config import ADMIN_ID
from utils.db_helper import with_session

import logging

logger = logging.getLogger(__name__)

router = Router()

@router.message(CommandStart())
@with_session
async def cmd_start(message: Message, session):
    """
    Обработчик команды /start
    """
    try:
        # Проверяем, существует ли пользователь
        query = select(User).where(User.telegram_id == message.from_user.id)
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        
        if user:
            # Пользователь уже зарегистрирован
            await send_role_menu(message, user)
        else:
            # Новый пользователь - предлагаем выбрать роль
            await message.answer(
                "👋 Добро пожаловать! Выберите вашу роль:",
                reply_markup=get_role_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Ошибка в cmd_start: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.callback_query(F.data.startswith("role_"))
@with_session
async def process_role_selection(callback: CallbackQuery, session):
    """
    Обработка выбора роли
    """
    try:
        role = callback.data.replace("role_", "")
        
        # Определяем роль
        if role == "customer":
            user_role = UserRole.CUSTOMER
        elif role == "installer":
            user_role = UserRole.INSTALLER
        else:
            await callback.answer("Неверная роль")
            return
        
        # Создаем нового пользователя
        is_admin = callback.from_user.id == ADMIN_ID
        
        new_user = User(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
            role=user_role,
            is_admin=is_admin
        )
        
        session.add(new_user)
        await session.commit()
        
        await callback.answer("✅ Регистрация успешна!")
        
        # Отправляем соответствующее меню
        await send_role_menu(callback.message, new_user)
        
        # Удаляем сообщение с выбором роли
        await callback.message.delete()
        
    except Exception as e:
        logger.error(f"Ошибка в process_role_selection: {e}")
        await callback.answer("❌ Ошибка при регистрации")
        await session.rollback()

@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: Message):
    """
    Обработчик команды /help
    """
    help_text = """
<b>🔧 Помощь по боту</b>

<b>Для заказчиков:</b>
• 📝 Новая заявка - создать заявку на монтаж
• 📋 Мои заявки - посмотреть статус ваших заявок
• /request [номер] - детали конкретной заявки

<b>Для монтажников:</b>
• 📋 Мои заявки - список взятых заявок
• 📊 Моя статистика - личная статистика
• В группе можно брать или отказываться от заявок

<b>Общее:</b>
• /start - перезапустить бота
• /help - показать это сообщение

По вопросам: @admin
    """
    
    await message.answer(help_text, parse_mode="HTML")

async def send_role_menu(message: Message, user: User):
    """
    Отправка меню в зависимости от роли
    """
    welcome_text = f"👋 С возвращением, {user.first_name or 'пользователь'}!"
    
    if user.is_admin:
        await message.answer(
            welcome_text + "\n\nВы вошли как администратор.",
            reply_markup=get_admin_main_keyboard()
        )
    elif user.role == UserRole.CUSTOMER:
        await message.answer(
            welcome_text + "\n\nВы вошли как заказчик.",
            reply_markup=get_customer_main_keyboard()
        )
    elif user.role == UserRole.INSTALLER:
        await message.answer(
            welcome_text + "\n\nВы вошли как монтажник.",
            reply_markup=get_installer_main_keyboard()
        )
