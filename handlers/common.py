from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
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
            return

        # Новый пользователь: предлагаем выбор роли
        await message.answer(
            "Добро пожаловать! Выберите вашу роль:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Заказчик", callback_data="role_customer")],
                [InlineKeyboardButton(text="Монтажник", callback_data="role_installer")]
            ])
        )

@router.callback_query(F.data.startswith("role_"))
async def set_role(callback: CallbackQuery, state: FSMContext):
    role = callback.data.split("_")[1]
    telegram_id = callback.from_user.id
    name = callback.from_user.full_name
    username = callback.from_user.username
    is_admin = (telegram_id == ADMIN_ID)

    async for session in get_db():
        user = User(
            telegram_id=telegram_id,
            role=role,
            name=name,
            username=username,
            is_admin=is_admin
        )
        session.add(user)
        await session.commit()

    await callback.message.edit_text(f"Вы зарегистрированы как {'заказчик' if role == 'customer' else 'монтажник'}.")
    if role == "customer":
        await callback.message.answer("Используйте меню для создания заявки.", reply_markup=customer_menu())
    else:
        await callback.message.answer("Используйте меню для просмотра заявок.", reply_markup=installer_menu())
    await callback.answer()