from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ContentType
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
import json

from database import get_db
from models import User, Request, District, GroupMessage, RequestStatus
from states.customer_states import RequestStates
from keyboards.reply import (
    get_cancel_keyboard, 
    get_location_keyboard, 
    get_done_keyboard,
    remove_keyboard
)
from keyboards.inline import get_district_keyboard
from services.geocoder import GeocoderService
from services.notifications import NotificationService
from utils.helpers import json_serialize_photos, validate_phone
from config import GROUP_ID, REQUEST_STATUS_NEW

logger = logging.getLogger(__name__)

router = Router()

@router.message(Command("new_request"))
@router.message(F.text == "📝 Новая заявка")
async def cmd_new_request(message: Message, state: FSMContext, session: AsyncSession = None):
    """
    Начало создания новой заявки
    """
    try:
        # Получаем сессию БД если не передана
        if not session:
            async for db_session in get_db():
                session = db_session
                break
        
        # Проверяем, что пользователь - заказчик
        query = select(User).where(User.telegram_id == message.from_user.id)
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        
        if not user or user.role.value != "customer":
            await message.answer("Эта функция доступна только заказчикам.")
            return
        
        # Очищаем предыдущее состояние
        await state.clear()
        
        # Начинаем новый запрос
        await state.set_state(RequestStates.waiting_description)
        await message.answer(
            "📝 Опишите подробно, какие работы нужно выполнить:",
            reply_markup=get_cancel_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка в cmd_new_request: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(RequestStates.waiting_description)
async def process_description(message: Message, state: FSMContext):
    """
    Обработка описания заявки
    """
    if message.text == "⬅️ Отмена":
        await state.clear()
        await message.answer("Создание заявки отменено.", reply_markup=remove_keyboard)
        return
    
    if not message.text or len(message.text) < 10:
        await message.answer("Описание должно содержать не менее 10 символов. Попробуйте еще раз:")
        return
    
    # Сохраняем описание
    await state.update_data(description=message.text)
    
    # Переходим к загрузке фото
    await state.set_state(RequestStates.waiting_photos)
    await message.answer(
        "📸 Отправьте фотографии (можно несколько). Когда закончите, нажмите '✅ Готово':",
        reply_markup=get_done_keyboard()
    )

@router.message(RequestStates.waiting_photos, F.content_type.in_({ContentType.PHOTO, ContentType.TEXT}))
async def process_photos(message: Message, state: FSMContext):
    """
    Обработка загрузки фото
    """
    data = await state.get_data()
    photos = data.get('photos', [])
    
    if message.text == "✅ Готово":
        if photos:
            # Переходим к вводу адреса
            await state.update_data(photos=photos)
            await state.set_state(RequestStates.waiting_address)
            await message.answer(
                "📍 Отправьте геолокацию или введите адрес вручную:",
                reply_markup=get_location_keyboard()
            )
        else:
            # Можно пропустить фото
            await state.update_data(photos=[])
            await state.set_state(RequestStates.waiting_address)
            await message.answer(
                "📍 Отправьте геолокацию или введите адрес вручную:",
                reply_markup=get_location_keyboard()
            )
    
    elif message.text == "⬅️ Отмена":
        await state.clear()
        await message.answer("Создание заявки отменено.", reply_markup=remove_keyboard)
    
    elif message.photo:
        # Сохраняем file_id фото
        photos.append(message.photo[-1].file_id)
        await state.update_data(photos=photos)
        await message.answer(f"✅ Фото добавлено. Всего: {len(photos)}. Можете добавить еще или нажать '✅ Готово'.")

@router.message(RequestStates.waiting_address, F.content_type == ContentType.LOCATION)
async def process_location(message: Message, state: FSMContext, session: AsyncSession = None):
    """
    Обработка геолокации
    """
    try:
        # Получаем сессию БД если не передана
        if not session:
            async for db_session in get_db():
                session = db_session
                break
        
        location = message.location
        lat, lon = location.latitude, location.longitude
        
        # Сохраняем координаты
        await state.update_data(latitude=lat, longitude=lon)
        
        # Пытаемся получить адрес через геокодер
        geocoder = GeocoderService(session)
        address = await geocoder.reverse_geocode(lat, lon)
        
        if address:
            # Сохраняем адрес и переходим к телефону
            await state.update_data(address=address)
            await state.set_state(RequestStates.waiting_phone)
            await message.answer(
                f"✅ Адрес определен:\n{address}\n\n📞 Введите номер телефона для связи:",
                reply_markup=get_cancel_keyboard()
            )
        else:
            # Если не удалось определить адрес, просим ввести вручную
            await state.set_state(RequestStates.waiting_address_manual)
            await message.answer(
                "❌ Не удалось определить адрес по геолокации.\n"
                "Пожалуйста, введите адрес вручную:",
                reply_markup=get_cancel_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Ошибка обработки геолокации: {e}")
        await message.answer("Произошла ошибка. Попробуйте ввести адрес вручную.")
        await state.set_state(RequestStates.waiting_address_manual)

@router.message(RequestStates.waiting_address, F.text)
async def process_manual_address(message: Message, state: FSMContext):
    """
    Обработка ручного ввода адреса
    """
    if message.text == "⬅️ Отмена":
        await state.clear()
        await message.answer("Создание заявки отменено.", reply_markup=remove_keyboard)
        return
    
    if message.text == "✏️ Ввести адрес вручную":
        await state.set_state(RequestStates.waiting_address_manual)
        await message.answer("Введите адрес вручную:", reply_markup=get_cancel_keyboard())
        return
    
    await message.answer("Пожалуйста, используйте кнопки меню или отправьте геолокацию.")

@router.message(RequestStates.waiting_address_manual)
async def process_manual_address_input(message: Message, state: FSMContext):
    """
    Обработка ручного ввода адреса
    """
    if message.text == "⬅️ Отмена":
        await state.clear()
        await message.answer("Создание заявки отменено.", reply_markup=remove_keyboard)
        return
    
    if not message.text or len(message.text) < 5:
        await message.answer("Адрес должен содержать не менее 5 символов. Попробуйте еще раз:")
        return
    
    # Сохраняем адрес
    await state.update_data(address=message.text)
    
    # Переходим к вводу телефона
    await state.set_state(RequestStates.waiting_phone)
    await message.answer(
        "📞 Введите номер телефона для связи:",
        reply_markup=get_cancel_keyboard()
    )

@router.message(RequestStates.waiting_phone)
async def process_phone(message: Message, state: FSMContext, session: AsyncSession = None):
    """
    Обработка номера телефона
    """
    if message.text == "⬅️ Отмена":
        await state.clear()
        await message.answer("Создание заявки отменено.", reply_markup=remove_keyboard)
        return
    
    phone = message.text
    
    # Проверяем корректность номера
    if not validate_phone(phone):
        await message.answer(
            "❌ Неверный формат номера. Пожалуйста, введите номер в формате +7XXXXXXXXXX или 8XXXXXXXXXX:"
        )
        return
    
    # Сохраняем телефон
    await state.update_data(phone=phone)
    
    # Переходим к выбору района
    await state.set_state(RequestStates.waiting_district)
    await message.answer(
        "🏘 Выберите район:",
        reply_markup=get_district_keyboard()
    )

@router.callback_query(StateFilter(RequestStates.waiting_district), F.data.startswith("district_"))
async def process_district(callback: CallbackQuery, state: FSMContext, session: AsyncSession = None):
    """
    Обработка выбора района и создание заявки
    """
    try:
        # Получаем сессию БД если не передана
        if not session:
            async for db_session in get_db():
                session = db_session
                break
        
        district_name = callback.data.replace("district_", "")
        
        # Получаем район из БД
        query = select(District).where(District.name == district_name)
        result = await session.execute(query)
        district = result.scalar_one_or_none()
        
        if not district:
            await callback.answer("Район не найден")
            return
        
        # Получаем все данные из состояния
        data = await state.get_data()
        
        # Получаем пользователя
        query = select(User).where(User.telegram_id == callback.from_user.id)
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Пользователь не найден")
            return
        
        # Создаем заявку
        new_request = Request(
            customer_id=user.id,
            district_id=district.id,
            description=data['description'],
            photos=json_serialize_photos(data.get('photos', [])),
            address=data['address'],
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            phone=data['phone'],
            status=RequestStatus.NEW
        )
        
        session.add(new_request)
        await session.commit()
        
        # Отправляем заявку в группу
        bot = callback.bot
        notification_service = NotificationService(bot, session)
        sent_message = await notification_service.send_request_to_group(new_request, GROUP_ID)
        
        if sent_message:
            # Сохраняем информацию о сообщении в группе
            group_message = GroupMessage(
                request_id=new_request.id,
                chat_id=GROUP_ID,
                message_id=sent_message.message_id
            )
            session.add(group_message)
            await session.commit()
        
        # Очищаем состояние
        await state.clear()
        
        # Отправляем подтверждение заказчику
        await callback.message.edit_text(
            f"✅ Заявка #{new_request.id} успешно создана!\n"
            f"Монтажники уже получили уведомление. Мы оповестим вас, когда заявка будет взята в работу.",
            reply_markup=None
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при создании заявки: {e}")
        await callback.answer("Ошибка при создании заявки")
        await session.rollback()