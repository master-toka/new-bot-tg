from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import User, Request, GroupMessage, Refusal
from keyboards import installer_menu, installer_request_actions, group_request_keyboard
from utils import format_request_for_group, format_request_for_installer, logger
from config import GROUP_ID, BOT_TOKEN
import json

router = Router()
bot = Bot(token=BOT_TOKEN)

class RefuseFSM(StatesGroup):
    reason = State()

# Функция отправки заявки в группу (вызывается из customer)
async def send_request_to_group(request_id: int, session: AsyncSession):
    from handlers.installer import bot
    request = await session.get(Request, request_id)
    customer = await session.get(User, request.customer_id)
    district = await session.get(District, request.district_id)
    text = format_request_for_group(request, customer.name, district.name)
    photos = json.loads(request.photos) if request.photos else []

    if photos:
        # Отправляем медиагруппу
        media = [InputMediaPhoto(media=photos[0], caption=text)]
        for p in photos[1:]:
            media.append(InputMediaPhoto(media=p))
        msgs = await bot.send_media_group(GROUP_ID, media)
        # Первое сообщение получит кнопки
        first_msg = msgs[0]
        await bot.edit_message_reply_markup(GROUP_ID, first_msg.message_id, reply_markup=group_request_keyboard(request.id))
        # Сохраняем связь с сообщением
        group_msg = GroupMessage(request_id=request.id, message_id=first_msg.message_id)
        session.add(group_msg)
        await session.commit()
    else:
        # Без фото
        msg = await bot.send_message(GROUP_ID, text, reply_markup=group_request_keyboard(request.id))
        group_msg = GroupMessage(request_id=request.id, message_id=msg.message_id)
        session.add(group_msg)
        await session.commit()

    # Если есть координаты, отправляем геолокацию отдельно
    if request.latitude and request.longitude:
        await bot.send_location(GROUP_ID, request.latitude, request.longitude)

# Обработка нажатия "Взять"
@router.callback_query(F.data.startswith("take_"))
async def take_request(callback: CallbackQuery, state: FSMContext):
    request_id = int(callback.data.split("_")[1])
    installer_tg_id = callback.from_user.id

    async for session in get_db():
        # Проверяем, что пользователь — монтажник
        installer = await session.execute(select(User).where(User.telegram_id == installer_tg_id, User.role == "installer"))
        installer = installer.scalar_one_or_none()
        if not installer:
            await callback.answer("Вы не зарегистрированы как монтажник.", show_alert=True)
            return

        # Получаем заявку
        request = await session.get(Request, request_id)
        if not request or request.status != "new":
            await callback.answer("Заявка уже недоступна.", show_alert=True)
            return

        # Обновляем статус
        request.status = "in_progress"
        request.installer_id = installer.id
        request.taken_at = func.now()
        await session.commit()

        # Редактируем сообщение в группе: убираем кнопки и добавляем инфо о взятии
        group_msg = await session.execute(select(GroupMessage).where(GroupMessage.request_id == request_id))
        group_msg = group_msg.scalar_one()
        await bot.edit_message_text(
            chat_id=GROUP_ID,
            message_id=group_msg.message_id,
            text=callback.message.text + f"\n\n✅ Взято монтажником: {installer.name}",
            reply_markup=None
        )

        # Уведомляем заказчика
        customer = await session.get(User, request.customer_id)
        await bot.send_message(
            customer.telegram_id,
            f"Заявка №{request.id} взята в работу монтажником {installer.name}."
        )

        # Отправляем детали монтажнику в ЛС
        await send_request_details_to_installer(request.id, installer.telegram_id, session)

    await callback.answer()

async def send_request_details_to_installer(request_id: int, installer_tg_id: int, session: AsyncSession):
    request = await session.get(Request, request_id)
    customer = await session.get(User, request.customer_id)
    district = await session.get(District, request.district_id)
    text = format_request_for_installer(request, customer.name, district.name)
    photos = json.loads(request.photos) if request.photos else []
    has_coords = request.latitude is not None

    if photos:
        media = [InputMediaPhoto(media=photos[0], caption=text)]
        for p in photos[1:]:
            media.append(InputMediaPhoto(media=p))
        await bot.send_media_group(installer_tg_id, media)
        # Кнопки прикрепим к первому сообщению
        # TODO: получить message_id первого сообщения и отредактировать с кнопками - сложно с media_group, можно просто отправить отдельно кнопки
        await bot.send_message(installer_tg_id, "Действия:", reply_markup=installer_request_actions(request_id, has_coords))
    else:
        await bot.send_message(installer_tg_id, text, reply_markup=installer_request_actions(request_id, has_coords))

# Обработка отказа
@router.callback_query(F.data.startswith("refuse_"))
async def refuse_request(callback: CallbackQuery, state: FSMContext):
    request_id = int(callback.data.split("_")[1])
    installer_tg_id = callback.from_user.id

    async for session in get_db():
        installer = await session.execute(select(User).where(User.telegram_id == installer_tg_id, User.role == "installer"))
        installer = installer.scalar_one_or_none()
        if not installer:
            await callback.answer("Вы не монтажник.", show_alert=True)
            return

        request = await session.get(Request, request_id)
        if request.status != "new":
            await callback.answer("Заявка уже обработана.", show_alert=True)
            return

    # Запускаем FSM для ввода причины
    await state.set_state(RefuseFSM.reason)
    await state.update_data(request_id=request_id, installer_id=installer.id)
    await callback.message.answer("Укажите причину отказа:")
    await callback.answer()

@router.message(RefuseFSM.reason)
async def process_refuse_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    request_id = data["request_id"]
    installer_id = data["installer_id"]
    reason = message.text

    async for session in get_db():
        refusal = Refusal(request_id=request_id, installer_id=installer_id, reason=reason)
        session.add(refusal)
        # Заявка остаётся new, можно обновить сообщение в группе (по желанию)
        group_msg = await session.execute(select(GroupMessage).where(GroupMessage.request_id == request_id))
        group_msg = group_msg.scalar_one()
        await bot.edit_message_text(
            chat_id=GROUP_ID,
            message_id=group_msg.message_id,
            text=message.reply_to_message.text + f"\n\n❌ Отказ от {message.from_user.full_name}: {reason}",
            reply_markup=group_request_keyboard(request_id)  # оставляем кнопки для других
        )
        await session.commit()

    await message.answer("Причина отказа записана.")
    await state.clear()

# Просмотр активных заявок монтажником в ЛС
@router.message(Command("my_requests"))
@router.message(F.text == "📋 Мои активные заявки")
async def my_requests(message: Message):
    installer_tg_id = message.from_user.id
    async for session in get_db():
        installer = await session.execute(select(User).where(User.telegram_id == installer_tg_id))
        installer = installer.scalar_one_or_none()
        if not installer or installer.role != "installer":
            await message.answer("Эта команда только для монтажников.")
            return

        requests = await session.execute(
            select(Request).where(Request.installer_id == installer.id, Request.status == "in_progress")
        )
        requests = requests.scalars().all()

        if not requests:
            await message.answer("У вас нет активных заявок.")
            return

        for req in requests:
            district = await session.get(District, req.district_id)
            text = f"Заявка #{req.id} - {district.name}\nАдрес: {req.address}"
            # Кнопки с действиями
            await message.answer(text, reply_markup=installer_request_actions(req.id, req.latitude is not None))

# Действия по кнопкам из ЛС
@router.callback_query(F.data.startswith("map_"))
async def show_map(callback: CallbackQuery):
    request_id = int(callback.data.split("_")[1])
    async for session in get_db():
        request = await session.get(Request, request_id)
        if request and request.latitude and request.longitude:
            # Отправляем ссылку на Яндекс.Карты
            yandex_url = f"https://yandex.ru/maps/?pt={request.longitude},{request.latitude}&z=17&l=map"
            await callback.message.answer(f"🗺 [Открыть на карте]({yandex_url})", parse_mode="Markdown")
        else:
            await callback.answer("Координаты отсутствуют.", show_alert=True)
    await callback.answer()

@router.callback_query(F.data.startswith("call_"))
async def call_phone(callback: CallbackQuery):
    request_id = int(callback.data.split("_")[1])
    async for session in get_db():
        request = await session.get(Request, request_id)
        if request and request.phone:
            await callback.message.answer(f"📞 Телефон: {request.phone}\nСсылка для звонка: tel:{request.phone}")
        else:
            await callback.answer("Телефон не указан.", show_alert=True)
    await callback.answer()

@router.callback_query(F.data.startswith("complete_"))
async def complete_request(callback: CallbackQuery):
    request_id = int(callback.data.split("_")[1])
    installer_tg_id = callback.from_user.id
    async for session in get_db():
        installer = await session.execute(select(User).where(User.telegram_id == installer_tg_id))
        installer = installer.scalar_one()
        request = await session.get(Request, request_id)
        if not request or request.installer_id != installer.id or request.status != "in_progress":
            await callback.answer("Ошибка: заявка не в работе у вас.", show_alert=True)
            return

        request.status = "completed"
        request.completed_at = func.now()
        await session.commit()

        # Уведомляем заказчика
        customer = await session.get(User, request.customer_id)
        await bot.send_message(customer.telegram_id, f"Заявка №{request.id} выполнена монтажником {installer.name}.")

        # Редактируем сообщение в группе, если оно есть
        group_msg = await session.execute(select(GroupMessage).where(GroupMessage.request_id == request_id))
        group_msg = group_msg.scalar_one_or_none()
        if group_msg:
            await bot.edit_message_text(
                chat_id=GROUP_ID,
                message_id=group_msg.message_id,
                text=callback.message.text + "\n\n✅ Заявка выполнена.",
                reply_markup=None
            )

        await callback.message.edit_text(callback.message.text + "\n\n✅ Заявка завершена.")
    await callback.answer()