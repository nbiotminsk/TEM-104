# -*- coding: utf-8 -*-
"""
Интеграция улучшенного TemDriver с существующей библиотекой test104.py
Объединяет возможности обеих реализаций для максимальной совместимости
"""

import sys
import logging
from typing import Optional, Dict, Any, Union
from datetime import datetime

# Импортируем существующую библиотеку
try:
    from test104 import TEM104_Serial_Client, TEM104_Base_Client
except ImportError:
    print("Ошибка: Не найден файл test104.py")
    sys.exit(1)

# Импортируем улучшенный TemDriver
try:
    from Улучшенный_TemDriver import TemDriver, Tem104Protocol, Tem104MProtocol
except ImportError:
    print("Ошибка: Не найден файл Улучшенный_TemDriver.py")
    sys.exit(1)

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# УНИВЕРСАЛЬНЫЙ КЛИЕНТ ТЭМ-104
# ============================================================================

class UniversalTem104Client:
    """
    Универсальный клиент для работы с ТЭМ-104.
    Объединяет возможности существующей библиотеки и улучшенного TemDriver.
    """
    
    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 2.0):
        """
        Инициализация универсального клиента.
        
        Args:
            port: Имя COM-порта
            baudrate: Скорость передачи
            timeout: Таймаут чтения
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        
        # Инициализируем оба клиента
        self.legacy_client = TEM104_Serial_Client(port, baudrate, timeout)
        self.tem_driver = TemDriver(port, baudrate, timeout)
        
        # Флаги для определения используемого метода
        self.use_legacy = False
        self.device_type = None
        
        logger.info(f"Инициализирован UniversalTem104Client для порта {port}")

    def connect(self) -> bool:
        """
        Подключение к устройству.
        
        Returns:
            True если подключение успешно
        """
        try:
            # Пробуем подключиться через TemDriver
            if self.tem_driver.connect():
                logger.info("Подключение через TemDriver успешно")
                return True
            else:
                logger.warning("TemDriver не смог подключиться")
                return False
        except Exception as e:
            logger.error(f"Ошибка подключения: {e}")
            return False

    def disconnect(self):
        """Отключение от устройства."""
        try:
            self.tem_driver.disconnect()
            logger.info("Отключение выполнено")
        except Exception as e:
            logger.error(f"Ошибка отключения: {e}")

    def identify_device(self, address: int) -> Optional[str]:
        """
        Идентификация устройства с автоматическим выбором метода.
        
        Args:
            address: Адрес устройства
            
        Returns:
            Имя устройства или None
        """
        logger.info(f"Идентификация устройства с адресом {address}")
        
        # Пробуем через TemDriver
        try:
            device_name = self.tem_driver.identify_device(address)
            if device_name:
                self.device_type = device_name
                logger.info(f"Устройство определено через TemDriver: {device_name}")
                return device_name
        except Exception as e:
            logger.warning(f"TemDriver не смог идентифицировать устройство: {e}")
        
        # Пробуем через legacy клиент
        try:
            self.legacy_client.connect()
            # Здесь нужно добавить метод идентификации для legacy клиента
            # Пока что просто возвращаем None
            logger.info("Попытка идентификации через legacy клиент")
            return None
        except Exception as e:
            logger.warning(f"Legacy клиент не смог подключиться: {e}")
        
        return None

    def read_all_data(self, address: int) -> Optional[Dict[str, Any]]:
        """
        Чтение всех данных с устройства.
        
        Args:
            address: Адрес устройства
            
        Returns:
            Словарь с данными или None
        """
        logger.info(f"Чтение всех данных с адреса {address}")
        
        # Сначала идентифицируем устройство
        device_name = self.identify_device(address)
        if not device_name:
            logger.error("Не удалось идентифицировать устройство")
            return None
        
        # Выбираем протокол
        if 'M' in device_name:
            protocol = Tem104MProtocol(self.tem_driver, address)
            logger.info("Используется протокол для новых моделей")
        else:
            protocol = Tem104Protocol(self.tem_driver, address)
            logger.info("Используется протокол для старых моделей")
        
        # Читаем данные
        results = {}
        
        try:
            # Время
            dt = protocol.read_datetime()
            if dt:
                results['datetime'] = dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Мгновенные параметры
            current = protocol.read_current_values()
            if current:
                results['current'] = current
            
            # Накопленные итоги
            totals = protocol.read_total_values()
            if totals:
                results['totals'] = totals
            
            # Дополнительная информация
            results['device_type'] = device_name
            results['address'] = address
            results['timestamp'] = datetime.now().isoformat()
            
            logger.info("Данные успешно прочитаны")
            return results
            
        except Exception as e:
            logger.error(f"Ошибка чтения данных: {e}")
            return None

    def read_current_values(self, address: int) -> Optional[Dict[str, float]]:
        """
        Чтение только мгновенных параметров.
        
        Args:
            address: Адрес устройства
            
        Returns:
            Словарь с мгновенными параметрами или None
        """
        device_name = self.identify_device(address)
        if not device_name:
            return None
        
        if 'M' in device_name:
            protocol = Tem104MProtocol(self.tem_driver, address)
        else:
            protocol = Tem104Protocol(self.tem_driver, address)
        
        return protocol.read_current_values()

    def read_total_values(self, address: int) -> Optional[Dict[str, float]]:
        """
        Чтение только накопленных итогов.
        
        Args:
            address: Адрес устройства
            
        Returns:
            Словарь с накопленными итогами или None
        """
        device_name = self.identify_device(address)
        if not device_name:
            return None
        
        if 'M' in device_name:
            protocol = Tem104MProtocol(self.tem_driver, address)
        else:
            protocol = Tem104Protocol(self.tem_driver, address)
        
        return protocol.read_total_values()

    def read_datetime(self, address: int) -> Optional[datetime]:
        """
        Чтение времени с устройства.
        
        Args:
            address: Адрес устройства
            
        Returns:
            Объект datetime или None
        """
        device_name = self.identify_device(address)
        if not device_name:
            return None
        
        if 'M' in device_name:
            protocol = Tem104MProtocol(self.tem_driver, address)
        else:
            protocol = Tem104Protocol(self.tem_driver, address)
        
        return protocol.read_datetime()

    def __enter__(self):
        """Поддержка контекстного менеджера."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Автоматическое закрытие соединения."""
        self.disconnect()

# ============================================================================
# РАСШИРЕННЫЙ МАССОВЫЙ ОПРОС
# ============================================================================

class AdvancedMassPolling:
    """
    Расширенный класс для массового опроса устройств.
    Использует универсальный клиент для максимальной совместимости.
    """
    
    def __init__(self):
        """Инициализация массового опроса."""
        self.results = []
        self.statistics = {
            'total': 0,
            'success': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }
    
    def poll_device(self, port: str, address: int, name: str = None) -> Dict[str, Any]:
        """
        Опрос одного устройства.
        
        Args:
            port: COM-порт
            address: Адрес устройства
            name: Имя устройства (опционально)
            
        Returns:
            Результат опроса
        """
        if name is None:
            name = f"Устройство {address}"
        
        result = {
            'name': name,
            'port': port,
            'address': address,
            'status': 'ERROR',
            'error': None,
            'data': None,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            with UniversalTem104Client(port) as client:
                # Читаем все данные
                data = client.read_all_data(address)
                
                if data:
                    result['status'] = 'SUCCESS'
                    result['data'] = data
                    self.statistics['success'] += 1
                else:
                    result['error'] = 'Данные не получены'
                    self.statistics['errors'] += 1
                    
        except Exception as e:
            result['error'] = str(e)
            self.statistics['errors'] += 1
        
        self.statistics['total'] += 1
        return result
    
    def poll_devices(self, devices: list) -> list:
        """
        Массовый опрос устройств.
        
        Args:
            devices: Список устройств [{'port': 'COM3', 'address': 1, 'name': 'Device1'}, ...]
            
        Returns:
            Список результатов опроса
        """
        logger.info(f"Начинаем массовый опрос {len(devices)} устройств")
        
        self.statistics['start_time'] = datetime.now()
        self.results = []
        
        for i, device in enumerate(devices, 1):
            logger.info(f"Опрос {i}/{len(devices)}: {device.get('name', f'Device {device.get('address', 'Unknown')}')}")
            
            result = self.poll_device(
                port=device['port'],
                address=device['address'],
                name=device.get('name')
            )
            
            self.results.append(result)
            
            # Выводим результат
            if result['status'] == 'SUCCESS':
                logger.info(f"  ✓ Успешно")
                if result['data'] and 'current' in result['data']:
                    current = result['data']['current']
                    logger.info(f"    T1: {current.get('t1', 0):.1f}°C, T2: {current.get('t2', 0):.1f}°C")
            else:
                logger.warning(f"  ✗ Ошибка: {result['error']}")
        
        self.statistics['end_time'] = datetime.now()
        
        # Выводим статистику
        self._print_statistics()
        
        return self.results
    
    def _print_statistics(self):
        """Вывод статистики опроса."""
        duration = self.statistics['end_time'] - self.statistics['start_time']
        
        print("\n" + "="*60)
        print("📊 СТАТИСТИКА МАССОВОГО ОПРОСА")
        print("="*60)
        print(f"Всего устройств: {self.statistics['total']}")
        print(f"Успешно: {self.statistics['success']}")
        print(f"Ошибки: {self.statistics['errors']}")
        print(f"Время выполнения: {duration}")
        
        if self.statistics['total'] > 0:
            success_rate = (self.statistics['success'] / self.statistics['total']) * 100
            print(f"Процент успеха: {success_rate:.1f}%")
    
    def save_results(self, filename: str = None):
        """
        Сохранение результатов в JSON файл.
        
        Args:
            filename: Имя файла (если None, генерируется автоматически)
        """
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"mass_poll_results_{timestamp}.json"
        
        data = {
            'statistics': self.statistics,
            'results': self.results,
            'generated_at': datetime.now().isoformat()
        }
        
        try:
            import json
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Результаты сохранены в {filename}")
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")

# ============================================================================
# ДЕМОНСТРАЦИОННЫЕ ФУНКЦИИ
# ============================================================================

def demo_universal_client():
    """Демонстрация универсального клиента."""
    
    print("=== ДЕМОНСТРАЦИЯ УНИВЕРСАЛЬНОГО КЛИЕНТА ===")
    
    PORT = 'COM3'
    ADDRESS = 1
    
    try:
        with UniversalTem104Client(PORT) as client:
            # Идентификация
            device_name = client.identify_device(ADDRESS)
            if device_name:
                print(f"✓ Устройство: {device_name}")
                
                # Чтение всех данных
                data = client.read_all_data(ADDRESS)
                if data:
                    print("✓ Данные получены:")
                    if 'datetime' in data:
                        print(f"  Время: {data['datetime']}")
                    if 'current' in data:
                        current = data['current']
                        print(f"  T1: {current.get('t1', 0):.1f}°C")
                        print(f"  T2: {current.get('t2', 0):.1f}°C")
                        print(f"  Flow: {current.get('flow1', 0):.2f} м³/ч")
                    if 'totals' in data:
                        totals = data['totals']
                        print(f"  V1: {totals.get('V1_total', 0):.3f} м³")
                        print(f"  Q1: {totals.get('Q1_total', 0):.4f} кВт·ч")
                else:
                    print("✗ Данные не получены")
            else:
                print("✗ Устройство не найдено")
                
    except Exception as e:
        print(f"✗ Ошибка: {e}")

def demo_mass_polling():
    """Демонстрация массового опроса."""
    
    print("=== ДЕМОНСТРАЦИЯ МАССОВОГО ОПРОСА ===")
    
    # Список устройств для опроса
    devices = [
        {'port': 'COM3', 'address': 1, 'name': 'ТЭМ-104 #1'},
        {'port': 'COM3', 'address': 2, 'name': 'ТЭМ-104 #2'},
        {'port': 'COM4', 'address': 1, 'name': 'ТЭМ-104М #1'},
    ]
    
    poller = AdvancedMassPolling()
    results = poller.poll_devices(devices)
    
    # Сохраняем результаты
    poller.save_results()
    
    return results

def main():
    """Главная функция."""
    
    print("🔧 ИНТЕГРАЦИЯ TEMDRIVER С СУЩЕСТВУЮЩЕЙ БИБЛИОТЕКОЙ")
    print("=" * 60)
    
    while True:
        print("\nВыберите демонстрацию:")
        print("  1 - Универсальный клиент")
        print("  2 - Массовый опрос")
        print("  0 - Выход")
        
        choice = input("\nВаш выбор: ").strip()
        
        if choice == "0":
            print("До свидания!")
            break
        elif choice == "1":
            demo_universal_client()
        elif choice == "2":
            demo_mass_polling()
        else:
            print("❌ Неверный выбор")

if __name__ == "__main__":
    main() 