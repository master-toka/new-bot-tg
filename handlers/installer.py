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

# Настройка подробного логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

router = Router()

@router.message(Command("my_requests"))
@router.message(F.text == "📋 Мои заявки")
async def cmd_my_requests(message: Message, session: AsyncSession = None):
    """
    Просмотр списка активных заявок монтажника
    """
    try:
        logger.info(f"Монтажник {message.from_user.id} запросил список заявок")
        
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

        # Отправляем детали каждой заявки
        for req in requests:
            await send_request_details(message, req, user, session)

    except Exception as e:
        logger.error(f"Ошибка в cmd_my_requests: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.callback_query(F.data.startswith("take_"))
async def process_take_request(callback: CallbackQuery, session: AsyncSession = None):
    """
    Монтажник берет заявку из группы - БЕЗ ФИЛЬТРА ПО ЧАТУ
    """
    try:
        # Подробное логирование входящего callback
        logger.info("=" * 50)
        logger.info(f"🔥 TAKE CALLBACK ПОЛУЧЕН: {callback.data}")
        logger.info(f"🔥 От пользователя: {callback.from_user.id} (@{callback.from_user.username})")
        logger.info(f"🔥 В чате: {callback.message.chat.id} ({callback.message.chat.type})")
        logger.info(f"🔥 Сообщение ID: {callback.message.message_id}")
        logger.info("=" * 50)

        # Отвечаем на callback сразу, чтобы избежать таймаута
        await callback.answer("⏳ Обрабатываю запрос...")

        # Проверяем, что это группа монтажников
        if callback.message.chat.id != GROUP_ID:
            logger.warning(f"⚠️ Попытка взять заявку из другого чата: {callback.message.chat.id}")
            await callback.answer("❌ Это действие доступно только в группе монтажников", show_alert=True)
            return

        if not session:
            logger.debug("Создаем новую сессию БД")
            async for db_session in get_db():
                session = db_session
                break

        # Извлекаем ID заявки
        request_id = extract_message_id(callback.data, "take_")
        logger.info(f"📌 Извлечен ID заявки: {request_id}")

        if not request_id:
            logger.error("❌ Не удалось извлечь ID заявки из callback_data")
            await callback.answer("❌ Неверный ID заявки", show_alert=True)
            return

        # Получаем монтажника
        logger.debug(f"🔍 Поиск монтажника с telegram_id: {callback.from_user.id}")
        query = select(User).where(
            and_(
                User.telegram_id == callback.from_user.id,
                User.role == UserRole.INSTALLER
            )
        )
        result = await session.execute(query)
        installer = result.scalar_one_or_none()

        if not installer:
            logger.error(f"❌ Пользователь {callback.from_user.id} не найден или не является монтажником")
            await callback.answer("❌ Вы не зарегистрированы как монтажник", show_alert=True)
            return

        logger.info(f"✅ Монтажник найден: ID={installer.id}, имя={installer.first_name}")

        # Получаем информацию о заявке ДО обновления для логирования
        query = select(Request).where(Request.id == request_id)
        result = await session.execute(query)
        request_before = result.scalar_one_or_none()

        if not request_before:
            logger.error(f"❌ Заявка с ID {request_id} не найдена")
            await callback.answer("❌ Заявка не найдена", show_alert=True)
            return

        logger.info(f"📋 Заявка #{request_id} до обновления: статус={request_before.status.value}, "
                   f"installer_id={request_before.installer_id}")

        # Атомарно обновляем заявку
        logger.debug("🔄 Выполняем атомарное обновление заявки")
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
            logger.warning(f"⚠️ Заявка #{request_id} не может быть взята - статус изменился")
            
            # Получаем актуальную информацию о заявке
            query = select(Request).where(Request.id == request_id)
            result = await session.execute(query)
            current_request = result.scalar_one_or_none()
            
            if current_request:
                logger.warning(f"Текущий статус заявки: {current_request.status.value}, "
                             f"installer_id: {current_request.installer_id}")
                
                if current_request.installer:
                    taker_name = current_request.installer.first_name or current_request.installer.username
                    await callback.answer(
                        f"❌ Заявка уже взята монтажником {taker_name}",
                        show_alert=True
                    )
                else:
                    await callback.answer(
                        f"❌ Заявка уже {current_request.status.value}",
                        show_alert=True
                    )
            else:
                await callback.answer("❌ Заявка не найдена", show_alert=True)
            
            return

        # УСПЕХ - заявка взята
        logger.info(f"✅ ЗАЯВКА #{request_id} УСПЕШНО ВЗЯТА монтажником {installer.id}")
        logger.info(f"Новый статус: {updated_request.status.value}, taken_at: {updated_request.taken_at}")

        # Уведомляем заказчика
        try:
            logger.debug(f"📱 Отправка уведомления заказчику {updated_request.customer.telegram_id}")
            notification_service = NotificationService(callback.bot, session)
            await notification_service.notify_customer(
                updated_request.customer.telegram_id,
                f"🔨 Заявка #{updated_request.id} взята в работу!\n\n"
                f"Монтажник: {installer.first_name or installer.username}\n"
                f"Скоро с вами свяжутся."
            )
            logger.info("✅ Уведомление заказчику отправлено")
        except Exception as e:
            logger.error(f"❌ Ошибка при уведомлении заказчика: {e}", exc_info=True)

        # Отправляем детали монтажнику
        try:
            logger.debug(f"📱 Отправка деталей заявки монтажнику {installer.telegram_id}")
            await notification_service.send_request_details_to_installer(updated_request, installer)
            logger.info("✅ Детали заявки отправлены монтажнику")
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке деталей монтажнику: {e}", exc_info=True)

        # Обновляем сообщение в группе
        try:
            logger.debug(f"🔍 Поиск сообщения в группе для заявки #{request_id}")
            query = select(GroupMessage).where(GroupMessage.request_id == updated_request.id)
            result = await session.execute(query)
            group_message = result.scalar_one_or_none()

            if group_message:
                logger.info(f"✅ Найдено сообщение в группе: chat_id={group_message.chat_id}, "
                           f"message_id={group_message.message_id}")
                
                try:
                    await notification_service.update_group_message(
                        group_message.chat_id,
                        group_message.message_id,
                        updated_request
                    )
                    logger.info("✅ Сообщение в группе успешно обновлено")
                except Exception as e:
                    logger.error(f"❌ Не удалось обновить сообщение в группе: {e}", exc_info=True)
                    # Пытаемся отправить новое сообщение как запасной вариант
                    await callback.bot.send_message(
                        group_message.chat_id,
                        f"⚠️ Заявка #{updated_request.id} взята монтажником "
                        f"{installer.first_name or installer.username}.\n"
                        f"(не удалось обновить оригинальное сообщение)"
                    )
            else:
                logger.warning(f"⚠️ Не найдена запись GroupMessage для заявки #{request_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка при работе с сообщением в группе: {e}", exc_info=True)

        # Отправляем подтверждение монтажнику
        await callback.answer(
            f"✅ Заявка #{request_id} успешно взята!",
            show_alert=False
        )
        
        logger.info(f"✅ Процесс взятия заявки #{request_id} завершен успешно")

    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА при взятии заявки: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка", show_alert=True)
        if session:
            await session.rollback()

@router.callback_query(F.data.startswith("refuse_"))
async def process_refuse_request(callback: CallbackQuery, state: FSMContext, session: AsyncSession = None):
    """
    Монтажник отказывается от заявки - БЕЗ ФИЛЬТРА ПО ЧАТУ
    """
    try:
        logger.info(f"❌ Получен отказ от заявки: {callback.data} от {callback.from_user.id}")
        
        # Проверяем, что это группа монтажников
        if callback.message.chat.id != GROUP_ID:
            logger.warning(f"⚠️ Попытка отказа от заявки из другого чата: {callback.message.chat.id}")
            await callback.answer("❌ Это действие доступно только в группе монтажников", show_alert=True)
            return
        
        request_id = extract_message_id(callback.data, "refuse_")
        if not request_id:
            await callback.answer("Неверный ID заявки")
            return

        if not session:
            async for db_session in get_db():
                session = db_session
                break

        # Отвечаем на callback сразу
        await callback.answer("⏳ Запрашиваю причину отказа...")

        query = select(Request).where(Request.id == request_id)
        result = await session.execute(query)
        request = result.scalar_one_or_none()

        if not request:
            await callback.answer("Заявка не найдена")
            return

        if request.status != RequestStatus.NEW:
            status_text = {
                RequestStatus.IN_PROGRESS: "уже в работе",
                RequestStatus.COMPLETED: "уже выполнена",
                RequestStatus.CANCELLED: "отменена"
            }.get(request.status, "изменила статус")
            
            await callback.answer(f"❌ Эта заявка {status_text}, отказ невозможен", show_alert=True)
            return

        # Сохраняем ID заявки в состояние и запрашиваем причину
        await state.update_data(refuse_request_id=request_id)
        await state.set_state(RefusalStates.waiting_reason)

        # Отправляем сообщение в ЛС монтажника для ввода причины
        await callback.message.answer(
            "❓ Пожалуйста, укажите причину отказа от заявки:\n"
            "(минимум 5 символов)",
            reply_markup=remove_keyboard
        )

        logger.info(f"📝 Запрошена причина отказа для заявки #{request_id}")

    except Exception as e:
        logger.error(f"Ошибка при запросе причины отказа: {e}", exc_info=True)
        await callback.answer("Ошибка")

@router.message(StateFilter(RefusalStates.waiting_reason))
async def process_refuse_reason(message: Message, state: FSMContext, session: AsyncSession = None):
    """
    Обработка причины отказа и завершение отказа
    """
    try:
        logger.info(f"📝 Получена причина отказа от {message.from_user.id}: {message.text}")
        
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

        await session.commit()
        logger.info(f"✅ Отказ зарегистрирован для заявки #{request_id} от монтажника {installer.id}")

        # Обновляем сообщение в группе
        query = select(GroupMessage).where(GroupMessage.request_id == request.id)
        result = await session.execute(query)
        group_message = result.scalar_one_or_none()

        if group_message:
            try:
                await message.bot.edit_message_text(
                    chat_id=group_message.chat_id,
                    message_id=group_message.message_id,
                    text=f"⚠️ <b>Заявка #{request.id}</b>\n\n"
                         f"Монтажник {installer.first_name or installer.username} отказался от заявки.\n"
                         f"<b>Причина:</b> {message.text}\n\n"
                         f"Заявка снова доступна для других монтажников.",
                    parse_mode="HTML"
                )
                logger.info(f"✅ Сообщение в группе обновлено после отказа")
            except Exception as e:
                logger.error(f"❌ Ошибка при обновлении сообщения после отказа: {e}")

        await message.answer(
            "✅ Отказ зарегистрирован. Заявка осталась в группе для других монтажников.",
            reply_markup=get_installer_main_keyboard()
        )

        await state.clear()

    except Exception as e:
        logger.error(f"❌ Ошибка при отказе от заявки: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка")
        await state.clear()
        await session.rollback()

@router.callback_query(F.data.startswith("complete_"))
async def process_complete_request(callback: CallbackQuery, state: FSMContext, session: AsyncSession = None):
    """
    Завершение заявки монтажником
    """
    try:
        logger.info(f"✅ Завершение заявки: {callback.data} от {callback.from_user.id}")
        
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

        logger.info(f"✅ Заявка #{request_id} завершена монтажником {installer.id}")

        # Уведомляем заказчика
        notification_service = NotificationService(callback.bot, session)
        await notification_service.notify_customer(
            request.customer.telegram_id,
            f"✅ Заявка #{request.id} выполнена!\n\n"
            f"Монтажник {installer.first_name or installer.username} завершил работу."
        )

        # Обновляем сообщение в ЛС монтажника
        await callback.message.edit_reply_markup(reply_markup=None)
        
        # Если есть caption (фото), обновляем его, иначе текст
        if callback.message.caption:
            await callback.message.edit_caption(
                callback.message.caption + "\n\n✅ <b>Заявка завершена!</b>",
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                callback.message.text + "\n\n✅ <b>Заявка завершена!</b>",
                parse_mode="HTML"
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

        await callback.answer("✅ Заявка успешно завершена!")

    except Exception as e:
        logger.error(f"❌ Ошибка при завершении заявки: {e}", exc_info=True)
        await callback.answer("Ошибка при завершении заявки")
        await session.rollback()

async def send_request_details(message: Message, request: Request, installer: User, session: AsyncSession):
    """
    Отправка деталей заявки монтажнику
    """
    try:
        notification_service = NotificationService(message.bot, session)
        await notification_service.send_request_details_to_installer(request, installer)
        logger.info(f"✅ Детали заявки #{request.id} отправлены монтажнику {installer.id}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки деталей заявки: {e}", exc_info=True)
