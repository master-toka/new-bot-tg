import aiohttp
import logging
from typing import Optional, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import GEOCODER_API_KEY
from models import GeocodeCache

logger = logging.getLogger(__name__)

class GeocoderService:
    """
    Сервис для работы с Яндекс.Геокодером
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.base_url = "https://geocode-maps.yandex.ru/1.x/"
        self.api_key = GEOCODER_API_KEY
    
    async def reverse_geocode(self, lat: float, lon: float) -> Optional[str]:
        """
        Получение адреса по координатам
        """
        if not self.api_key:
            logger.warning("GEOCODER_API_KEY не настроен")
            return None
        
        # Проверяем кэш
        cached = await self._get_from_cache(lat, lon)
        if cached:
            logger.info(f"Адрес найден в кэше: {cached}")
            return cached
        
        try:
            params = {
                "apikey": self.api_key,
                "format": "json",
                "geocode": f"{lon},{lat}",
                "kind": "house",
                "results": 1
            }
            
            async with aiohttp.ClientSession() as aio_session:
                async with aio_session.get(self.base_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        address = self._parse_response(data)
                        
                        if address:
                            # Сохраняем в кэш
                            await self._save_to_cache(lat, lon, address)
                            return address
                    else:
                        logger.error(f"Ошибка геокодера: статус {response.status}")
                        return None
                        
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка сети при геокодировании: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при геокодировании: {e}")
        
        return None
    
    async def geocode(self, address: str) -> Optional[Tuple[float, float]]:
        """
        Получение координат по адресу
        """
        if not self.api_key:
            logger.warning("GEOCODER_API_KEY не настроен")
            return None
        
        try:
            params = {
                "apikey": self.api_key,
                "format": "json",
                "geocode": address,
                "results": 1
            }
            
            async with aiohttp.ClientSession() as aio_session:
                async with aio_session.get(self.base_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        coords = self._parse_coords(data)
                        return coords
                    else:
                        logger.error(f"Ошибка геокодера: статус {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Ошибка при геокодировании адреса: {e}")
            return None
    
    def _parse_response(self, data: Dict[str, Any]) -> Optional[str]:
        """
        Парсинг ответа от геокодера для получения адреса
        """
        try:
            feature_member = data['response']['GeoObjectCollection']['featureMember']
            if feature_member:
                geo_object = feature_member[0]['GeoObject']
                address = geo_object['metaDataProperty']['GeocoderMetaData']['text']
                return address
        except (KeyError, IndexError) as e:
            logger.error(f"Ошибка парсинга ответа геокодера: {e}")
        
        return None
    
    def _parse_coords(self, data: Dict[str, Any]) -> Optional[Tuple[float, float]]:
        """
        Парсинг ответа от геокодера для получения координат
        """
        try:
            feature_member = data['response']['GeoObjectCollection']['featureMember']
            if feature_member:
                geo_object = feature_member[0]['GeoObject']
                pos = geo_object['Point']['pos']
                lon, lat = map(float, pos.split())
                return (lat, lon)
        except (KeyError, IndexError, ValueError) as e:
            logger.error(f"Ошибка парсинга координат: {e}")
        
        return None
    
    async def _get_from_cache(self, lat: float, lon: float) -> Optional[str]:
        """
        Получение адреса из кэша
        """
        try:
            # Округляем координаты для поиска в кэше
            lat_rounded = round(lat, 6)
            lon_rounded = round(lon, 6)
            
            query = select(GeocodeCache).where(
                GeocodeCache.latitude == lat_rounded,
                GeocodeCache.longitude == lon_rounded
            )
            result = await self.session.execute(query)
            cached = result.scalar_one_or_none()
            
            return cached.address if cached else None
            
        except Exception as e:
            logger.error(f"Ошибка при получении из кэша: {e}")
            return None
    
    async def _save_to_cache(self, lat: float, lon: float, address: str):
        """
        Сохранение адреса в кэш
        """
        try:
            # Округляем координаты для сохранения
            lat_rounded = round(lat, 6)
            lon_rounded = round(lon, 6)
            
            cache_entry = GeocodeCache(
                latitude=lat_rounded,
                longitude=lon_rounded,
                address=address
            )
            
            self.session.add(cache_entry)
            await self.session.commit()
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении в кэш: {e}")
            await self.session.rollback()