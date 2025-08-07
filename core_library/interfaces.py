# -*- coding: utf-8 -*-
"""
Интерфейсы и абстрактные базовые классы для проекта TEM-104.
Обеспечивают четкую архитектуру и контракты между компонентами.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Literal
from dataclasses import dataclass
import datetime

# Типы протоколов
ProtocolType = Literal['ARVAS_LEGACY', 'ARVAS_LEGACY_1', 'TESMART', 'ARVAS_M', 'ARVAS_M1']
ConnectionType = Literal['COM', 'TCP']


@dataclass
class TEM104Data:
    """Датакласс для хранения данных со счетчика."""
    time: Optional[datetime.datetime] = None
    energy_Q: Optional[float] = None  # Энергия (Гкал/МВт*ч)
    mass_M1: Optional[float] = None   # Масса (т)
    volume_V1: Optional[float] = None # Объем 1 (м³)
    volume_V2: Optional[float] = None # Объем 2 (м³)
    temp_T1: Optional[float] = None   # Температура 1 (°C)
    temp_T2: Optional[float] = None   # Температура 2 (°C)
    flow_G1: Optional[float] = None   # Расход 1 (м³/ч)
    flow_G2: Optional[float] = None   # Расход 2 (м³/ч)
    operating_time: Optional[int] = None  # Наработка (секунды)
    protocol_type: Optional[ProtocolType] = None
    device_status: str = "UNKNOWN"
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует данные в словарь для обратной совместимости."""
        return {
            'Time': self.time.strftime("%Y-%m-%d %H:%M:%S") if self.time else None,
            'Q': self.energy_Q,
            'M1': self.mass_M1,
            'V1': self.volume_V1,
            'V2': self.volume_V2,
            'T1': self.temp_T1,
            'T2': self.temp_T2,
            'G1': self.flow_G1,
            'G2': self.flow_G2,
            'T_nar': self.operating_time,
            'protocol': self.protocol_type,
            'status': self.device_status
        }
    
    @property
    def operating_hours(self) -> Optional[int]:
        """Возвращает наработку в часах."""
        return int(self.operating_time / 3600) if self.operating_time else None


class TransportInterface(ABC):
    """Абстрактный интерфейс для транспортного уровня."""
    
    @abstractmethod
    def connect(self) -> None:
        """Установить соединение с устройством."""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Закрыть соединение с устройством."""
        pass
    
    @abstractmethod
    def send_and_receive(self, data: bytes, timeout: Optional[float] = None) -> Optional[bytes]:
        """
        Отправить данные и получить ответ.
        
        Args:
            data: Данные для отправки
            timeout: Таймаут ожидания ответа
            
        Returns:
            Полученные данные или None при ошибке
        """
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Проверить состояние соединения."""
        pass


class ProtocolInterface(ABC):
    """Абстрактный интерфейс для протокольного уровня."""
    
    @abstractmethod
    def auto_detect_protocol(self) -> Optional[ProtocolType]:
        """Автоматически определить тип протокола устройства."""
        pass
    
    @abstractmethod
    def read_all_data(self) -> TEM104Data:
        """Прочитать все данные с устройства."""
        pass
    
    @abstractmethod
    def read_time(self) -> Optional[datetime.datetime]:
        """Прочитать текущее время с устройства."""
        pass
    
    @abstractmethod
    def read_totals(self) -> Dict[str, float]:
        """Прочитать накопленные итоги."""
        pass
    
    @abstractmethod
    def read_instantaneous(self) -> Dict[str, float]:
        """Прочитать мгновенные параметры."""
        pass


class DataParserInterface(ABC):
    """Интерфейс для парсеров данных различных протоколов."""
    
    @abstractmethod
    def parse_time(self, payload: bytes) -> Optional[datetime.datetime]:
        """Распарсить время из ответа устройства."""
        pass
    
    @abstractmethod
    def parse_totals(self, payload: bytes) -> Dict[str, float]:
        """Распарсить накопленные итоги."""
        pass
    
    @abstractmethod
    def parse_instantaneous(self, payload: bytes) -> Dict[str, float]:
        """Распарсить мгновенные параметры."""
        pass
