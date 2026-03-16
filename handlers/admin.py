from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from sqlalchemy import select
import logging
from datetime import datetime, timedelta

from models import User, District
from keyboards.inline import get_admin_menu_keyboard, get_back_keyboard
from keyboards.reply import get_admin_main_keyboard
from services.statistics import StatisticsService
from utils.init_districts import check_districts, init_districts
from config import ADMIN_ID
from utils.db_helper import with_session

logger = logging.getLogger(__name__)

router = Router()

# Фильтр для администратора
router.message.filter(F.from_user.id == ADMIN_ID)
router.callback_query.filter(F.from_user.id == ADMIN_ID)

@router.message(Command("admin"))
@router.message(F.text == "👑 Админ панель")
async def cmd_admin(message: Message):
    """
    Открытие админ-панели
    """
    await message.answer(
        "👑 <b>Панель администратора</b>\n\n"
        "Выберите раздел статистики:",
        reply_markup=get_admin_menu_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("admin_stats_"))
@with_session
async def process_admin_stats(callback: CallbackQuery, session):
    """
    Обработка запросов статистики
    """
    try:
        stats_type = callback.data.replace("admin_stats_", "")
        stats_service = StatisticsService(session)
        
        if stats_type == "general":
            await show_general_stats(callback, stats_service)
        elif stats_type == "districts":
            await show_district_stats(callback, stats_service)
        elif stats_type == "installers":
            await show_installer_stats(callback, stats_service)
        elif stats_type == "period":
            await show_period_stats(callback, stats_service)
        elif stats_type == "refusals":
            await show_refusal_stats(callback, stats_service)
            
    except Exception as e:
        logger.error(f"Ошибка в админ-панели: {e}")
        await callback.answer("Ошибка при получении статистики")

@router.callback_query(F.data == "admin_check_districts")
@with_session
async def admin_check_districts(callback: CallbackQuery, session):
    """
    Проверка районов в БД
    """
    try:
        result = await check_districts(session)
        
        text = "🏘 <b>Проверка районов</b>\n\n"
        text += f"Всего в БД: {result['count']}\n\n"
        
        if result['districts']:
            text += "📋 <b>Существующие районы:</b>\n"
            for d in result['districts']:
                text += f"• {d['name']} (ID: {d['id']})\n"
        
        if result['missing']:
            text += f"\n⚠️ <b>Отсутствуют ({len(result['missing'])}):</b>\n"
            for d in result['missing']:
                text += f"• {d}\n"
            
            text += "\nДля добавления используйте /init_districts"
        else:
            text += "\n✅ Все районы присутствуют в БД!"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при проверке районов: {e}")
        await callback.answer("❌ Ошибка")

@router.message(Command("init_districts"))
@with_session
async def cmd_init_districts(message: Message, session):
    """
    Принудительная инициализация районов
    """
    try:
        await init_districts(session)
        await message.answer("✅ Районы успешно инициализированы!")
    except Exception as e:
        logger.error(f"Ошибка при инициализации районов: {e}")
        await message.answer(f"❌ Ошибка: {e}")

@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    """
    Возврат в главное меню админки
    """
    await callback.message.edit_text(
        "👑 <b>Панель администратора</b>\n\n"
        "Выберите раздел статистики:",
        reply_markup=get_admin_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

async def show_general_stats(callback: CallbackQuery, stats_service: StatisticsService):
    """
    Показ общей статистики
    """
    stats = await stats_service.get_general_stats()
    
    if not stats:
        await callback.message.edit_text(
            "❌ Не удалось получить статистику",
            reply_markup=get_back_keyboard()
        )
        return
    
    text = "📊 <b>Общая статистика</b>\n\n"
    
    text += "<b>👥 Пользователи:</b>\n"
    text += f"• Всего: {stats['users']['total']}\n"
    text += f"• Заказчики: {stats['users']['customers']}\n"
    text += f"• Монтажники: {stats['users']['installers']}\n\n"
    
    text += "<b>📋 Заявки:</b>\n"
    text += f"• Новые: {stats['requests'].get('new', 0)}\n"
    text += f"• В работе: {stats['requests'].get('in_progress', 0)}\n"
    text += f"• Выполнено: {stats['requests'].get('completed', 0)}\n"
    text += f"• Отменено: {stats['requests'].get('cancelled', 0)}\n\n"
    
    text += f"<b>❌ Отказы:</b> {stats['refusals']}\n\n"
    
    if stats['avg_completion_hours']:
        text += f"<b>⏱ Среднее время выполнения:</b>\n"
        text += f"• {stats['avg_completion_hours']} часов\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

async def show_district_stats(callback: CallbackQuery, stats_service: StatisticsService):
    """
    Показ статистики по районам
    """
    stats = await stats_service.get_district_stats()
    
    if not stats:
        await callback.message.edit_text(
            "❌ Не удалось получить статистику по районам",
            reply_markup=get_back_keyboard()
        )
        return
    
    text = "📍 <b>Статистика по районам</b>\n\n"
    
    for item in stats:
        text += f"<b>{item['district']}:</b>\n"
        text += f"• Всего заявок: {item['total']}\n"
        text += f"• Выполнено: {item['completed']}\n"
        text += f"• В работе: {item['active']}\n"
        text += f"• Выполняемость: {item['completion_rate']}%\n"
        text += "➖➖➖➖➖➖➖\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

async def show_installer_stats(callback: CallbackQuery, stats_service: StatisticsService):
    """
    Показ статистики по монтажникам
    """
    stats = await stats_service.get_installer_stats()
    
    if not stats:
        await callback.message.edit_text(
            "❌ Не удалось получить статистику по монтажникам",
            reply_markup=get_back_keyboard()
        )
        return
    
    text = "👥 <b>Рейтинг монтажников</b>\n\n"
    
    for i, item in enumerate(stats[:10], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} <b>{item['name']}</b>\n"
        text += f"• Выполнено: {item['completed']}\n"
        text += f"• В работе: {item['in_progress']}\n"
        text += f"• Отказы: {item['refusals']}\n"
        text += "➖➖➖➖➖➖➖\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

async def show_period_stats(callback: CallbackQuery, stats_service: StatisticsService):
    """
    Показ статистики за период (последние 30 дней)
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    stats = await stats_service.get_period_stats(start_date, end_date)
    
    if not stats:
        await callback.message.edit_text(
            "❌ Не удалось получить статистику за период",
            reply_markup=get_back_keyboard()
        )
        return
    
    text = "📅 <b>Статистика за последние 30 дней</b>\n\n"
    text += f"• Новых заявок: {stats['new_requests']}\n"
    text += f"• Выполнено: {stats['completed_requests']}\n"
    text += f"• В работе: {stats['in_progress']}\n"
    text += f"• Выполняемость: {stats['completion_rate']}%\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

async def show_refusal_stats(callback: CallbackQuery, stats_service: StatisticsService):
    """
    Показ статистики отказов
    """
    stats = await stats_service.get_refusal_stats()
    
    if not stats:
        await callback.message.edit_text(
            "📊 Нет отказов за последние 30 дней",
            reply_markup=get_back_keyboard()
        )
        return
    
    text = "❌ <b>Отказы за последние 30 дней</b>\n\n"
    
    for item in stats[:10]:
        text += f"<b>Заявка #{item['request_id']}</b>\n"
        text += f"Монтажник: {item['installer_name']}\n"
        text += f"Причина: {item['reason'][:50]}{'...' if len(item['reason']) > 50 else ''}\n"
        text += f"Дата: {item['date']}\n"
        text += "➖➖➖➖➖➖➖\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()
