# -*- coding: utf-8 -*-
"""
Пример использования улучшенной архитектуры TEM-104.
Демонстрирует новые возможности: фабрику, парсеры, логирование.
"""

import sys
import os
import time

# Добавляем путь к библиотеке
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core_library import (
    TEM104ClientFactory,
    ConnectionPoolManager,
    setup_logging,
    get_logger,
    PerformanceLogger,
    LogContext,
    TEM104Data
)
import logging


def example_basic_usage():
    """Базовый пример использования с фабрикой."""
    print("\n" + "="*60)
    print("ПРИМЕР 1: Базовое использование с фабрикой")
    print("="*60)
    
    # Настройка логирования
    setup_logging(log_level="INFO", file_output=True)
    logger = get_logger(__name__)
    
    try:
        # Создание клиента через фабрику
        client = TEM104ClientFactory.create_client(
            connection_type="COM",
            port="COM3",
            baudrate=9600,
            address=1
        )
        
        logger.info("Клиент создан успешно")
        
        # Подключение и опрос
        with PerformanceLogger("Полный цикл опроса"):
            client.connect()
            logger.info("Подключение установлено")
            
            # Чтение данных
            data = client.read_all_data()
            
            # Вывод результатов
            print(f"\nДанные устройства:")
            print(f"  Протокол: {client.protocol_type}")
            print(f"  Энергия (Q): {data.get('Q', 'N/A'):.3f} Гкал")
            print(f"  Масса (M1): {data.get('M1', 'N/A'):.3f} т")
            print(f"  Температура 1: {data.get('T1', 'N/A'):.2f} °C")
            print(f"  Температура 2: {data.get('T2', 'N/A'):.2f} °C")
            
            client.disconnect()
            logger.info("Соединение закрыто")
            
    except Exception as e:
        logger.error(f"Ошибка при опросе: {e}")
        print(f"Ошибка: {e}")


def example_tcp_with_pool():
    """Пример работы с TCP и пулом соединений."""
    print("\n" + "="*60)
    print("ПРИМЕР 2: TCP с пулом соединений")
    print("="*60)
    
    logger = get_logger(__name__)
    
    # Список устройств для опроса
    devices = [
        {"id": "device1", "host": "128.140.251.30", "port": 5009, "address": 1},
        {"id": "device2", "host": "128.140.251.22", "port": 5009, "address": 1},
        {"id": "device3", "host": "128.140.251.52", "port": 5009, "address": 1},
    ]
    
    # Использование пула соединений
    with ConnectionPoolManager(max_connections=5) as pool:
        for device in devices:
            try:
                # Получаем соединение из пула
                client = pool.get_connection(
                    connection_id=device["id"],
                    connection_type="TCP",
                    host=device["host"],
                    port=device["port"],
                    address=device["address"]
                )
                
                client.connect()
                data = client.read_all_data()
                
                print(f"\nУстройство {device['id']} ({device['host']}):")
                print(f"  Статус: ОНЛАЙН")
                print(f"  Энергия: {data.get('Q', 'N/A'):.3f} Гкал")
                
            except Exception as e:
                print(f"\nУстройство {device['id']} ({device['host']}):")
                print(f"  Статус: ОШИБКА - {e}")
                logger.warning(f"Не удалось опросить {device['id']}: {e}")


def example_with_dataclass():
    """Пример использования датакласса TEM104Data."""
    print("\n" + "="*60)
    print("ПРИМЕР 3: Использование датакласса TEM104Data")
    print("="*60)
    
    # Создаем объект данных
    data = TEM104Data(
        energy_Q=123.456,
        mass_M1=78.900,
        volume_V1=100.500,
        temp_T1=65.12,
        temp_T2=45.34,
        flow_G1=3.456,
        operating_time=3600 * 1000,  # 1000 часов в секундах
        protocol_type='ARVAS_M1',
        device_status='OK'
    )
    
    # Используем свойства датакласса
    print(f"\nДанные устройства (через датакласс):")
    print(f"  Протокол: {data.protocol_type}")
    print(f"  Статус: {data.device_status}")
    print(f"  Энергия: {data.energy_Q:.3f} Гкал")
    print(f"  Масса: {data.mass_M1:.3f} т")
    print(f"  Объем: {data.volume_V1:.3f} м³")
    print(f"  Температуры: {data.temp_T1:.1f}°C / {data.temp_T2:.1f}°C")
    print(f"  Расход: {data.flow_G1:.3f} м³/ч")
    print(f"  Наработка: {data.operating_hours} часов")
    
    # Преобразование в словарь для обратной совместимости
    data_dict = data.to_dict()
    print(f"\nСловарь для совместимости: {list(data_dict.keys())}")


def example_debug_logging():
    """Пример работы с различными уровнями логирования."""
    print("\n" + "="*60)
    print("ПРИМЕР 4: Управление логированием")
    print("="*60)
    
    logger = get_logger(__name__)
    
    # Обычный уровень логирования
    logger.info("Это информационное сообщение")
    logger.debug("Это отладочное сообщение (не видно на уровне INFO)")
    
    # Временное изменение уровня логирования
    print("\nВременное включение DEBUG:")
    with LogContext(logging.DEBUG):
        logger.debug("Теперь отладочные сообщения видны!")
        logger.info("Информационные тоже видны")
    
    logger.debug("Это снова не видно (вернулись к INFO)")
    
    # Измерение производительности
    print("\nИзмерение производительности:")
    with PerformanceLogger("Имитация долгой операции"):
        time.sleep(0.5)  # Имитация работы
        logger.info("Выполняется операция...")
        time.sleep(0.5)


def example_error_handling():
    """Пример обработки ошибок с логированием."""
    print("\n" + "="*60)
    print("ПРИМЕР 5: Обработка ошибок")
    print("="*60)
    
    logger = get_logger(__name__)
    
    # Попытка создать клиент с неверными параметрами
    try:
        # Неверный тип подключения
        client = TEM104ClientFactory.create_client(
            connection_type="INVALID_TYPE",
            address=1
        )
    except ValueError as e:
        logger.error(f"Ошибка создания клиента: {e}")
        print(f"Перехвачена ошибка: {e}")
    
    # Попытка создать TCP клиент без обязательных параметров
    try:
        client = TEM104ClientFactory.create_client(
            connection_type="TCP",
            address=1
            # host не указан - будет ошибка
        )
    except TypeError as e:
        logger.error(f"Отсутствуют обязательные параметры: {e}")
        print(f"Перехвачена ошибка: {e}")


def main():
    """Главная функция с меню выбора примера."""
    print("\n" + "="*60)
    print("ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ УЛУЧШЕННОЙ АРХИТЕКТУРЫ TEM-104")
    print("="*60)
    
    examples = {
        "1": ("Базовое использование с фабрикой", example_basic_usage),
        "2": ("TCP с пулом соединений", example_tcp_with_pool),
        "3": ("Использование датакласса TEM104Data", example_with_dataclass),
        "4": ("Управление логированием", example_debug_logging),
        "5": ("Обработка ошибок", example_error_handling),
        "6": ("Запустить все примеры", None)
    }
    
    print("\nДоступные примеры:")
    for key, (name, _) in examples.items():
        print(f"  {key}. {name}")
    
    choice = input("\nВыберите пример (1-6) или Enter для выхода: ").strip()
    
    if choice == "6":
        # Запуск всех примеров
        for key, (name, func) in examples.items():
            if key != "6" and func:
                func()
    elif choice in examples and examples[choice][1]:
        # Запуск выбранного примера
        examples[choice][1]()
    elif choice:
        print("Неверный выбор")
    
    print("\n" + "="*60)
    print("Примеры завершены")
    print("="*60)


if __name__ == "__main__":
    main()
