from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ContentType
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import User, District, Request, GroupMessage
from keyboards import cancel_keyboard, geo_keyboard, districts_keyboard
from utils import reverse_geocode, format_request_for_group, logger
from config import GROUP_ID
from handlers.installer import send_request_to_group
import json

router = Router()

class RequestFSM(StatesGroup):
    description = State()
    photos = State()
    address = State()
    phone = State()
    district = State()

@router.message(Command("new_request"))
@router.message(F.text == "📝 Новая заявка")
async def new_request(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    async for session in get_db():
        user = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user.scalar_one_or_none()
        if not user or user.role != "customer":
            await message.answer("Эта команда только для заказчиков.")
            return
    await state.set_state(RequestFSM.description)
    await message.answer("Опишите работу:", reply_markup=cancel_keyboard())

@router.message(RequestFSM.description)
async def process_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(RequestFSM.photos)
    await message.answer("Отправьте фото (одно или несколько). Когда закончите, введите /done", reply_markup=cancel_keyboard())

@router.message(RequestFSM.photos, F.photo)
async def process_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer("Фото добавлено. Можете отправить ещё или /done")

@router.message(RequestFSM.photos, Command("done"))
async def photos_done(message: Message, state: FSMContext):
    await state.set_state(RequestFSM.address)
    await message.answer("Укажите адрес. Отправьте геолокацию или введите вручную:", reply_markup=geo_keyboard())

@router.message(RequestFSM.address, F.location)
async def process_location(message: Message, state: FSMContext):
    lat = message.location.latitude
    lon = message.location.longitude
    address = await reverse_geocode(lat, lon)
    if address:
        await state.update_data(address=address, latitude=lat, longitude=lon)
        await message.answer(f"Распознан адрес: {address}\nВерно?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data="addr_confirm")],
            [InlineKeyboardButton(text="Нет, ввести вручную", callback_data="addr_manual")]
        ]))
    else:
        await message.answer("Не удалось распознать адрес. Введите вручную:")
        await state.set_state(RequestFSM.address_manual)

@router.callback_query(F.data == "addr_confirm")
async def addr_confirm(callback: CallbackQuery, state: FSMContext):
    await state.set_state(RequestFSM.phone)
    await callback.message.edit_text("Введите номер телефона для связи:")
    await callback.answer()

@router.callback_query(F.data == "addr_manual")
async def addr_manual(callback: CallbackQuery, state: FSMContext):
    await state.set_state(RequestFSM.address_manual)
    await callback.message.edit_text("Введите адрес вручную:")
    await callback.answer()

@router.message(RequestFSM.address_manual)
async def process_manual_address(message: Message, state: FSMContext):
    await state.update_data(address=message.text, latitude=None, longitude=None)
    await state.set_state(RequestFSM.phone)
    await message.answer("Введите номер телефона для связи:")

@router.message(RequestFSM.phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.text
    await state.update_data(phone=phone)
    # Получаем районы из БД
    async for session in get_db():
        districts = await session.execute(select(District))
        districts = districts.scalars().all()
        if not districts:
            # Если районов нет, создадим пару для примера
            districts = [District(name="Центральный"), District(name="Северный")]
            session.add_all(districts)
            await session.commit()
            districts = await session.execute(select(District))
            districts = districts.scalars().all()
    await state.set_state(RequestFSM.district)
    await message.answer("Выберите район:", reply_markup=districts_keyboard(districts))

@router.callback_query(RequestFSM.district, F.data.startswith("district_"))
async def process_district(callback: CallbackQuery, state: FSMContext):
    district_id = int(callback.data.split("_")[1])
    data = await state.get_data()
    async for session in get_db():
        # Получаем заказчика
        user = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = user.scalar_one()
        # Создаём заявку
        photos = data.get("photos", [])
        photos_str = json.dumps(photos) if photos else None
        request = Request(
            customer_id=user.id,
            description=data["description"],
            photos=photos_str,
            address=data["address"],
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            phone=data["phone"],
            district_id=district_id,
            status="new"
        )
        session.add(request)
        await session.commit()
        await session.refresh(request)

        # Отправляем в группу
        await send_request_to_group(request.id, session)

    await callback.message.edit_text("Заявка создана и отправлена монтажникам!")
    await state.clear()
    await callback.answer()