import logging
import aiohttp
from config import GEOCODER_API_KEY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def reverse_geocode(lat: float, lon: float) -> str | None:
    """Преобразует координаты в адрес через Яндекс.Геокодер."""
    if not GEOCODER_API_KEY:
        logger.warning("GEOCODER_API_KEY не задан")
        return None
    url = "https://geocode-maps.yandex.ru/1.x/"
    params = {
        "apikey": GEOCODER_API_KEY,
        "geocode": f"{lon},{lat}",
        "format": "json",
        "lang": "ru_RU"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    try:
                        address = data["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]["metaDataProperty"]["GeocoderMetaData"]["text"]
                        return address
                    except (KeyError, IndexError):
                        logger.error("Не удалось распарсить ответ геокодера")
                        return None
                else:
                    logger.error(f"Ошибка геокодера: {resp.status}")
                    return None
    except Exception as e:
        logger.exception(f"Исключение при геокодировании: {e}")
        return None

def format_request_for_group(request, customer_name, district_name):
    """Формирует текст заявки для отправки в группу."""
    text = (
        f"🔨 Новая заявка #{request.id}\n"
        f"Заказчик: {customer_name}\n"
        f"Район: {district_name}\n"
        f"Адрес: {request.address}\n"
        f"Телефон: {request.phone}\n"
        f"Описание: {request.description}\n"
    )
    return text

def format_request_for_installer(request, customer_name, district_name):
    """Формирует детали заявки для монтажника в ЛС."""
    text = (
        f"📌 Заявка #{request.id}\n"
        f"Заказчик: {customer_name}\n"
        f"Район: {district_name}\n"
        f"Адрес: {request.address}\n"
        f"Телефон: {request.phone}\n"
        f"Описание: {request.description}\n"
    )
    return text