# -*- coding: utf-8 -*-
"""
Практические примеры использования улучшенного TemDriver
На основе руководства "Опрос счетчиков ТЭМ-104 на Python_ Полное руководство"
"""

from Улучшенный_TemDriver import TemDriver, Tem104Protocol, Tem104MProtocol
import logging
import time
import json
from datetime import datetime, timedelta

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# ПРИМЕР 1: Простая проверка связи
# ============================================================================

def example_1_simple_connection():
    """Простейший пример - проверяем, что устройство отвечает."""
    
    print("=== ПРИМЕР 1: Простая проверка связи ===")
    
    # Настройки подключения
    PORT = 'COM3'  # Замените на ваш порт
    DEVICE_ADDRESS = 1
    
    try:
        with TemDriver(port=PORT) as driver:
            if not driver.ser:
                print("✗ Не удалось подключиться к устройству")
                return
            
            # Идентификация устройства
            device_name = driver.identify_device(DEVICE_ADDRESS)
            
            if device_name:
                print(f"✓ Устройство найдено: {device_name}")
                
                # Определяем тип протокола
                if 'M' in device_name:
                    print("  Тип: Новые модели (ТЭМ-104М/104М-1)")
                else:
                    print("  Тип: Старые модели (ТЭМ-104/104-1)")
            else:
                print("✗ Устройство не отвечает")
                
    except Exception as e:
        print(f"✗ Ошибка: {e}")

# ============================================================================
# ПРИМЕР 2: Полный опрос устройства
# ============================================================================

def example_2_full_device_poll():
    """Полный опрос устройства с чтением всех данных."""
    
    print("=== ПРИМЕР 2: Полный опрос устройства ===")
    
    PORT = 'COM3'
    DEVICE_ADDRESS = 1
    
    try:
        with TemDriver(port=PORT) as driver:
            if not driver.ser:
                print("✗ Не удалось подключиться к устройству")
                return
            
            # Идентификация
            device_name = driver.identify_device(DEVICE_ADDRESS)
            if not device_name:
                print("✗ Устройство не найдено")
                return
            
            # Выбор протокола
            if 'M' in device_name:
                protocol = Tem104MProtocol(driver, DEVICE_ADDRESS)
                print("Используется протокол для новых моделей")
            else:
                protocol = Tem104Protocol(driver, DEVICE_ADDRESS)
                print("Используется протокол для старых моделей")
            
            # Чтение всех данных
            results = {}
            
            # 1. Время
            dt = protocol.read_datetime()
            if dt:
                results['datetime'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                print(f"✓ Время: {results['datetime']}")
            
            # 2. Мгновенные параметры
            current = protocol.read_current_values()
            if current:
                results['current'] = current
                print("✓ Мгновенные параметры:")
                for key, value in current.items():
                    print(f"  {key}: {value}")
            
            # 3. Накопленные итоги
            totals = protocol.read_total_values()
            if totals:
                results['totals'] = totals
                print("✓ Накопленные итоги:")
                for key, value in totals.items():
                    print(f"  {key}: {value}")
            
            # Сохранение результатов
            if results:
                filename = f"device_poll_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                print(f"✓ Результаты сохранены в {filename}")
                
    except Exception as e:
        print(f"✗ Ошибка: {e}")

# ============================================================================
# ПРИМЕР 3: Мониторинг в реальном времени
# ============================================================================

def example_3_real_time_monitoring():
    """Мониторинг устройства в реальном времени."""
    
    print("=== ПРИМЕР 3: Мониторинг в реальном времени ===")
    print("Нажмите Ctrl+C для остановки\n")
    
    PORT = 'COM3'
    DEVICE_ADDRESS = 1
    POLL_INTERVAL = 30  # секунды
    
    try:
        with TemDriver(port=PORT) as driver:
            if not driver.ser:
                print("✗ Не удалось подключиться к устройству")
                return
            
            # Идентификация
            device_name = driver.identify_device(DEVICE_ADDRESS)
            if not device_name:
                print("✗ Устройство не найдено")
                return
            
            # Выбор протокола
            if 'M' in device_name:
                protocol = Tem104MProtocol(driver, DEVICE_ADDRESS)
            else:
                protocol = Tem104Protocol(driver, DEVICE_ADDRESS)
            
            cycle = 0
            while True:
                cycle += 1
                print(f"\n🔄 Цикл {cycle} - {datetime.now().strftime('%H:%M:%S')}")
                print("-" * 50)
                
                try:
                    # Чтение мгновенных параметров
                    current = protocol.read_current_values()
                    if current:
                        print(f"T1: {current.get('t1', 0):6.1f}°C | "
                              f"T2: {current.get('t2', 0):6.1f}°C | "
                              f"Flow: {current.get('flow1', 0):6.2f} м³/ч | "
                              f"Power: {current.get('power1', 0):6.3f} кВт")
                    else:
                        print("✗ Данные не получены")
                        
                except Exception as e:
                    print(f"✗ Ошибка чтения: {e}")
                
                print(f"⏰ Следующий опрос через {POLL_INTERVAL} секунд...")
                time.sleep(POLL_INTERVAL)
                
    except KeyboardInterrupt:
        print("\n⏹️  Мониторинг остановлен пользователем")
    except Exception as e:
        print(f"✗ Критическая ошибка: {e}")

# ============================================================================
# ПРИМЕР 4: Диагностика проблем
# ============================================================================

def example_4_diagnostics():
    """Диагностика проблем с подключением."""
    
    print("=== ПРИМЕР 4: Диагностика проблем ===")
    
    # Тестируем разные настройки
    test_configs = [
        {"port": "COM3", "baudrate": 9600, "address": 1},
        {"port": "COM3", "baudrate": 19200, "address": 1},
        {"port": "COM3", "baudrate": 9600, "address": 2},
        {"port": "COM4", "baudrate": 9600, "address": 1},
    ]
    
    for i, config in enumerate(test_configs, 1):
        print(f"\n🔍 Тест {i}: {config}")
        
        try:
            with TemDriver(port=config['port'], baudrate=config['baudrate']) as driver:
                if not driver.ser:
                    print("  ✗ Порт не открыт")
                    continue
                
                # Идентификация
                device_name = driver.identify_device(config['address'])
                if device_name:
                    print(f"  ✓ Устройство найдено: {device_name}")
                    
                    # Тест чтения данных
                    if 'M' in device_name:
                        protocol = Tem104MProtocol(driver, config['address'])
                    else:
                        protocol = Tem104Protocol(driver, config['address'])
                    
                    current = protocol.read_current_values()
                    if current:
                        print(f"  ✓ Данные прочитаны (T1: {current.get('t1', 0):.1f}°C)")
                    else:
                        print("  ⚠ Данные не прочитаны")
                else:
                    print("  ✗ Устройство не отвечает")
                    
        except Exception as e:
            print(f"  ✗ Ошибка: {e}")

# ============================================================================
# ПРИМЕР 5: Массовый опрос устройств
# ============================================================================

def example_5_mass_polling():
    """Массовый опрос нескольких устройств."""
    
    print("=== ПРИМЕР 5: Массовый опрос устройств ===")
    
    # Список устройств для опроса
    devices = [
        {"port": "COM3", "address": 1, "name": "Устройство 1"},
        {"port": "COM3", "address": 2, "name": "Устройство 2"},
        {"port": "COM4", "address": 1, "name": "Устройство 3"},
    ]
    
    results = []
    
    for device in devices:
        print(f"\n📡 Опрос: {device['name']} (Порт: {device['port']}, Адрес: {device['address']})")
        
        try:
            with TemDriver(port=device['port']) as driver:
                if not driver.ser:
                    print("  ✗ Порт не открыт")
                    continue
                
                # Идентификация
                device_name = driver.identify_device(device['address'])
                if not device_name:
                    print("  ✗ Устройство не отвечает")
                    continue
                
                print(f"  ✓ Устройство: {device_name}")
                
                # Выбор протокола
                if 'M' in device_name:
                    protocol = Tem104MProtocol(driver, device['address'])
                else:
                    protocol = Tem104Protocol(driver, device['address'])
                
                # Чтение данных
                current = protocol.read_current_values()
                totals = protocol.read_total_values()
                
                if current or totals:
                    result = {
                        "name": device['name'],
                        "port": device['port'],
                        "address": device['address'],
                        "device_type": device_name,
                        "status": "ONLINE",
                        "current": current,
                        "totals": totals,
                        "timestamp": datetime.now().isoformat()
                    }
                    results.append(result)
                    
                    print("  ✓ Данные получены:")
                    if current:
                        print(f"    T1: {current.get('t1', 0):.1f}°C")
                        print(f"    T2: {current.get('t2', 0):.1f}°C")
                    if totals:
                        print(f"    V1: {totals.get('V1_total', 0):.3f} м³")
                        print(f"    Q1: {totals.get('Q1_total', 0):.4f} кВт·ч")
                else:
                    print("  ✗ Данные не получены")
                    
        except Exception as e:
            print(f"  ✗ Ошибка: {e}")
            results.append({
                "name": device['name'],
                "port": device['port'],
                "address": device['address'],
                "status": "ERROR",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
        
        time.sleep(1)  # Пауза между опросами
    
    # Выводим сводку
    print(f"\n📋 СВОДКА ОПРОСА:")
    print("=" * 50)
    online_count = sum(1 for r in results if r['status'] == 'ONLINE')
    print(f"Всего устройств: {len(devices)}")
    print(f"Онлайн: {online_count}")
    print(f"Ошибки: {len(devices) - online_count}")
    
    # Сохраняем результаты
    if results:
        filename = f"mass_poll_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"✓ Результаты сохранены в {filename}")
    
    return results

# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================

def main():
    """Главная функция с меню выбора примеров."""
    
    print("🔥 ПРАКТИЧЕСКИЕ ПРИМЕРЫ TEMDRIVER")
    print("=" * 50)
    
    examples = [
        ("1", "Простая проверка связи", example_1_simple_connection),
        ("2", "Полный опрос устройства", example_2_full_device_poll),
        ("3", "Мониторинг в реальном времени", example_3_real_time_monitoring),
        ("4", "Диагностика проблем", example_4_diagnostics),
        ("5", "Массовый опрос устройств", example_5_mass_polling),
    ]
    
    while True:
        print("\nВыберите пример:")
        for num, name, func in examples:
            print(f"  {num} - {name}")
        print("  0 - Выход")
        
        choice = input("\nВаш выбор: ").strip()
        
        if choice == "0":
            print("До свидания!")
            break
        elif choice in [num for num, _, _ in examples]:
            # Находим выбранную функцию
            for num, name, func in examples:
                if num == choice:
                    print(f"\n🚀 Запуск: {name}")
                    print("=" * 50)
                    try:
                        func()
                    except Exception as e:
                        print(f"✗ Ошибка выполнения: {e}")
                    break
        else:
            print("❌ Неверный выбор")

if __name__ == "__main__":
    main() 