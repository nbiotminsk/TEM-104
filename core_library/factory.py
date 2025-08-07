# -*- coding: utf-8 -*-
"""
Фабрика для создания клиентов TEM-104.
Упрощает создание клиентов и обеспечивает единую точку входа.
"""

from typing import Dict, Any, Optional, Type
from .interfaces import ConnectionType, ProtocolType
from .test104 import TEM104_Serial_Client, TEM104_TCP_Client, TEM104_Base_Client
import logging

logger = logging.getLogger(__name__)


class TEM104ClientFactory:
    """
    Фабрика для создания клиентов TEM-104.
    
    Использование:
        client = TEM104ClientFactory.create_client(
            connection_type="COM",
            port="COM3",
            baudrate=9600,
            address=1
        )
    """
    
    # Реестр типов клиентов
    _client_types: Dict[ConnectionType, Type[TEM104_Base_Client]] = {
        "COM": TEM104_Serial_Client,
        "TCP": TEM104_TCP_Client
    }
    
    @classmethod
    def create_client(
        cls,
        connection_type: ConnectionType,
        address: int = 1,
        protocol: Optional[ProtocolType] = None,
        **kwargs
    ) -> TEM104_Base_Client:
        """
        Создает клиент для работы со счетчиком TEM-104.
        
        Args:
            connection_type: Тип подключения ("COM" или "TCP")
            address: Сетевой адрес счетчика (по умолчанию 1)
            protocol: Тип протокола (опционально, определяется автоматически)
            **kwargs: Дополнительные параметры для конкретного типа клиента
                Для COM: port, baudrate, timeout
                Для TCP: host, port, timeout
        
        Returns:
            Экземпляр клиента TEM104
            
        Raises:
            ValueError: Если указан неподдерживаемый тип подключения
            TypeError: Если не переданы обязательные параметры
        
        Examples:
            >>> # Создание COM клиента
            >>> client = TEM104ClientFactory.create_client(
            ...     connection_type="COM",
            ...     port="COM3",
            ...     baudrate=9600,
            ...     address=1
            ... )
            
            >>> # Создание TCP клиента
            >>> client = TEM104ClientFactory.create_client(
            ...     connection_type="TCP",
            ...     host="192.168.1.100",
            ...     port=5009,
            ...     address=1
            ... )
        """
        if connection_type not in cls._client_types:
            raise ValueError(
                f"Неподдерживаемый тип подключения: {connection_type}. "
                f"Доступные типы: {list(cls._client_types.keys())}"
            )
        
        client_class = cls._client_types[connection_type]
        
        # Валидация обязательных параметров
        if connection_type == "COM":
            if "port" not in kwargs:
                raise TypeError("Для COM подключения необходим параметр 'port'")
            if "baudrate" not in kwargs:
                kwargs["baudrate"] = 9600  # Значение по умолчанию
                logger.info(f"Используется скорость по умолчанию: {kwargs['baudrate']}")
        
        elif connection_type == "TCP":
            if "host" not in kwargs:
                raise TypeError("Для TCP подключения необходим параметр 'host'")
            if "port" not in kwargs:
                kwargs["port"] = 5009  # Значение по умолчанию
                logger.info(f"Используется порт по умолчанию: {kwargs['port']}")
        
        # Добавляем протокол, если указан
        if protocol:
            kwargs["protocol"] = protocol
        
        # Создаем клиент
        try:
            client = client_class(address=address, **kwargs)
            logger.info(
                f"Создан {connection_type} клиент для адреса {address} "
                f"с параметрами: {cls._safe_kwargs_for_log(kwargs)}"
            )
            return client
        except Exception as e:
            logger.error(f"Ошибка создания клиента: {e}")
            raise
    
    @staticmethod
    def _safe_kwargs_for_log(kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Безопасное форматирование параметров для логирования."""
        safe_kwargs = kwargs.copy()
        # Маскируем чувствительные данные
        if "host" in safe_kwargs:
            parts = str(safe_kwargs["host"]).split(".")
            if len(parts) == 4:
                safe_kwargs["host"] = f"{parts[0]}.xxx.xxx.{parts[3]}"
        return safe_kwargs
    
    @classmethod
    def register_client_type(
        cls,
        connection_type: str,
        client_class: Type[TEM104_Base_Client]
    ) -> None:
        """
        Регистрирует новый тип клиента в фабрике.
        
        Args:
            connection_type: Имя типа подключения
            client_class: Класс клиента
        """
        cls._client_types[connection_type] = client_class
        logger.info(f"Зарегистрирован новый тип клиента: {connection_type}")


class ConnectionPoolManager:
    """
    Менеджер пула соединений для оптимизации массового опроса.
    """
    
    def __init__(self, max_connections: int = 10):
        """
        Инициализация менеджера пула соединений.
        
        Args:
            max_connections: Максимальное количество одновременных соединений
        """
        self.max_connections = max_connections
        self._connections: Dict[str, TEM104_Base_Client] = {}
        self._connection_usage: Dict[str, int] = {}
        logger.info(f"Инициализирован пул соединений (макс: {max_connections})")
    
    def get_connection(
        self,
        connection_id: str,
        connection_type: ConnectionType,
        **kwargs
    ) -> TEM104_Base_Client:
        """
        Получает или создает соединение из пула.
        
        Args:
            connection_id: Уникальный идентификатор соединения
            connection_type: Тип подключения
            **kwargs: Параметры для создания нового соединения
            
        Returns:
            Клиент из пула соединений
        """
        if connection_id in self._connections:
            client = self._connections[connection_id]
            self._connection_usage[connection_id] += 1
            logger.debug(f"Переиспользование соединения {connection_id} "
                        f"(использований: {self._connection_usage[connection_id]})")
            return client
        
        # Проверяем лимит соединений
        if len(self._connections) >= self.max_connections:
            # Удаляем наименее используемое соединение
            least_used_id = min(self._connection_usage, key=self._connection_usage.get)
            self.release_connection(least_used_id)
        
        # Создаем новое соединение
        client = TEM104ClientFactory.create_client(connection_type, **kwargs)
        self._connections[connection_id] = client
        self._connection_usage[connection_id] = 1
        logger.info(f"Создано новое соединение в пуле: {connection_id}")
        return client
    
    def release_connection(self, connection_id: str) -> None:
        """
        Освобождает соединение из пула.
        
        Args:
            connection_id: Идентификатор соединения
        """
        if connection_id in self._connections:
            client = self._connections[connection_id]
            try:
                client.disconnect()
            except Exception as e:
                logger.warning(f"Ошибка при закрытии соединения {connection_id}: {e}")
            
            del self._connections[connection_id]
            del self._connection_usage[connection_id]
            logger.info(f"Соединение {connection_id} удалено из пула")
    
    def release_all(self) -> None:
        """Освобождает все соединения в пуле."""
        connection_ids = list(self._connections.keys())
        for conn_id in connection_ids:
            self.release_connection(conn_id)
        logger.info("Все соединения в пуле освобождены")
    
    def __enter__(self):
        """Контекстный менеджер - вход."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер - выход."""
        self.release_all()
