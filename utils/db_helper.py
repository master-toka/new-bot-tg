from functools import wraps
from typing import Any, Callable
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
        # Проверяем, есть ли уже сессия в kwargs
        if 'session' in kwargs and kwargs['session'] is not None:
            return await func(*args, **kwargs)
        
        # Создаем новую сессию
        async for session in get_db():
            kwargs['session'] = session
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}")
                # Пытаемся ответить на callback, если это он
                for arg in args:
                    if isinstance(arg, CallbackQuery):
                        try:
                            await arg.answer("❌ Произошла ошибка")
                        except:
                            pass
                        break
                # Пробрасываем ошибку дальше
                raise
            finally:
                # Сессия автоматически закроется в get_db
                break
    return wrapper
