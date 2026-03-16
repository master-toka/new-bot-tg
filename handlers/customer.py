from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ContentType
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
import json
import re

from database import get_db
from models import User, Request, District, GroupMessage, RequestStatus
from states.customer_states import RequestStates
from keyboards.reply import (
    get_customer_main_keyboard,
    get_cancel_keyboard, 
    get_location_keyboard, 
    get_done_keyboard,
    remove_keyboard
)
from keyboards.inline import get_district_keyboard
from services.geocoder import GeocoderService
from services.notifications import NotificationService
from utils.helpers import json_serialize_photos, validate_phone
from config import GROUP_ID, DISTRICTS

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
        
        if not user:
            await message.answer("❌ Вы не зарегистрированы. Используйте /start для регистрации.")
            return
        
        if user.role.value != "customer":
            await message.answer("❌ Эта функция доступна только заказчикам.")
            return
        
        # Очищаем предыдущее состояние
        await state.clear()
        
        # Начинаем новый запрос
        await state.set_state(RequestStates.waiting_description)
        await message.answer(
            "📝 Опишите подробно, какие работы нужно выполнить:\n"
            "(минимум 10 символов)",
            reply_markup=get_cancel_keyboard()
        )
        
        logger.info(f"Пользователь {message.from_user.id} начал создание заявки")
        
    except Exception as e:
        logger.error(f"Ошибка в cmd_new_request: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")

@router.message(RequestStates.waiting_description)
async def process_description(message: Message, state: FSMContext):
    """
    Обработка описания заявки
    """
    if message.text == "⬅️ Отмена":
        await state.clear()
        await message.answer("❌ Создание заявки отменено.", reply_markup=get_customer_main_keyboard())
        return
    
    if not message.text or len(message.text.strip()) < 10:
        await message.answer("❌ Описание должно содержать не менее 10 символов. Попробуйте еще раз:")
        return
    
    # Сохраняем описание
    await state.update_data(description=message.text.strip())
    
    # Переходим к загрузке фото
    await state.set_state(RequestStates.waiting_photos)
    await message.answer(
        "📸 Отправьте фотографии (можно несколько). Когда закончите, нажмите '✅ Готово':\n"
        "(можно пропустить, нажав '✅ Готово' сразу)",
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
        # Сохраняем фото (может быть пустым списком)
        await state.update_data(photos=photos)
        
        # Переходим к вводу адреса
        await state.set_state(RequestStates.waiting_address)
        await message.answer(
            "📍 Отправьте геолокацию или введите адрес вручную:",
            reply_markup=get_location_keyboard()
        )
        logger.info(f"Загружено фото: {len(photos)} шт.")
    
    elif message.text == "⬅️ Отмена":
        await state.clear()
        await message.answer("❌ Создание заявки отменено.", reply_markup=get_customer_main_keyboard())
    
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
                f"✅ Адрес определен:\n{address}\n\n"
                f"📞 Введите номер телефона для связи\n"
                f"(например: +7XXXXXXXXXX или 8XXXXXXXXXX):",
                reply_markup=get_cancel_keyboard()
            )
            logger.info(f"Адрес определен по геолокации: {address}")
        else:
            # Если не удалось определить адрес, просим ввести вручную
            await state.set_state(RequestStates.waiting_address_manual)
            await message.answer(
                "❌ Не удалось определить адрес по геолокации.\n"
                "Пожалуйста, введите адрес вручную:",
                reply_markup=get_cancel_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Ошибка обработки геолокации: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка. Попробуйте ввести адрес вручную.")
        await state.set_state(RequestStates.waiting_address_manual)

@router.message(RequestStates.waiting_address, F.text)
async def process_manual_address_choice(message: Message, state: FSMContext):
    """
    Обработка выбора ручного ввода адреса
    """
    if message.text == "⬅️ Отмена":
        await state.clear()
        await message.answer("❌ Создание заявки отменено.", reply_markup=get_customer_main_keyboard())
        return
    
    if message.text == "✏️ Ввести адрес вручную":
        await state.set_state(RequestStates.waiting_address_manual)
        await message.answer("✏️ Введите адрес вручную:", reply_markup=get_cancel_keyboard())
        return
    
    await message.answer("❌ Пожалуйста, используйте кнопки меню или отправьте геолокацию.")

@router.message(RequestStates.waiting_address_manual)
async def process_manual_address_input(message: Message, state: FSMContext):
    """
    Обработка ручного ввода адреса
    """
    if message.text == "⬅️ Отмена":
        await state.clear()
        await message.answer("❌ Создание заявки отменено.", reply_markup=get_customer_main_keyboard())
        return
    
    if not message.text or len(message.text.strip()) < 5:
        await message.answer("❌ Адрес должен содержать не менее 5 символов. Попробуйте еще раз:")
        return
    
    # Сохраняем адрес
    await state.update_data(address=message.text.strip())
    
    # Переходим к вводу телефона
    await state.set_state(RequestStates.waiting_phone)
    await message.answer(
        "📞 Введите номер телефона для связи\n"
        "(например: +7XXXXXXXXXX или 8XXXXXXXXXX):",
        reply_markup=get_cancel_keyboard()
    )

@router.message(RequestStates.waiting_phone)
async def process_phone(message: Message, state: FSMContext):
    """
    Обработка номера телефона
    """
    if message.text == "⬅️ Отмена":
        await state.clear()
        await message.answer("❌ Создание заявки отменено.", reply_markup=get_customer_main_keyboard())
        return
    
    phone = message.text.strip()
    
    # Проверяем корректность номера
    if not validate_phone(phone):
        await message.answer(
            "❌ Неверный формат номера.\n"
            "Пожалуйста, введите номер в формате +7XXXXXXXXXX или 8XXXXXXXXXX:"
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
    logger.info(f"Пользователь ввел телефон, переходим к выбору района")

@router.callback_query(StateFilter(RequestStates.waiting_district))
async def debug_district_callback(callback: CallbackQuery, state: FSMContext):
    """
    Отладочный обработчик для просмотра всех callback'ов в состоянии выбора района
    """
    logger.info(f"DEBUG - Callback в состоянии выбора района: {callback.data}")
    logger.info(f"DEBUG - От пользователя: {callback.from_user.id}")
    
    # Проверяем состояние
    current_state = await state.get_state()
    data = await state.get_data()
    logger.info(f"DEBUG - Текущее состояние: {current_state}")
    logger.info(f"DEBUG - Данные состояния: {data}")
    
    # Если это наш callback, передаем дальше
    if callback.data.startswith("district_"):
        await process_district(callback, state)
    else:
        await callback.answer("Неизвестное действие")

async def process_district(callback: CallbackQuery, state: FSMContext, session: AsyncSession = None):
    """
    Обработка выбора района и создание заявки - ИСПРАВЛЕНО
    """
    try:
        # Отвечаем на callback сразу, чтобы избежать таймаута
        await callback.answer("Обрабатываю выбор района...")
        
        # Получаем сессию БД если не передана
        if not session:
            async for db_session in get_db():
                session = db_session
                break
        
        # Извлекаем название района из callback_data
        district_callback = callback.data.replace("district_", "")
        # Восстанавливаем оригинальное название (заменяем _ на пробелы)
        district_name = district_callback.replace('_', ' ')
        
        logger.info(f"Выбран район: {district_name} (callback: {district_callback})")
        
        # Проверяем, что район есть в списке
        if district_name not in DISTRICTS:
            # Пробуем найти по частичному совпадению
            found = False
            for d in DISTRICTS:
                normalized_d = d.replace(' ', '_').replace('-', '_').replace('.', '_')
                if normalized_d == district_callback:
                    district_name = d
                    found = True
                    break
            
            if not found:
                logger.error(f"Район не найден: {district_name}")
                await callback.message.edit_text(
                    "❌ Ошибка: выбранный район не найден. Попробуйте снова.",
                    reply_markup=get_district_keyboard()
                )
                return
        
        # Получаем все данные из состояния
        data = await state.get_data()
        
        # Проверяем наличие всех необходимых данных
        required_fields = ['description', 'address', 'phone']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            logger.error(f"Отсутствуют поля: {missing_fields}")
            await callback.message.edit_text(
                "❌ Ошибка: не все данные заполнены. Начните создание заявки заново."
            )
            await state.clear()
            return
        
        # Получаем пользователя
        query = select(User).where(User.telegram_id == callback.from_user.id)
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            logger.error(f"Пользователь не найден: {callback.from_user.id}")
            await callback.message.edit_text(
                "❌ Ошибка: пользователь не найден. Используйте /start для регистрации."
            )
            await state.clear()
            return
        
        # Получаем или создаем район в БД
        query = select(District).where(District.name == district_name)
        result = await session.execute(query)
        district = result.scalar_one_or_none()
        
        if not district:
            # Создаем район, если его нет в БД
            district = District(name=district_name, is_active=True)
            session.add(district)
            await session.flush()  # Получаем ID без коммита
            logger.info(f"Создан новый район в БД: {district_name}")
        
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
        await session.commit()  # Коммитим, чтобы получить ID заявки
        
        logger.info(f"Создана новая заявка #{new_request.id} в районе {district_name}")
        
        # Отправляем заявку в группу
        try:
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
                logger.info(f"Заявка #{new_request.id} отправлена в группу, message_id: {sent_message.message_id}")
            else:
                logger.error(f"Не удалось отправить заявку #{new_request.id} в группу")
                
        except Exception as e:
            logger.error(f"Ошибка при отправке в группу: {e}", exc_info=True)
            # Продолжаем выполнение, даже если не удалось отправить в группу
        
        # Очищаем состояние
        await state.clear()
        
        # Отправляем подтверждение заказчику
        await callback.message.edit_text(
            f"✅ <b>Заявка #{new_request.id} успешно создана!</b>\n\n"
            f"📍 <b>Адрес:</b> {data['address']}\n"
            f"🏘 <b>Район:</b> {district_name}\n"
            f"📞 <b>Телефон:</b> {data['phone']}\n"
            f"📸 <b>Фото:</b> {len(data.get('photos', []))} шт.\n\n"
            f"Монтажники уже получили уведомление. Мы оповестим вас, когда заявка будет взята в работу.",
            parse_mode="HTML"
        )
        
        # Возвращаем пользователя в главное меню
        await callback.message.answer(
            "Выберите действие:",
            reply_markup=get_customer_main_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка при создании заявки: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ Произошла ошибка при создании заявки. Пожалуйста, попробуйте снова."
        )
        await state.clear()
        await session.rollback()
