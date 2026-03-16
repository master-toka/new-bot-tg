from functools import wraps
from typing import Optional, Any, Callable
import logging
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db

logger = logging.getLogger(__name__)

def with_session(func: Callable) -> Callable:
    """
    Декоратор для автоматического управления сессией БД
    """
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Пропускаем, если сессия уже передана
        if 'session' in kwargs:
            return await func(*args, **kwargs)
        
        # Получаем сессию
        async for session in get_db():
            kwargs['session'] = session
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}")
                # Если это callback, отвечаем на него
                for arg in args:
                    if isinstance(arg, CallbackQuery):
                        await arg.answer("❌ Произошла ошибка")
                        break
                raise
            finally:
                break  # Важно: выходим из генератора
    return wrapper
