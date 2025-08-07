# -*- coding: utf-8 -*-
"""
Парсеры данных для различных протоколов TEM-104.
Устраняет дублирование кода и обеспечивает единообразную обработку.
"""

import struct
import datetime
from typing import Optional, Dict, Any, Tuple
from .interfaces import DataParserInterface, ProtocolType, TEM104Data
import logging

logger = logging.getLogger(__name__)


def bcd_to_int(bcd_byte: int) -> int:
    """
    Преобразует один байт BCD в integer.
    
    Args:
        bcd_byte: Байт в BCD формате
        
    Returns:
        Целое число
    """
    return (bcd_byte >> 4) * 10 + (bcd_byte & 0x0F)


def safe_unpack_float(payload: bytes, offset: int, default: float = 0.0) -> float:
    """
    Безопасно извлекает float из payload по смещению.
    
    Args:
        payload: Байтовые данные
        offset: Смещение в байтах
        default: Значение по умолчанию при ошибке
        
    Returns:
        Значение float или default при ошибке
    """
    try:
        if payload and len(payload) >= offset + 4:
            return struct.unpack('>f', payload[offset:offset+4])[0]
    except struct.error as e:
        logger.debug(f"Ошибка распаковки float по смещению {offset}: {e}")
    return default


def safe_unpack_long(payload: bytes, offset: int, default: int = 0) -> int:
    """
    Безопасно извлекает unsigned long из payload по смещению.
    
    Args:
        payload: Байтовые данные
        offset: Смещение в байтах
        default: Значение по умолчанию при ошибке
        
    Returns:
        Значение long или default при ошибке
    """
    try:
        if payload and len(payload) >= offset + 4:
            return struct.unpack('>L', payload[offset:offset+4])[0]
    except struct.error as e:
        logger.debug(f"Ошибка распаковки long по смещению {offset}: {e}")
    return default


class BaseParser(DataParserInterface):
    """Базовый класс для всех парсеров протоколов."""
    
    def __init__(self, protocol_type: ProtocolType):
        """
        Инициализация парсера.
        
        Args:
            protocol_type: Тип протокола
        """
        self.protocol_type = protocol_type
        logger.debug(f"Инициализирован парсер для протокола {protocol_type}")
    
    def parse_combined_value(
        self, 
        payload: bytes, 
        int_offset: int, 
        float_offset: int
    ) -> float:
        """
        Парсит комбинированное значение (целая + дробная часть).
        
        Args:
            payload: Данные
            int_offset: Смещение целой части
            float_offset: Смещение дробной части
            
        Returns:
            Комбинированное значение
        """
        integer_part = safe_unpack_long(payload, int_offset)
        float_part = safe_unpack_float(payload, float_offset)
        return float(integer_part + float_part)
    
    def parse_time(self, payload: bytes) -> Optional[datetime.datetime]:
        """Базовая реализация парсинга времени."""
        return None
    
    def parse_totals(self, payload: bytes) -> Dict[str, float]:
        """Базовая реализация парсинга итогов."""
        return {}
    
    def parse_instantaneous(self, payload: bytes) -> Dict[str, float]:
        """Базовая реализация парсинга мгновенных параметров."""
        return {}


class ArvasM1Parser(BaseParser):
    """Парсер для протокола ARVAS_M1."""
    
    def __init__(self):
        super().__init__('ARVAS_M1')
    
    def parse_time(self, payload: bytes) -> Optional[datetime.datetime]:
        """Парсит время в десятичном формате."""
        if payload and len(payload) >= 6:
            try:
                ss, mm, hh, dd, MM, YY = payload[:6]
                return datetime.datetime(2000 + YY, MM, dd, hh, mm, ss)
            except (ValueError, IndexError) as e:
                logger.warning(f"Ошибка парсинга времени ARVAS_M1: {e}")
        return None
    
    def parse_totals(self, payload: bytes) -> Dict[str, float]:
        """Парсит накопленные итоги для ARVAS_M1."""
        result = {}
        try:
            result['Q'] = self.parse_combined_value(payload, 0x10, 0x20)
            result['M1'] = self.parse_combined_value(payload, 0x0C, 0x1C)
            result['V1'] = self.parse_combined_value(payload, 0x08, 0x18)
            result['T_nar'] = safe_unpack_long(payload, 0x30)
        except Exception as e:
            logger.error(f"Ошибка парсинга итогов ARVAS_M1: {e}")
        return result
    
    def parse_instantaneous(self, payload: bytes) -> Dict[str, float]:
        """Парсит мгновенные параметры для ARVAS_M1."""
        result = {}
        try:
            result['T1'] = safe_unpack_float(payload, 0x00)
            result['T2'] = safe_unpack_float(payload, 0x04)
            result['G1'] = safe_unpack_float(payload, 0x20)
            result['G2'] = safe_unpack_float(payload, 0x24)
        except Exception as e:
            logger.error(f"Ошибка парсинга мгновенных ARVAS_M1: {e}")
        return result


class ArvasMParser(BaseParser):
    """Парсер для протокола ARVAS_M."""
    
    def __init__(self):
        super().__init__('ARVAS_M')
    
    def parse_time(self, payload: bytes) -> Optional[datetime.datetime]:
        """Парсит время в десятичном формате."""
        if payload and len(payload) >= 6:
            try:
                ss, mm, hh, dd, MM, YY = payload[:6]
                return datetime.datetime(2000 + YY, MM, dd, hh, mm, ss)
            except (ValueError, IndexError) as e:
                logger.warning(f"Ошибка парсинга времени ARVAS_M: {e}")
        return None
    
    def parse_totals(self, payload: bytes) -> Dict[str, float]:
        """Парсит накопленные итоги для ARVAS_M."""
        result = {}
        try:
            result['Q'] = self.parse_combined_value(payload, 0x28, 0x68)
            result['M1'] = self.parse_combined_value(payload, 0x18, 0x58)
            result['V1'] = self.parse_combined_value(payload, 0x08, 0x48)
            result['V2'] = self.parse_combined_value(payload, 0x0C, 0x4C)
            result['T_nar'] = safe_unpack_long(payload, 0xA0)
        except Exception as e:
            logger.error(f"Ошибка парсинга итогов ARVAS_M: {e}")
        return result
    
    def parse_instantaneous(self, payload: bytes) -> Dict[str, float]:
        """Парсит мгновенные параметры для ARVAS_M."""
        result = {}
        try:
            result['T1'] = safe_unpack_float(payload, 0x00)
            result['T2'] = safe_unpack_float(payload, 0x04)
            result['G1'] = safe_unpack_float(payload, 0x40)
            result['G2'] = safe_unpack_float(payload, 0x44)
        except Exception as e:
            logger.error(f"Ошибка парсинга мгновенных ARVAS_M: {e}")
        return result


class ArvasLegacy1Parser(BaseParser):
    """Парсер для протокола ARVAS_LEGACY_1."""
    
    def __init__(self):
        super().__init__('ARVAS_LEGACY_1')
    
    def parse_time(self, payload: bytes) -> Optional[datetime.datetime]:
        """Парсит время в BCD формате."""
        if payload and len(payload) >= 7:
            try:
                ss = bcd_to_int(payload[0])
                mm = bcd_to_int(payload[1])
                hh = bcd_to_int(payload[2])
                dd = bcd_to_int(payload[4])
                MM = bcd_to_int(payload[5])
                YY = bcd_to_int(payload[6])
                return datetime.datetime(2000 + YY, MM, dd, hh, mm, ss)
            except (ValueError, IndexError) as e:
                logger.warning(f"Ошибка парсинга времени ARVAS_LEGACY_1: {e}")
        return None
    
    def parse_totals(self, payload: bytes) -> Dict[str, float]:
        """Парсит накопленные итоги для ARVAS_LEGACY_1."""
        result = {}
        try:
            result['Q'] = self.parse_combined_value(payload, 0x54, 0x58)
            result['M1'] = self.parse_combined_value(payload, 0x4C, 0x50)
            result['V1'] = self.parse_combined_value(payload, 0x44, 0x48)
            result['T_nar'] = safe_unpack_long(payload, 0x60)
        except Exception as e:
            logger.error(f"Ошибка парсинга итогов ARVAS_LEGACY_1: {e}")
        return result
    
    def parse_instantaneous(self, payload: bytes) -> Dict[str, float]:
        """Парсит мгновенные параметры для ARVAS_LEGACY_1."""
        result = {}
        try:
            result['T1'] = safe_unpack_float(payload, 0x08)
            result['T2'] = safe_unpack_float(payload, 0x0C)
            result['G1'] = safe_unpack_float(payload, 0x00)
        except Exception as e:
            logger.error(f"Ошибка парсинга мгновенных ARVAS_LEGACY_1: {e}")
        return result


class ArvasLegacyParser(BaseParser):
    """Парсер для протокола ARVAS_LEGACY."""
    
    def __init__(self):
        super().__init__('ARVAS_LEGACY')
    
    def parse_time(self, payload: bytes) -> Optional[datetime.datetime]:
        """Парсит время в BCD формате."""
        if payload and len(payload) >= 10:
            try:
                ss = bcd_to_int(payload[0])
                mm = bcd_to_int(payload[2])
                hh = bcd_to_int(payload[4])
                dd = bcd_to_int(payload[7])
                MM = bcd_to_int(payload[8])
                YY = bcd_to_int(payload[9])
                return datetime.datetime(2000 + YY, MM, dd, hh, mm, ss)
            except (ValueError, IndexError) as e:
                logger.warning(f"Ошибка парсинга времени ARVAS_LEGACY: {e}")
        return None
    
    def parse_totals(self, payload: bytes) -> Dict[str, float]:
        """Парсит накопленные итоги для ARVAS_LEGACY."""
        result = {}
        try:
            result['Q'] = self.parse_combined_value(payload, 0x58, 0x28)
            result['M1'] = self.parse_combined_value(payload, 0x48, 0x18)
            result['V1'] = self.parse_combined_value(payload, 0x38, 0x08)
            result['V2'] = self.parse_combined_value(payload, 0x3C, 0x0C)
            result['T_nar'] = safe_unpack_long(payload, 0x6C)
        except Exception as e:
            logger.error(f"Ошибка парсинга итогов ARVAS_LEGACY: {e}")
        return result
    
    def parse_instantaneous(self, payload: bytes) -> Dict[str, float]:
        """Парсит мгновенные параметры для ARVAS_LEGACY."""
        result = {}
        try:
            result['T1'] = safe_unpack_float(payload, 0x00)
            result['T2'] = safe_unpack_float(payload, 0x04)
            result['G1'] = safe_unpack_float(payload, 0x40)
            result['G2'] = safe_unpack_float(payload, 0x44)
        except Exception as e:
            logger.error(f"Ошибка парсинга мгновенных ARVAS_LEGACY: {e}")
        return result


class TesmartParser(BaseParser):
    """Парсер для протокола TESMART."""
    
    def __init__(self):
        super().__init__('TESMART')
    
    @staticmethod
    def get_tesmart_coeff(comma_val: int, param_type: str) -> int:
        """
        Получает коэффициент для TESMART.
        
        Args:
            comma_val: Значение запятой
            param_type: Тип параметра ('energy' или 'volume')
            
        Returns:
            Коэффициент
        """
        coeffs = {
            'energy': {6: 100000, 5: 10000, 4: 1000, 3: 100, 2: 10},
            'volume': {5: 1000, 4: 100, 3: 10}
        }
        return coeffs.get(param_type, {}).get(comma_val, 1)
    
    def parse_time(self, payload: bytes) -> Optional[datetime.datetime]:
        """Парсит время из общего блока TESMART."""
        if payload and len(payload) >= 0x488:
            try:
                ss = bcd_to_int(payload[0x482])
                mm = bcd_to_int(payload[0x483])
                hh = bcd_to_int(payload[0x484])
                dd = bcd_to_int(payload[0x485])
                MM = bcd_to_int(payload[0x486])
                YY = bcd_to_int(payload[0x487])
                return datetime.datetime(2000 + YY, MM, dd, hh, mm, ss)
            except (ValueError, IndexError) as e:
                logger.warning(f"Ошибка парсинга времени TESMART: {e}")
        return None
    
    def parse_full_data(self, full_payload: bytes) -> TEM104Data:
        """
        Парсит полные данные TESMART из объединенного payload.
        
        Args:
            full_payload: Полный payload (5 блоков по 256 байт)
            
        Returns:
            Объект TEM104Data с распарсенными данными
        """
        data = TEM104Data(protocol_type='TESMART')
        
        try:
            # Время
            data.time = self.parse_time(full_payload)
            
            # Коэффициенты
            k_v1 = self.get_tesmart_coeff(full_payload[0x02FA], 'volume')
            k_v2 = self.get_tesmart_coeff(full_payload[0x02FB], 'volume')
            k_q1 = self.get_tesmart_coeff(full_payload[0x02FA], 'energy')
            
            # Накопленные итоги
            data.energy_Q = self.parse_combined_value(full_payload, 0x0378, 0x0360) / k_q1
            data.mass_M1 = self.parse_combined_value(full_payload, 0x0348, 0x0330) / k_v1
            data.volume_V1 = self.parse_combined_value(full_payload, 0x0318, 0x0300) / k_v1
            data.volume_V2 = self.parse_combined_value(full_payload, 0x031C, 0x0304) / k_v2
            data.operating_time = safe_unpack_long(full_payload, 0x0404)
            
            # Мгновенные параметры
            data.temp_T1 = safe_unpack_float(full_payload, 0x0200)
            data.temp_T2 = safe_unpack_float(full_payload, 0x0204)
            data.flow_G1 = safe_unpack_float(full_payload, 0x0288)
            data.flow_G2 = safe_unpack_float(full_payload, 0x028C)
            
            data.device_status = "OK"
            
        except Exception as e:
            logger.error(f"Ошибка парсинга данных TESMART: {e}")
            data.device_status = "PARSE_ERROR"
        
        return data


class ParserFactory:
    """Фабрика для создания парсеров."""
    
    _parsers = {
        'ARVAS_M1': ArvasM1Parser,
        'ARVAS_M': ArvasMParser,
        'ARVAS_LEGACY_1': ArvasLegacy1Parser,
        'ARVAS_LEGACY': ArvasLegacyParser,
        'TESMART': TesmartParser
    }
    
    @classmethod
    def create_parser(cls, protocol_type: ProtocolType) -> DataParserInterface:
        """
        Создает парсер для указанного протокола.
        
        Args:
            protocol_type: Тип протокола
            
        Returns:
            Экземпляр парсера
            
        Raises:
            ValueError: Если протокол не поддерживается
        """
        if protocol_type not in cls._parsers:
            raise ValueError(f"Неподдерживаемый протокол: {protocol_type}")
        
        parser_class = cls._parsers[protocol_type]
        return parser_class()
    
    @classmethod
    def register_parser(
        cls, 
        protocol_type: str, 
        parser_class: type
    ) -> None:
        """
        Регистрирует новый парсер.
        
        Args:
            protocol_type: Тип протокола
            parser_class: Класс парсера
        """
        cls._parsers[protocol_type] = parser_class
        logger.info(f"Зарегистрирован парсер для протокола {protocol_type}")
