from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
import logging
from datetime import datetime

from database import get_db
from models import User, Request, GroupMessage, Refusal, RequestStatus, UserRole
from states.customer_states import RefusalStates
from keyboards.reply import get_installer_main_keyboard, remove_keyboard
from keyboards.inline import get_installer_request_keyboard
from services.notifications import NotificationService
from utils.helpers import extract_message_id
from config import GROUP_ID

logger = logging.getLogger(__name__)

router = Router()

@router.message(Command("my_requests"))
@router.message(F.text == "📋 Мои заявки")
async def cmd_my_requests(message: Message, session: AsyncSession = None):
    """
    Просмотр списка активных заявок монтажника
    """
    try:
        if not session:
            async for db_session in get_db():
                session = db_session
                break

        query = select(User).where(User.telegram_id == message.from_user.id)
        result = await session.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("Пользователь не найден. Используйте /start для регистрации.")
            return

        query = select(Request).where(
            and_(
                Request.installer_id == user.id,
                Request.status == RequestStatus.IN_PROGRESS
            )
        ).order_by(Request.created_at.desc())

        result = await session.execute(query)
        requests = result.scalars().all()

        if not requests:
            await message.answer("У вас нет активных заявок.")
            return

        text = "📋 <b>Ваши активные заявки:</b>\n\n"
        for req in requests:
            text += f"🔨 Заявка #{req.id}\n"
            text += f"📍 Адрес: {req.address[:50]}...\n"
            text += f"📅 Взята: {req.taken_at.strftime('%d.%m.%Y %H:%M') if req.taken_at else 'Неизвестно'}\n"
            text += "➖➖➖➖➖➖➖\n"

        await message.answer(text, parse_mode="HTML")

        for req in requests:
            await send_request_details(message, req, user, session)

    except Exception as e:
        logger.error(f"Ошибка в cmd_my_requests: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.callback_query(F.data.startswith("complete_"))
async def process_complete_request(callback: CallbackQuery, state: FSMContext, session: AsyncSession = None):
    """
    Завершение заявки монтажником
    """
    try:
        if not session:
            async for db_session in get_db():
                session = db_session
                break

        request_id = extract_message_id(callback.data, "complete_")
        if not request_id:
            await callback.answer("Неверный ID заявки")
            return

        query = select(Request).where(Request.id == request_id)
        result = await session.execute(query)
        request = result.scalar_one_or_none()

        if not request:
            await callback.answer("Заявка не найдена")
            return

        query = select(User).where(User.telegram_id == callback.from_user.id)
        result = await session.execute(query)
        installer = result.scalar_one_or_none()

        if not installer or request.installer_id != installer.id:
            await callback.answer("У вас нет прав для завершения этой заявки")
            return

        if request.status != RequestStatus.IN_PROGRESS:
            await callback.answer("Заявка уже завершена или не в работе")
            return

        request.status = RequestStatus.COMPLETED
        request.completed_at = datetime.now()
        await session.commit()

        notification_service = NotificationService(callback.bot, session)
        await notification_service.notify_customer(
            request.customer.telegram_id,
            f"✅ Заявка #{request.id} выполнена!\n\n"
            f"Монтажник {installer.first_name or installer.username} завершил работу."
        )

        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.edit_caption(
            callback.message.caption + "\n\n✅ <b>Заявка завершена!</b>",
            parse_mode="HTML"
        )

        query = select(GroupMessage).where(GroupMessage.request_id == request.id)
        result = await session.execute(query)
        group_message = result.scalar_one_or_none()

        if group_message:
            await notification_service.update_group_message(
                group_message.chat_id,
                group_message.message_id,
                request
            )

        await callback.answer("Заявка успешно завершена!")

    except Exception as e:
        logger.error(f"Ошибка при завершении заявки: {e}", exc_info=True)
        await callback.answer("Ошибка при завершении заявки")
        await session.rollback()

@router.callback_query(F.data.startswith("take_"))
async def process_take_request(callback: CallbackQuery, session: AsyncSession = None):
    """
    Монтажник берет заявку из группы (атомарное обновление)
    """
    try:
        if not session:
            async for db_session in get_db():
                session = db_session
                break

        request_id = extract_message_id(callback.data, "take_")
        if not request_id:
            await callback.answer("Неверный ID заявки")
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
            await callback.answer("Вы не зарегистрированы как монтажник")
            return

        # Атомарно обновляем заявку
        stmt = update(Request).where(
            Request.id == request_id,
            Request.status == RequestStatus.NEW
        ).values(
            installer_id=installer.id,
            status=RequestStatus.IN_PROGRESS,
            taken_at=datetime.now()
        ).returning(Request)

        result = await session.execute(stmt)
        updated_request = result.scalar_one_or_none()
        await session.commit()

        if not updated_request:
            # Если не обновилось, значит заявка уже не NEW
            await callback.answer("❌ Эта заявка уже принята другим монтажником")
            return

        logger.info(f"Монтажник {installer.id} взял заявку {request_id}")

        # Уведомляем заказчика
        notification_service = NotificationService(callback.bot, session)
        await notification_service.notify_customer(
            updated_request.customer.telegram_id,
            f"🔨 Заявка #{updated_request.id} взята в работу!\n\n"
            f"Монтажник: {installer.first_name or installer.username}\n"
            f"Скоро с вами свяжутся."
        )

        # Отправляем детали монтажнику
        await notification_service.send_request_details_to_installer(updated_request, installer)

        # Обновляем сообщение в группе
        query = select(GroupMessage).where(GroupMessage.request_id == updated_request.id)
        result = await session.execute(query)
        group_message = result.scalar_one_or_none()

        if group_message:
            try:
                await notification_service.update_group_message(
                    group_message.chat_id,
                    group_message.message_id,
                    updated_request
                )
            except Exception as e:
                logger.error(f"Не удалось обновить сообщение в группе: {e}")
                # Пытаемся отправить новое сообщение
                await callback.bot.send_message(
                    group_message.chat_id,
                    f"⚠️ Заявка #{updated_request.id} взята монтажником {installer.first_name or installer.username}.\n"
                    f"(не удалось обновить оригинальное сообщение)"
                )

        await callback.answer("✅ Заявка взята в работу!")

    except Exception as e:
        logger.error(f"Ошибка при взятии заявки: {e}", exc_info=True)
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

        # Дополнительно проверим статус заявки, чтобы не предлагать отказ, если она уже взята
        if not session:
            async for db_session in get_db():
                session = db_session
                break

        query = select(Request).where(Request.id == request_id)
        result = await session.execute(query)
        request = result.scalar_one_or_none()

        if not request:
            await callback.answer("Заявка не найдена")
            return

        if request.status != RequestStatus.NEW:
            await callback.answer("❌ Эта заявка уже взята или завершена, отказ невозможен")
            return

        await state.update_data(refuse_request_id=request_id)
        await state.set_state(RefusalStates.waiting_reason)

        await callback.message.answer(
            "❓ Пожалуйста, укажите причину отказа от заявки:",
            reply_markup=remove_keyboard
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при запросе причины отказа: {e}", exc_info=True)
        await callback.answer("Ошибка")

@router.message(StateFilter(RefusalStates.waiting_reason))
async def process_refuse_reason(message: Message, state: FSMContext, session: AsyncSession = None):
    """
    Обработка причины отказа и завершение отказа
    """
    try:
        if not session:
            async for db_session in get_db():
                session = db_session
                break

        if message.text == "⬅️ Отмена":
            await state.clear()
            await message.answer("Отказ отменен.", reply_markup=get_installer_main_keyboard())
            return

        if not message.text or len(message.text) < 5:
            await message.answer("Причина должна содержать не менее 5 символов. Попробуйте еще раз:")
            return

        data = await state.get_data()
        request_id = data.get('refuse_request_id')

        if not request_id:
            await state.clear()
            await message.answer("Ошибка: заявка не найдена")
            return

        # Повторно проверяем статус внутри транзакции
        async with session.begin():
            query = select(Request).where(Request.id == request_id).with_for_update()
            result = await session.execute(query)
            request = result.scalar_one_or_none()

            if not request:
                await message.answer("Заявка не найдена")
                await state.clear()
                return

            if request.status != RequestStatus.NEW:
                await message.answer("❌ Заявка уже взята другим монтажником. Отказ невозможен.")
                await state.clear()
                return

            query = select(User).where(User.telegram_id == message.from_user.id)
            result = await session.execute(query)
            installer = result.scalar_one_or_none()

            refusal = Refusal(
                request_id=request.id,
                installer_id=installer.id,
                reason=message.text
            )
            session.add(refusal)
            # Статус заявки не меняем, она остаётся new

        await session.commit()

        # Обновляем сообщение в группе (можно добавить пометку об отказе, но это необязательно)
        query = select(GroupMessage).where(GroupMessage.request_id == request.id)
        result = await session.execute(query)
        group_message = result.scalar_one_or_none()

        if group_message:
            try:
                # Можно отредактировать сообщение, добавив информацию о том, что был отказ
                # Но для простоты пока ничего не делаем
                pass
            except Exception as e:
                logger.error(f"Ошибка при обновлении сообщения после отказа: {e}")

        await message.answer(
            "✅ Отказ зарегистрирован. Заявка осталась в группе для других монтажников.",
            reply_markup=get_installer_main_keyboard()
        )

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при отказе от заявки: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка")
        await state.clear()
        await session.rollback()

async def send_request_details(message: Message, request: Request, installer: User, session: AsyncSession):
    """
    Отправка деталей заявки монтажнику
    """
    try:
        notification_service = NotificationService(message.bot, session)
        await notification_service.send_request_details_to_installer(request, installer)
    except Exception as e:
        logger.error(f"Ошибка отправки деталей заявки: {e}")
