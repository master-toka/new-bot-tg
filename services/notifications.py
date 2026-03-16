from aiogram import Bot
from aiogram.types import Message, InputMediaPhoto
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from typing import List, Optional, Union
import json

from models import Request, User
from keyboards.inline import get_request_action_keyboard, get_installer_request_keyboard

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Сервис для отправки уведомлений
    """
    
    def __init__(self, bot: Bot, session: AsyncSession):
        self.bot = bot
        self.session = session
    
    async def send_request_to_group(self, request: Request, group_id: int):
        """
        Отправка заявки в группу монтажников
        """
        try:
            # Получаем фото заявки
            photos = []
            if request.photos:
                try:
                    photos = json.loads(request.photos)
                except json.JSONDecodeError:
                    logger.error(f"Ошибка парсинга фото для заявки {request.id}")
            
            # Формируем текст сообщения
            text = self._format_request_text(request)
            
            # Отправляем фото и текст
            if photos:
                # Отправляем первое фото с кнопками
                media = InputMediaPhoto(
                    media=photos[0],
                    caption=text
                )
                
                sent_message = await self.bot.send_photo(
                    chat_id=group_id,
                    photo=photos[0],
                    caption=text,
                    reply_markup=get_request_action_keyboard(request.id)
                )
                
                # Отправляем остальные фото
                for photo in photos[1:]:
                    await self.bot.send_photo(
                        chat_id=group_id,
                        photo=photo
                    )
            else:
                # Если фото нет, отправляем только текст
                sent_message = await self.bot.send_message(
                    chat_id=group_id,
                    text=text,
                    reply_markup=get_request_action_keyboard(request.id)
                )
            
            # Если есть координаты, отправляем геолокацию
            if request.latitude and request.longitude:
                await self.bot.send_location(
                    chat_id=group_id,
                    latitude=request.latitude,
                    longitude=request.longitude,
                    reply_to_message_id=sent_message.message_id
                )
            
            logger.info(f"Заявка {request.id} отправлена в группу {group_id}")
            return sent_message
            
        except Exception as e:
            logger.error(f"Ошибка отправки заявки в группу: {e}")
            return None
    
    async def send_request_details_to_installer(self, request: Request, installer: User):
        """
        Отправка деталей заявки монтажнику в ЛС
        """
        try:
            # Получаем фото
            photos = []
            if request.photos:
                try:
                    photos = json.loads(request.photos)
                except json.JSONDecodeError:
                    logger.error(f"Ошибка парсинга фото для заявки {request.id}")
            
            # Формируем текст
            text = self._format_installer_request_text(request)
            
            # Создаем клавиатуру с действиями
            has_coords = request.latitude is not None and request.longitude is not None
            keyboard = get_installer_request_keyboard(request.id, has_coords)
            
            # Отправляем сообщение
            if photos:
                await self.bot.send_photo(
                    chat_id=installer.telegram_id,
                    photo=photos[0],
                    caption=text,
                    reply_markup=keyboard
                )
                
                # Отправляем остальные фото
                for photo in photos[1:]:
                    await self.bot.send_photo(
                        chat_id=installer.telegram_id,
                        photo=photo
                    )
            else:
                await self.bot.send_message(
                    chat_id=installer.telegram_id,
                    text=text,
                    reply_markup=keyboard
                )
            
            logger.info(f"Детали заявки {request.id} отправлены монтажнику {installer.telegram_id}")
            
        except Exception as e:
            logger.error(f"Ошибка отправки деталей заявки монтажнику: {e}")
    
    async def notify_customer(self, customer_id: int, text: str):
        """
        Отправка уведомления заказчику
        """
        try:
            await self.bot.send_message(
                chat_id=customer_id,
                text=text
            )
            logger.info(f"Уведомление отправлено заказчику {customer_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления заказчику: {e}")
    
    async def update_group_message(self, group_id: int, message_id: int, request: Request):
        """
        Обновление сообщения в группе (после взятия/отказа)
        """
        try:
            # Формируем новый текст
            text = self._format_request_text(request)
            
            # Добавляем информацию о монтажнике если заявка взята
            if request.status.value == "in_progress" and request.installer:
                text += f"\n\n👤 Взял: {request.installer.first_name or request.installer.username}"
            
            # Обновляем сообщение, убираем кнопки
            await self.bot.edit_message_text(
                chat_id=group_id,
                message_id=message_id,
                text=text
            )
            
            logger.info(f"Сообщение в группе обновлено для заявки {request.id}")
            
        except Exception as e:
            logger.error(f"Ошибка обновления сообщения в группе: {e}")
    
    def _format_request_text(self, request: Request) -> str:
        """
        Форматирование текста заявки для группы
        """
        text = f"🔨 <b>Заявка #{request.id}</b>\n\n"
        text += f"📝 <b>Описание:</b>\n{request.description}\n\n"
        text += f"📍 <b>Адрес:</b> {request.address}\n"
        text += f"📞 <b>Телефон:</b> {request.phone}\n"
        text += f"🏘 <b>Район:</b> {request.district.name}\n"
        text += f"\n⏰ <b>Создана:</b> {request.created_at.strftime('%d.%m.%Y %H:%M')}"
        
        return text
    
    def _format_installer_request_text(self, request: Request) -> str:
        """
        Форматирование текста заявки для монтажника в ЛС
        """
        text = f"🔨 <b>Заявка #{request.id}</b>\n\n"
        text += f"📝 <b>Описание:</b>\n{request.description}\n\n"
        text += f"📍 <b>Адрес:</b> {request.address}\n"
        text += f"📞 <b>Телефон клиента:</b> {request.phone}\n"
        text += f"🏘 <b>Район:</b> {request.district.name}\n"
        text += f"\n📅 <b>Дата создания:</b> {request.created_at.strftime('%d.%m.%Y %H:%M')}"
        
        return text