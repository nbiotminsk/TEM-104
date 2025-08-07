# -*- coding: utf-8 -*-
"""
Конфигурация логирования для проекта TEM-104.
Обеспечивает централизованное управление логами.
"""

import logging
import logging.handlers
import os
from datetime import datetime
from typing import Optional
import sys


class ColoredFormatter(logging.Formatter):
    """
    Форматтер с цветным выводом для консоли.
    """
    
    # ANSI escape codes для цветов
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    def format(self, record):
        """Форматирует запись лога с цветом."""
        if not sys.stdout.isatty():
            # Не используем цвета, если вывод не в терминал
            return super().format(record)
        
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        
        return super().format(record)


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_dir: str = "logs",
    console_output: bool = True,
    file_output: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    Настраивает систему логирования для проекта.
    
    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Имя файла лога (если None, генерируется автоматически)
        log_dir: Директория для логов
        console_output: Выводить логи в консоль
        file_output: Сохранять логи в файл
        max_bytes: Максимальный размер файла лога
        backup_count: Количество резервных копий файлов лога
        format_string: Формат строки лога
        
    Returns:
        Настроенный корневой логгер
        
    Examples:
        >>> logger = setup_logging(log_level="DEBUG")
        >>> logger.info("Система логирования настроена")
    """
    
    # Создаем директорию для логов, если не существует
    if file_output and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Генерируем имя файла лога, если не указано
    if log_file is None:
        timestamp = datetime.now().strftime("%Y%m%d")
        log_file = f"tem104_{timestamp}.log"
    
    # Формат лога по умолчанию
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Получаем корневой логгер
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Удаляем существующие обработчики
    logger.handlers.clear()
    
    # Настройка вывода в консоль
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        
        # Используем цветной форматтер для консоли
        console_formatter = ColoredFormatter(format_string)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    # Настройка записи в файл
    if file_output:
        file_path = os.path.join(log_dir, log_file)
        file_handler = logging.handlers.RotatingFileHandler(
            file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))
        
        # Обычный форматтер для файла (без цветов)
        file_formatter = logging.Formatter(format_string)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    # Логируем информацию о настройке
    logger.info("=" * 50)
    logger.info("Система логирования инициализирована")
    logger.info(f"Уровень логирования: {log_level}")
    if file_output:
        logger.info(f"Файл лога: {os.path.join(log_dir, log_file)}")
    logger.info("=" * 50)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Получает логгер для модуля.
    
    Args:
        name: Имя модуля (обычно __name__)
        
    Returns:
        Логгер для модуля
        
    Examples:
        >>> logger = get_logger(__name__)
        >>> logger.debug("Отладочное сообщение")
    """
    return logging.getLogger(name)


class LogContext:
    """
    Контекстный менеджер для временного изменения уровня логирования.
    
    Использование:
        with LogContext(logging.DEBUG):
            # Здесь будут выводиться отладочные сообщения
            logger.debug("Это сообщение будет видно")
    """
    
    def __init__(self, level: int, logger: Optional[logging.Logger] = None):
        """
        Инициализация контекста логирования.
        
        Args:
            level: Временный уровень логирования
            logger: Логгер для изменения (если None, используется корневой)
        """
        self.level = level
        self.logger = logger or logging.getLogger()
        self.old_level = None
    
    def __enter__(self):
        """Вход в контекст - сохраняем и меняем уровень."""
        self.old_level = self.logger.level
        self.logger.setLevel(self.level)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Выход из контекста - восстанавливаем уровень."""
        self.logger.setLevel(self.old_level)


class PerformanceLogger:
    """
    Класс для логирования производительности операций.
    
    Использование:
        perf = PerformanceLogger("Опрос устройства")
        perf.start()
        # ... выполнение операции ...
        perf.stop()
    """
    
    def __init__(self, operation_name: str, logger: Optional[logging.Logger] = None):
        """
        Инициализация логгера производительности.
        
        Args:
            operation_name: Имя операции
            logger: Логгер для вывода (если None, используется корневой)
        """
        self.operation_name = operation_name
        self.logger = logger or logging.getLogger()
        self.start_time = None
        self.end_time = None
    
    def start(self):
        """Начинает отсчет времени."""
        self.start_time = datetime.now()
        self.logger.debug(f"Начало операции: {self.operation_name}")
    
    def stop(self):
        """Останавливает отсчет и логирует результат."""
        if self.start_time is None:
            self.logger.warning(f"Операция {self.operation_name} не была начата")
            return
        
        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()
        
        self.logger.info(
            f"Операция '{self.operation_name}' завершена за {duration:.3f} сек"
        )
        
        # Сброс для повторного использования
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        """Контекстный менеджер - вход."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер - выход."""
        self.stop()


# Инициализация логирования при импорте модуля
# (можно закомментировать, если инициализация должна быть явной)
if not logging.getLogger().handlers:
    setup_logging()
