from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import User, Request, District, Refusal
from keyboards import admin_panel
from config import ADMIN_ID

router = Router()

@router.message(Command("admin"))
async def admin_panel_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ запрещён.")
        return
    await message.answer("Панель администратора", reply_markup=admin_panel())

@router.callback_query(F.data == "admin_general")
async def admin_general(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа")
        return
    async for session in get_db():
        total_requests = await session.scalar(select(func.count(Request.id)))
        new_requests = await session.scalar(select(func.count(Request.id)).where(Request.status == "new"))
        in_progress = await session.scalar(select(func.count(Request.id)).where(Request.status == "in_progress"))
        completed = await session.scalar(select(func.count(Request.id)).where(Request.status == "completed"))
        total_customers = await session.scalar(select(func.count(User.id)).where(User.role == "customer"))
        total_installers = await session.scalar(select(func.count(User.id)).where(User.role == "installer"))
        total_refusals = await session.scalar(select(func.count(Refusal.id)))

        text = (
            f"📊 Общая статистика:\n"
            f"Всего заявок: {total_requests}\n"
            f"Новых: {new_requests}\n"
            f"В работе: {in_progress}\n"
            f"Выполнено: {completed}\n"
            f"Заказчиков: {total_customers}\n"
            f"Монтажников: {total_installers}\n"
            f"Отказов: {total_refusals}"
        )
    await callback.message.edit_text(text, reply_markup=admin_panel())
    await callback.answer()

@router.callback_query(F.data == "admin_districts")
async def admin_districts(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    async for session in get_db():
        districts = await session.execute(select(District))
        districts = districts.scalars().all()
        lines = ["📊 По районам:"]
        for d in districts:
            total = await session.scalar(select(func.count(Request.id)).where(Request.district_id == d.id))
            completed = await session.scalar(select(func.count(Request.id)).where(Request.district_id == d.id, Request.status == "completed"))
            lines.append(f"{d.name}: всего {total}, выполнено {completed}")
        text = "\n".join(lines)
    await callback.message.edit_text(text, reply_markup=admin_panel())
    await callback.answer()

@router.callback_query(F.data == "admin_installers")
async def admin_installers(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    async for session in get_db():
        installers = await session.execute(select(User).where(User.role == "installer"))
        installers = installers.scalars().all()
        lines = ["📊 По монтажникам:"]
        for inst in installers:
            completed = await session.scalar(select(func.count(Request.id)).where(Request.installer_id == inst.id, Request.status == "completed"))
            refusals = await session.scalar(select(func.count(Refusal.id)).where(Refusal.installer_id == inst.id))
            lines.append(f"{inst.name}: выполнено {completed}, отказов {refusals}")
        text = "\n".join(lines)
    await callback.message.edit_text(text, reply_markup=admin_panel())
    await callback.answer()

@router.callback_query(F.data == "admin_period")
async def admin_period(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    await callback.message.edit_text("📅 Статистика за период будет доступна позже.", reply_markup=admin_panel())
    await callback.answer()