# -*- coding: utf-8 -*-
"""
Основная библиотека TEM-104.
Предоставляет удобный интерфейс для работы со счетчиками ТЭМ-104.

Использование:
    from core_library import TEM104ClientFactory, setup_logging
    
    # Настройка логирования
    setup_logging(log_level="INFO")
    
    # Создание клиента
    client = TEM104ClientFactory.create_client(
        connection_type="COM",
        port="COM3",
        baudrate=9600,
        address=1
    )
    
    # Опрос устройства
    client.connect()
    data = client.read_all_data()
    client.disconnect()
"""

__version__ = "2.0.0"
__author__ = "TEM-104 Development Team"
__license__ = "MIT"

# Импорт основных классов и функций
from .test104 import (
    TEM104_Base_Client,
    TEM104_Serial_Client,
    TEM104_TCP_Client
)

from .factory import (
    TEM104ClientFactory,
    ConnectionPoolManager
)

from .interfaces import (
    TEM104Data,
    ProtocolType,
    ConnectionType,
    TransportInterface,
    ProtocolInterface,
    DataParserInterface
)

from .parsers import (
    ParserFactory,
    ArvasM1Parser,
    ArvasMParser,
    ArvasLegacy1Parser,
    ArvasLegacyParser,
    TesmartParser,
    bcd_to_int,
    safe_unpack_float,
    safe_unpack_long
)

from .logging_config import (
    setup_logging,
    get_logger,
    LogContext,
    PerformanceLogger,
    ColoredFormatter
)

# Экспортируемые имена
__all__ = [
    # Версия
    '__version__',
    
    # Основные клиенты
    'TEM104_Base_Client',
    'TEM104_Serial_Client', 
    'TEM104_TCP_Client',
    
    # Фабрики
    'TEM104ClientFactory',
    'ConnectionPoolManager',
    'ParserFactory',
    
    # Интерфейсы и типы
    'TEM104Data',
    'ProtocolType',
    'ConnectionType',
    'TransportInterface',
    'ProtocolInterface',
    'DataParserInterface',
    
    # Парсеры
    'ArvasM1Parser',
    'ArvasMParser',
    'ArvasLegacy1Parser',
    'ArvasLegacyParser',
    'TesmartParser',
    
    # Утилиты
    'bcd_to_int',
    'safe_unpack_float',
    'safe_unpack_long',
    
    # Логирование
    'setup_logging',
    'get_logger',
    'LogContext',
    'PerformanceLogger',
    'ColoredFormatter'
]

# Инициализация логирования при импорте (опционально)
import logging
if not logging.getLogger().handlers:
    from .logging_config import setup_logging
    setup_logging(log_level="INFO", console_output=True, file_output=False)
