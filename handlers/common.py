from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from database import get_db
from models import User
from keyboards import customer_menu, installer_menu
from config import ADMIN_ID
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    telegram_id = message.from_user.id
    name = message.from_user.full_name
    username = message.from_user.username

    async for session in get_db():
        # Проверяем, существует ли пользователь
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()

        if user:
            # Если уже зарегистрирован, показываем соответствующее меню
            if user.role == "customer":
                await message.answer("Вы в главном меню заказчика.", reply_markup=customer_menu())
            elif user.role == "installer":
                await message.answer("Вы в главном меню монтажника.", reply_markup=installer_menu())
            else:
                await message.answer("Добро пожаловать! Ваша роль не определена.")
            return

        # Новый пользователь: предлагаем выбор роли
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👤 Заказчик", callback_data="role_customer")],
                [InlineKeyboardButton(text="🔧 Монтажник", callback_data="role_installer")]
            ]
        )
        
        await message.answer(
            "👋 Добро пожаловать!\n\n"
            "Выберите вашу роль:",
            reply_markup=keyboard
        )

@router.callback_query(F.data.startswith("role_"))
async def set_role(callback: CallbackQuery, state: FSMContext):
    role = callback.data.split("_")[1]
    telegram_id = callback.from_user.id
    name = callback.from_user.full_name
    username = callback.from_user.username
    is_admin = (telegram_id == ADMIN_ID)

    async for session in get_db():
        # Проверяем, не зарегистрирован ли уже пользователь
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            await callback.message.edit_text("Вы уже зарегистрированы.")
            await callback.answer()
            return

        user = User(
            telegram_id=telegram_id,
            role=role,
            name=name,
            username=username,
            is_admin=is_admin
        )
        session.add(user)
        await session.commit()

    # Удаляем сообщение с выбором роли
    await callback.message.delete()
    
    # Отправляем приветственное сообщение с соответствующим меню
    if role == "customer":
        await callback.message.answer(
            "✅ Вы успешно зарегистрированы как заказчик!\n\n"
            "Теперь вы можете создавать заявки на монтажные работы.",
            reply_markup=customer_menu()
        )
    else:
        await callback.message.answer(
            "✅ Вы успешно зарегистрированы как монтажник!\n\n"
            "Теперь вы можете просматривать и брать заявки.",
            reply_markup=installer_menu()
        )
    
    await callback.answer()
