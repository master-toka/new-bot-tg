from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging

from models import User, Request, District, Refusal, RequestStatus, UserRole

logger = logging.getLogger(__name__)

class StatisticsService:
    """
    Сервис для сбора статистики
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_general_stats(self) -> Dict[str, Any]:
        """
        Получение общей статистики
        """
        try:
            customers_count = await self._count_users(UserRole.CUSTOMER)
            installers_count = await self._count_users(UserRole.INSTALLER)
            requests_stats = await self._count_requests_by_status()
            refusals_count = await self._count_refusals()
            avg_completion_time = await self._get_avg_completion_time()
            
            return {
                "users": {
                    "total": customers_count + installers_count,
                    "customers": customers_count,
                    "installers": installers_count
                },
                "requests": requests_stats,
                "refusals": refusals_count,
                "avg_completion_hours": avg_completion_time
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении общей статистики: {e}")
            return {}
    
    async def get_district_stats(self) -> List[Dict[str, Any]]:
        """
        Статистика по районам
        """
        try:
            districts = await self.session.execute(
                select(District).where(District.is_active == True)
            )
            districts = districts.scalars().all()
            
            result = []
            for district in districts:
                total_requests = await self._count_requests_by_district(district.id)
                completed_requests = await self._count_requests_by_district(
                    district.id, RequestStatus.COMPLETED
                )
                active_requests = await self._count_requests_by_district(
                    district.id, RequestStatus.IN_PROGRESS
                )
                
                result.append({
                    "district": district.name,
                    "total": total_requests,
                    "completed": completed_requests,
                    "active": active_requests,
                    "completion_rate": round(
                        (completed_requests / total_requests * 100) if total_requests > 0 else 0,
                        1
                    )
                })
            
            return sorted(result, key=lambda x: x["total"], reverse=True)
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики по районам: {e}")
            return []
    
    async def get_installer_stats(self) -> List[Dict[str, Any]]:
        """
        Статистика по монтажникам
        """
        try:
            installers = await self.session.execute(
                select(User).where(User.role == UserRole.INSTALLER)
            )
            installers = installers.scalars().all()
            
            result = []
            for installer in installers:
                completed = await self._count_installer_requests(
                    installer.id, RequestStatus.COMPLETED
                )
                in_progress = await self._count_installer_requests(
                    installer.id, RequestStatus.IN_PROGRESS
                )
                refusals = await self._count_installer_refusals(installer.id)
                
                result.append({
                    "installer_id": installer.id,
                    "name": installer.first_name or installer.username or f"ID {installer.telegram_id}",
                    "completed": completed,
                    "in_progress": in_progress,
                    "refusals": refusals,
                    "total_taken": completed + in_progress + refusals
                })
            
            return sorted(result, key=lambda x: x["completed"], reverse=True)
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики по монтажникам: {e}")
            return []
    
    async def get_installer_personal_stats(self, installer_id: int) -> Dict[str, Any]:
        """
        Личная статистика монтажника
        """
        try:
            completed = await self._count_installer_requests(installer_id, RequestStatus.COMPLETED)
            in_progress = await self._count_installer_requests(installer_id, RequestStatus.IN_PROGRESS)
            refusals = await self._count_installer_refusals(installer_id)
            
            # За последние 30 дней
            month_ago = datetime.now() - timedelta(days=30)
            query = select(Request).where(
                and_(
                    Request.installer_id == installer_id,
                    Request.status == RequestStatus.COMPLETED,
                    Request.completed_at >= month_ago
                )
            )
            result = await self.session.execute(query)
            month_completed = len(result.scalars().all())
            
            return {
                "completed": completed,
                "in_progress": in_progress,
                "refusals": refusals,
                "month_completed": month_completed
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении личной статистики: {e}")
            return {}
    
    async def get_refusal_stats(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Статистика отказов за последние N дней
        """
        try:
            since_date = datetime.now() - timedelta(days=days)
            
            query = select(Refusal).where(Refusal.created_at >= since_date).order_by(Refusal.created_at.desc())
            refusals = await self.session.execute(query)
            refusals = refusals.scalars().all()
            
            result = []
            for refusal in refusals[:20]:  # Показываем последние 20
                result.append({
                    "id": refusal.id,
                    "request_id": refusal.request_id,
                    "installer_name": refusal.installer.first_name or refusal.installer.username or "Неизвестно",
                    "reason": refusal.reason,
                    "date": refusal.created_at.strftime("%d.%m.%Y %H:%M")
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики отказов: {e}")
            return []
    
    async def get_period_stats(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """
        Статистика за определенный период
        """
        try:
            new_requests = await self._count_requests_by_period(start_date, end_date)
            completed_requests = await self._count_requests_by_period(
                start_date, end_date, RequestStatus.COMPLETED
            )
            in_progress = await self._count_requests_by_status_in_period(
                RequestStatus.IN_PROGRESS, start_date, end_date
            )
            
            return {
                "period": f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}",
                "new_requests": new_requests,
                "completed_requests": completed_requests,
                "in_progress": in_progress,
                "completion_rate": round(
                    (completed_requests / new_requests * 100) if new_requests > 0 else 0,
                    1
                )
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики за период: {e}")
            return {}
    
    # Вспомогательные методы
    async def _count_users(self, role: UserRole) -> int:
        query = select(func.count()).select_from(User).where(User.role == role)
        result = await self.session.execute(query)
        return result.scalar() or 0
    
    async def _count_requests_by_status(self) -> Dict[str, int]:
        stats = {}
        for status in RequestStatus:
            query = select(func.count()).select_from(Request).where(Request.status == status)
            result = await self.session.execute(query)
            stats[status.value] = result.scalar() or 0
        return stats
    
    async def _count_requests_by_status_in_period(self, status: RequestStatus, start: datetime, end: datetime) -> int:
        query = select(func.count()).select_from(Request).where(
            and_(
                Request.status == status,
                Request.created_at.between(start, end)
            )
        )
        result = await self.session.execute(query)
        return result.scalar() or 0
    
    async def _count_refusals(self) -> int:
        query = select(func.count()).select_from(Refusal)
        result = await self.session.execute(query)
        return result.scalar() or 0
    
    async def _get_avg_completion_time(self) -> Optional[float]:
        query = select(
            func.avg(
                func.extract('epoch', Request.completed_at - Request.taken_at) / 3600
            )
        ).where(
            Request.status == RequestStatus.COMPLETED,
            Request.taken_at.isnot(None),
            Request.completed_at.isnot(None)
        )
        result = await self.session.execute(query)
        avg_time = result.scalar()
        return round(avg_time, 1) if avg_time else None
    
    async def _count_requests_by_district(self, district_id: int, status: Optional[RequestStatus] = None) -> int:
        query = select(func.count()).select_from(Request).where(
            Request.district_id == district_id
        )
        if status:
            query = query.where(Request.status == status)
        result = await self.session.execute(query)
        return result.scalar() or 0
    
    async def _count_installer_requests(self, installer_id: int, status: RequestStatus) -> int:
        query = select(func.count()).select_from(Request).where(
            Request.installer_id == installer_id,
            Request.status == status
        )
        result = await self.session.execute(query)
        return result.scalar() or 0
    
    async def _count_installer_refusals(self, installer_id: int) -> int:
        query = select(func.count()).select_from(Refusal).where(
            Refusal.installer_id == installer_id
        )
        result = await self.session.execute(query)
        return result.scalar() or 0
    
    async def _count_requests_by_period(self, start_date: datetime, end_date: datetime, status: Optional[RequestStatus] = None) -> int:
        query = select(func.count()).select_from(Request).where(
            Request.created_at.between(start_date, end_date)
        )
        if status:
            query = query.where(Request.status == status)
        result = await self.session.execute(query)
        return result.scalar() or 0
