from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ContentType
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
import logging
from datetime import datetime
import json

from database import get_db
from models import User, Request, GroupMessage, Refusal, RequestStatus, UserRole
from states.customer_states import RefusalStates
from keyboards.reply import get_installer_main_keyboard, get_cancel_keyboard, remove_keyboard
from keyboards.inline import get_installer_request_keyboard, get_confirmation_keyboard
from services.notifications import NotificationService
from utils.helpers import extract_message_id, json_deserialize_photos
from config import GROUP_ID

logger = logging.getLogger(__name__)

router = Router()

@router.message(F.text == "📋 Мои заявки")
async def cmd_my_requests(message: Message, session: AsyncSession = None):
    """
    Просмотр списка активных заявок монтажника
    """
    try:
        # Получаем сессию БД если не передана
        if not session:
            async for db_session in get_db():
                session = db_session
                break
        
        # Получаем пользователя
        query = select(User).where(User.telegram_id == message.from_user.id)
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("Пользователь не найден. Используйте /start для регистрации.")
            return
        
        # Проверяем, что это монтажник
        if user.role != UserRole.INSTALLER:
            # Если это заказчик, показываем соответствующее сообщение
            await message.answer(
                "Эта функция доступна только монтажникам.\n"
                "Используйте меню заказчика для просмотра ваших заявок."
            )
            return
        
        # Получаем активные заявки монтажника (в работе)
        query = select(Request).where(
            and_(
                Request.installer_id == user.id,
                Request.status == RequestStatus.IN_PROGRESS
            )
        ).order_by(Request.created_at.desc())
        
        result = await session.execute(query)
        active_requests = result.scalars().all()
        
        # Получаем завершенные заявки (последние 5)
        query = select(Request).where(
            and_(
                Request.installer_id == user.id,
                Request.status == RequestStatus.COMPLETED
            )
        ).order_by(Request.completed_at.desc()).limit(5)
        
        result = await session.execute(query)
        completed_requests = result.scalars().all()
        
        if not active_requests and not completed_requests:
            await message.answer(
                "У вас пока нет заявок.\n"
                "Заявки можно брать в общем чате монтажников.",
                reply_markup=get_installer_main_keyboard()
            )
            return
        
        # Отправляем активные заявки
        if active_requests:
            text = "🔨 <b>Активные заявки в работе:</b>\n\n"
            
            for req in active_requests:
                time_taken = datetime.now() - req.taken_at
                hours = int(time_taken.total_seconds() / 3600)
                
                text += f"<b>Заявка #{req.id}</b>\n"
                text += f"📍 Адрес: {req.address[:50]}{'...' if len(req.address) > 50 else ''}\n"
                text += f"⏱ В работе: {hours} ч.\n"
                text += f"➖➖➖➖➖➖➖\n\n"
            
            await message.answer(text, parse_mode="HTML")
            
            # Отправляем детали каждой активной заявки
            for req in active_requests:
                await send_request_details(message, req, user, session)
        
        # Отправляем завершенные заявки
        if completed_requests:
            text = "✅ <b>Последние выполненные заявки:</b>\n\n"
            
            for req in completed_requests[:3]:  # Показываем только 3 последних
                text += f"<b>Заявка #{req.id}</b> - {req.completed_at.strftime('%d.%m.%Y')}\n"
                text += f"📍 {req.address[:50]}{'...' if len(req.address) > 50 else ''}\n"
                text += "➖➖➖➖➖➖➖\n"
            
            await message.answer(text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка в cmd_my_requests: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.callback_query(F.data.startswith("take_"))
async def process_take_request(callback: CallbackQuery, session: AsyncSession = None):
    """
    Монтажник берет заявку из группы
    """
    try:
        # Получаем сессию БД если не передана
        if not session:
            async for db_session in get_db():
                session = db_session
                break
        
        request_id = extract_message_id(callback.data, "take_")
        if not request_id:
            await callback.answer("Неверный ID заявки")
            return
        
        # Получаем заявку
        query = select(Request).where(Request.id == request_id)
        result = await session.execute(query)
        request = result.scalar_one_or_none()
        
        if not request:
            await callback.answer("Заявка не найдена")
            return
        
        # Проверяем статус
        if request.status != RequestStatus.NEW:
            await callback.answer("❌ Эта заявка уже взята другим монтажником")
            return
        
        # Получаем монтажника
        query = select(User).where(
            and_(
                User.telegram_id == callback.from_user.id,
                User.role == UserRole.INSTALLER
            )
        )
        result = await session.execute(query)
        installer = result.scalar_one_or_none()
        
        if not installer:
            await callback.answer("❌ Вы не зарегистрированы как монтажник")
            return
        
        # Обновляем заявку
        request.installer_id = installer.id
        request.status = RequestStatus.IN_PROGRESS
        request.taken_at = datetime.now()
        await session.commit()
        
        # Уведомляем заказчика
        notification_service = NotificationService(callback.bot, session)
        customer_name = installer.first_name or installer.username or "Монтажник"
        await notification_service.notify_customer(
            request.customer.telegram_id,
            f"✅ <b>Заявка #{request.id} взята в работу!</b>\n\n"
            f"👤 Монтажник: {customer_name}\n"
            f"📞 Скоро с вами свяжутся для уточнения деталей.\n\n"
            f"Статус заявки можно отслеживать в разделе «Мои заявки»."
        )
        
        # Отправляем детали заявки монтажнику
        await notification_service.send_request_details_to_installer(request, installer)
        
        # Обновляем сообщение в группе
        await notification_service.update_group_message(
            callback.message.chat.id,
            callback.message.message_id,
            request
        )
        
        await callback.answer("✅ Заявка взята в работу!")
        
        # Отправляем подтверждение в группу (опционально)
        await callback.message.answer(
            f"✅ Монтажник {customer_name} взял заявку #{request.id} в работу!"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при взятии заявки: {e}")
        await callback.answer("❌ Ошибка при взятии заявки")
        await session.rollback()

@router.callback_query(F.data.startswith("refuse_"))
async def process_refuse_request(callback: CallbackQuery, state: FSMContext, session: AsyncSession = None):
    """
    Монтажник отказывается от заявки - запрос причины
    """
    try:
        request_id = extract_message_id(callback.data, "refuse_")
        if not request_id:
            await callback.answer("Неверный ID заявки")
            return
        
        # Получаем сессию БД если не передана
        if not session:
            async for db_session in get_db():
                session = db_session
                break
        
        # Получаем заявку для проверки
        query = select(Request).where(Request.id == request_id)
        result = await session.execute(query)
        request = result.scalar_one_or_none()
        
        if not request:
            await callback.answer("Заявка не найдена")
            return
        
        # Проверяем, что заявка еще новая
        if request.status != RequestStatus.NEW:
            await callback.answer("❌ Эта заявка уже не доступна для отказа")
            return
        
        # Сохраняем ID заявки в состояние
        await state.update_data(refuse_request_id=request_id)
        await state.set_state(RefusalStates.waiting_reason)
        
        await callback.message.answer(
            "❓ Пожалуйста, укажите причину отказа от заявки:\n"
            "(например: далеко, сложная работа, нет времени и т.д.)",
            reply_markup=get_cancel_keyboard()
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при запросе причины отказа: {e}")
        await callback.answer("❌ Ошибка")

@router.message(StateFilter(RefusalStates.waiting_reason))
async def process_refuse_reason(message: Message, state: FSMContext, session: AsyncSession = None):
    """
    Обработка причины отказа и завершение отказа
    """
    try:
        # Получаем сессию БД если не передана
        if not session:
            async for db_session in get_db():
                session = db_session
                break
        
        if message.text == "⬅️ Отмена":
            await state.clear()
            await message.answer(
                "Отказ отменен.",
                reply_markup=get_installer_main_keyboard()
            )
            return
        
        if not message.text or len(message.text) < 5:
            await message.answer(
                "Причина должна содержать не менее 5 символов. Попробуйте еще раз:",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        # Получаем данные из состояния
        data = await state.get_data()
        request_id = data.get('refuse_request_id')
        
        if not request_id:
            await state.clear()
            await message.answer("Ошибка: заявка не найдена")
            return
        
        # Получаем заявку
        query = select(Request).where(Request.id == request_id)
        result = await session.execute(query)
        request = result.scalar_one_or_none()
        
        if not request:
            await message.answer("Заявка не найдена")
            await state.clear()
            return
        
        # Проверяем статус
        if request.status != RequestStatus.NEW:
            await message.answer(
                "❌ Статус заявки изменился. Отказ невозможен.",
                reply_markup=get_installer_main_keyboard()
            )
            await state.clear()
            return
        
        # Получаем монтажника
        query = select(User).where(User.telegram_id == message.from_user.id)
        result = await session.execute(query)
        installer = result.scalar_one_or_none()
        
        if not installer:
            await message.answer("Пользователь не найден")
            await state.clear()
            return
        
        # Создаем запись об отказе
        refusal = Refusal(
            request_id=request.id,
            installer_id=installer.id,
            reason=message.text
        )
        
        session.add(refusal)
        await session.commit()
        
        # Обновляем сообщение в группе
        query = select(GroupMessage).where(GroupMessage.request_id == request.id)
        result = await session.execute(query)
        group_message = result.scalar_one_or_none()
        
        if group_message:
            notification_service = NotificationService(message.bot, session)
            await notification_service.update_group_message(
                group_message.chat_id,
                group_message.message_id,
                request
            )
        
        await message.answer(
            f"✅ Отказ зарегистрирован.\n"
            f"Заявка #{request.id} осталась в группе для других монтажников.",
            reply_markup=get_installer_main_keyboard()
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при отказе от заявки: {e}")
        await message.answer("❌ Произошла ошибка")
        await state.clear()
        await session.rollback()

@router.callback_query(F.data.startswith("complete_"))
async def process_complete_request(callback: CallbackQuery, state: FSMContext, session: AsyncSession = None):
    """
    Завершение заявки монтажником
    """
    try:
        # Получаем сессию БД если не передана
        if not session:
            async for db_session in get_db():
                session = db_session
                break
        
        request_id = extract_message_id(callback.data, "complete_")
        if not request_id:
            await callback.answer("Неверный ID заявки")
            return
        
        # Получаем заявку
        query = select(Request).where(Request.id == request_id)
        result = await session.execute(query)
        request = result.scalar_one_or_none()
        
        if not request:
            await callback.answer("Заявка не найдена")
            return
        
        # Получаем монтажника
        query = select(User).where(User.telegram_id == callback.from_user.id)
        result = await session.execute(query)
        installer = result.scalar_one_or_none()
        
        # Проверяем, что монтажник имеет право завершить заявку
        if not installer or request.installer_id != installer.id:
            await callback.answer("❌ У вас нет прав для завершения этой заявки")
            return
        
        # Проверяем статус
        if request.status != RequestStatus.IN_PROGRESS:
            await callback.answer("❌ Заявка уже завершена или не в работе")
            return
        
        # Запрашиваем подтверждение
        await callback.message.answer(
            f"❓ Подтвердите завершение заявки #{request.id}",
            reply_markup=get_confirmation_keyboard(request_id, "complete")
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при запросе подтверждения завершения: {e}")
        await callback.answer("❌ Ошибка")

@router.callback_query(F.data.startswith("confirm_complete_"))
async def confirm_complete_request(callback: CallbackQuery, session: AsyncSession = None):
    """
    Подтверждение завершения заявки
    """
    try:
        # Получаем сессию БД если не передана
        if not session:
            async for db_session in get_db():
                session = db_session
                break
        
        request_id = extract_message_id(callback.data, "confirm_complete_")
        if not request_id:
            await callback.answer("Неверный ID заявки")
            return
        
        # Получаем заявку
        query = select(Request).where(Request.id == request_id)
        result = await session.execute(query)
        request = result.scalar_one_or_none()
        
        if not request:
            await callback.answer("Заявка не найдена")
            return
        
        # Получаем монтажника
        query = select(User).where(User.telegram_id == callback.from_user.id)
        result = await session.execute(query)
        installer = result.scalar_one_or_none()
        
        if not installer or request.installer_id != installer.id:
            await callback.answer("❌ У вас нет прав для завершения этой заявки")
            return
        
        # Обновляем статус
        request.status = RequestStatus.COMPLETED
        request.completed_at = datetime.now()
        await session.commit()
        
        # Уведомляем заказчика
        notification_service = NotificationService(callback.bot, session)
        installer_name = installer.first_name or installer.username or "Монтажник"
        
        await notification_service.notify_customer(
            request.customer.telegram_id,
            f"✅ <b>Заявка #{request.id} выполнена!</b>\n\n"
            f"👤 Монтажник: {installer_name}\n"
            f"📅 Дата завершения: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Спасибо за обращение! Если остались вопросы, создайте новую заявку."
        )
        
        # Обновляем сообщение в ЛС монтажника
        if callback.message.photo:
            await callback.message.edit_caption(
                callback.message.caption + "\n\n✅ <b>Заявка завершена!</b>",
                parse_mode="HTML",
                reply_markup=None
            )
        else:
            await callback.message.edit_text(
                callback.message.text + "\n\n✅ <b>Заявка завершена!</b>",
                parse_mode="HTML",
                reply_markup=None
            )
        
        # Обновляем сообщение в группе
        query = select(GroupMessage).where(GroupMessage.request_id == request.id)
        result = await session.execute(query)
        group_message = result.scalar_one_or_none()
        
        if group_message:
            await notification_service.update_group_message(
                group_message.chat_id,
                group_message.message_id,
                request
            )
        
        await callback.message.answer(
            f"✅ Заявка #{request.id} успешно завершена!",
            reply_markup=get_installer_main_keyboard()
        )
        
        await callback.answer("✅ Заявка завершена!")
        
    except Exception as e:
        logger.error(f"Ошибка при завершении заявки: {e}")
        await callback.answer("❌ Ошибка при завершении заявки")
        await session.rollback()

@router.callback_query(F.data.startswith("cancel_complete_"))
async def cancel_complete_request(callback: CallbackQuery):
    """
    Отмена завершения заявки
    """
    await callback.message.delete()
    await callback.answer("Завершение отменено")

@router.callback_query(F.data.startswith("view_coords_"))
async def view_request_coords(callback: CallbackQuery, session: AsyncSession = None):
    """
    Просмотр координат заявки на карте
    """
    try:
        request_id = extract_message_id(callback.data, "view_coords_")
        if not request_id:
            await callback.answer("Неверный ID заявки")
            return
        
        # Получаем сессию БД если не передана
        if not session:
            async for db_session in get_db():
                session = db_session
                break
        
        # Получаем заявку
        query = select(Request).where(Request.id == request_id)
        result = await session.execute(query)
        request = result.scalar_one_or_none()
        
        if not request or not request.latitude or not request.longitude:
            await callback.answer("Координаты не найдены")
            return
        
        # Отправляем локацию
        await callback.message.answer_location(
            latitude=request.latitude,
            longitude=request.longitude,
            reply_to_message_id=callback.message.message_id
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при отправке координат: {e}")
        await callback.answer("❌ Ошибка")

@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: Message):
    """
    Справка для монтажника
    """
    help_text = """
<b>🛠 Помощь для монтажника</b>

<b>Доступные команды:</b>
• 📋 Мои заявки - посмотреть ваши активные и завершенные заявки
• ℹ️ Помощь - показать это сообщение

<b>Как работать с заявками:</b>

1️⃣ <b>Взять заявку:</b>
   - В общем чате монтажников нажмите "✅ Взять"
   - Заявка появится в разделе "Мои заявки"
   - Заказчик получит уведомление

2️⃣ <b>Отказаться от заявки:</b>
   - Если заявка еще новая, нажмите "❌ Отказаться"
   - Укажите причину отказа

3️⃣ <b>Завершить заявку:</b>
   - В личном чате с ботом нажмите "✅ Завершить"
   - Подтвердите завершение работы
   - Заказчик получит уведомление

<b>Важно:</b>
• Не берите заявки, которые не можете выполнить
• Всегда указывайте причину отказа
• После завершения заявки она попадает в статистику

По вопросам: @admin
    """
    
    await message.answer(help_text, parse_mode="HTML", reply_markup=get_installer_main_keyboard())

@router.message(Command("stats"))
async def cmd_my_stats(message: Message, session: AsyncSession = None):
    """
    Просмотр личной статистики монтажника
    """
    try:
        # Получаем сессию БД если не передана
        if not session:
            async for db_session in get_db():
                session = db_session
                break
        
        # Получаем пользователя
        query = select(User).where(User.telegram_id == message.from_user.id)
        result = await session.execute(query)
        installer = result.scalar_one_or_none()
        
        if not installer or installer.role != UserRole.INSTALLER:
            await message.answer("Эта функция доступна только монтажникам")
            return
        
        # Получаем статистику
        # Всего выполнено
        query = select(Request).where(
            and_(
                Request.installer_id == installer.id,
                Request.status == RequestStatus.COMPLETED
            )
        )
        result = await session.execute(query)
        completed = len(result.scalars().all())
        
        # В работе
        query = select(Request).where(
            and_(
                Request.installer_id == installer.id,
                Request.status == RequestStatus.IN_PROGRESS
            )
        )
        result = await session.execute(query)
        in_progress = len(result.scalars().all())
        
        # Отказы
        query = select(Refusal).where(Refusal.installer_id == installer.id)
        result = await session.execute(query)
        refusals = len(result.scalars().all())
        
        # За последние 30 дней
        month_ago = datetime.now() - datetime.timedelta(days=30)
        query = select(Request).where(
            and_(
                Request.installer_id == installer.id,
                Request.status == RequestStatus.COMPLETED,
                Request.completed_at >= month_ago
            )
        )
        result = await session.execute(query)
        month_completed = len(result.scalars().all())
        
        text = f"📊 <b>Статистика монтажника</b>\n\n"
        text += f"👤 {installer.first_name or installer.username}\n\n"
        text += f"✅ Выполнено всего: {completed}\n"
        text += f"🔵 В работе: {in_progress}\n"
        text += f"❌ Отказов: {refusals}\n"
        text += f"📅 За 30 дней: {month_completed}\n"
        
        await message.answer(text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка в cmd_my_stats: {e}")
        await message.answer("❌ Ошибка при получении статистики")

async def send_request_details(message: Message, request: Request, installer: User, session: AsyncSession):
    """
    Отправка деталей заявки монтажнику
    """
    try:
        notification_service = NotificationService(message.bot, session)
        await notification_service.send_request_details_to_installer(request, installer)
    except Exception as e:
        logger.error(f"Ошибка отправки деталей заявки: {e}")
