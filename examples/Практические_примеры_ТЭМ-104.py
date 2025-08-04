# -*- coding: utf-8 -*-
"""
Практические примеры работы с теплосчетчиками ТЭМ-104
На основе библиотеки test104.py
"""

from test104 import TEM104_Serial_Client, TEM104_TCP_Client
import time
import json

# ============================================================================
# ПРИМЕР 1: Простая идентификация устройства
# ============================================================================

def example_1_simple_identification():
    """Простейший пример - проверяем, что прибор отвечает."""
    
    print("=== ПРИМЕР 1: Простая идентификация ===")
    
    # Создаем клиент для COM-порта
    client = TEM104_Serial_Client(
        port='COM3',      # Замените на ваш порт
        baudrate=9600,    # Скорость
        address=1         # Адрес счетчика
    )
    
    try:
        # Подключаемся
        print("Подключение к COM-порту...")
        client.connect()
        print("✓ Порт открыт успешно")
        
        # Определяем протокол автоматически
        print("Определение протокола...")
        protocol = client.auto_detect_protocol()
        
        if protocol:
            print(f"✓ Протокол определен: {protocol}")
            print(f"  Модель: {client.protocol_type}")
        else:
            print("✗ Не удалось определить протокол")
            return
            
    except Exception as e:
        print(f"✗ Ошибка: {e}")
    finally:
        client.disconnect()
        print("Соединение закрыто\n")

# ============================================================================
# ПРИМЕР 2: Чтение всех данных с форматированным выводом
# ============================================================================

def example_2_read_all_data():
    """Читаем все доступные данные с красивым форматированием."""
    
    print("=== ПРИМЕР 2: Чтение всех данных ===")
    
    client = TEM104_Serial_Client(port='COM3', baudrate=9600, address=1)
    
    try:
        client.connect()
        print("Подключение установлено")
        
        # Читаем все данные
        data = client.read_all_data()
        
        if data:
            print("\n📊 ДАННЫЕ СЧЕТЧИКА:")
            print("=" * 50)
            
            # Энергетические параметры
            print("🔥 ЭНЕРГЕТИЧЕСКИЕ ПАРАМЕТРЫ:")
            print(f"  Q (Энергия):     {data.get('Q', '---'):>10.3f} Гкал")
            print(f"  M1 (Масса):      {data.get('M1', '---'):>10.3f} т")
            
            # Температурные параметры
            print("\n🌡️  ТЕМПЕРАТУРНЫЕ ПАРАМЕТРЫ:")
            print(f"  T1 (Подача):     {data.get('T1', '---'):>10.2f} °C")
            print(f"  T2 (Обратка):    {data.get('T2', '---'):>10.2f} °C")
            
            # Расходные параметры
            print("\n💧 РАСХОДНЫЕ ПАРАМЕТРЫ:")
            print(f"  G1 (Расход 1):   {data.get('G1', '---'):>10.3f} м³/ч")
            print(f"  G2 (Расход 2):   {data.get('G2', '---'):>10.3f} м³/ч")
            
            # Технические параметры
            print("\n⚙️  ТЕХНИЧЕСКИЕ ПАРАМЕТРЫ:")
            print(f"  T_нар (Наработка): {int(data.get('T_nar', 0) / 3600):>10} ч")
            
            print("=" * 50)
        else:
            print("✗ Не удалось прочитать данные")
            
    except Exception as e:
        print(f"✗ Ошибка: {e}")
    finally:
        client.disconnect()

# ============================================================================
# ПРИМЕР 3: Массовый опрос через TCP/IP
# ============================================================================

def example_3_mass_polling():
    """Пример массового опроса нескольких счетчиков через TCP/IP."""
    
    print("=== ПРИМЕР 3: Массовый опрос через TCP/IP ===")
    
    # Список устройств для опроса
    devices = [
        {"name": "Дом 1", "ip": "192.168.1.100", "port": 5009, "addr": 1},
        {"name": "Дом 2", "ip": "192.168.1.101", "port": 5009, "addr": 1},
        {"name": "Дом 3", "ip": "192.168.1.102", "port": 5009, "addr": 1},
    ]
    
    results = []
    
    for device in devices:
        print(f"\n📡 Опрос: {device['name']} ({device['ip']})")
        
        client = None
        try:
            # Создаем TCP клиент
            client = TEM104_TCP_Client(
                host=device['ip'],
                port=device['port'],
                address=device['addr'],
                timeout=5.0
            )
            
            # Подключаемся
            client.connect()
            print("  ✓ Подключение установлено")
            
            # Определяем протокол
            protocol = client.auto_detect_protocol()
            print(f"  ✓ Протокол: {protocol}")
            
            # Читаем данные
            data = client.read_all_data()
            
            if data:
                # Сохраняем результат
                result = {
                    "name": device['name'],
                    "ip": device['ip'],
                    "protocol": protocol,
                    "status": "ONLINE",
                    "data": data
                }
                results.append(result)
                
                print(f"  ✓ Данные получены:")
                print(f"    Q: {data.get('Q', 0):.3f} Гкал")
                print(f"    T1: {data.get('T1', 0):.1f}°C")
                print(f"    T2: {data.get('T2', 0):.1f}°C")
            else:
                print("  ✗ Данные не получены")
                
        except Exception as e:
            print(f"  ✗ Ошибка: {e}")
            results.append({
                "name": device['name'],
                "ip": device['ip'],
                "status": "ERROR",
                "error": str(e)
            })
        finally:
            if client:
                client.disconnect()
        
        # Пауза между опросами
        time.sleep(1)
    
    # Выводим сводку
    print(f"\n📋 СВОДКА ОПРОСА:")
    print("=" * 50)
    online_count = sum(1 for r in results if r['status'] == 'ONLINE')
    print(f"Всего устройств: {len(devices)}")
    print(f"Онлайн: {online_count}")
    print(f"Ошибки: {len(devices) - online_count}")
    
    return results

# ============================================================================
# ПРИМЕР 4: Мониторинг в реальном времени
# ============================================================================

def example_4_real_time_monitoring():
    """Пример мониторинга в реальном времени с периодическим опросом."""
    
    print("=== ПРИМЕР 4: Мониторинг в реальном времени ===")
    print("Нажмите Ctrl+C для остановки\n")
    
    client = TEM104_Serial_Client(port='COM3', baudrate=9600, address=1)
    
    try:
        client.connect()
        print("Подключение установлено")
        
        # Определяем протокол один раз
        protocol = client.auto_detect_protocol()
        print(f"Протокол: {protocol}")
        
        cycle = 0
        while True:
            cycle += 1
            print(f"\n🔄 Цикл {cycle} - {time.strftime('%H:%M:%S')}")
            print("-" * 40)
            
            try:
                # Читаем данные
                data = client.read_all_data()
                
                if data:
                    # Выводим ключевые параметры
                    print(f"Q: {data.get('Q', 0):8.3f} Гкал | "
                          f"T1: {data.get('T1', 0):6.1f}°C | "
                          f"T2: {data.get('T2', 0):6.1f}°C | "
                          f"G1: {data.get('G1', 0):6.2f} м³/ч")
                else:
                    print("✗ Данные не получены")
                    
            except Exception as e:
                print(f"✗ Ошибка чтения: {e}")
            
            # Ждем 30 секунд до следующего опроса
            time.sleep(30)
            
    except KeyboardInterrupt:
        print("\n⏹️  Мониторинг остановлен пользователем")
    except Exception as e:
        print(f"✗ Критическая ошибка: {e}")
    finally:
        client.disconnect()
        print("Соединение закрыто")

# ============================================================================
# ПРИМЕР 5: Сохранение данных в файл
# ============================================================================

def example_5_data_logging():
    """Пример сохранения данных в JSON файл для дальнейшего анализа."""
    
    print("=== ПРИМЕР 5: Логирование данных ===")
    
    client = TEM104_Serial_Client(port='COM3', baudrate=9600, address=1)
    
    try:
        client.connect()
        print("Подключение установлено")
        
        # Читаем данные
        data = client.read_all_data()
        
        if data:
            # Добавляем метаданные
            log_entry = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "device_address": client.address,
                "protocol": client.protocol_type,
                "data": data
            }
            
            # Сохраняем в файл
            filename = f"tem104_log_{time.strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(log_entry, f, ensure_ascii=False, indent=2)
            
            print(f"✓ Данные сохранены в файл: {filename}")
            print(f"  Время: {log_entry['timestamp']}")
            print(f"  Протокол: {log_entry['protocol']}")
            print(f"  Q: {data.get('Q', 0):.3f} Гкал")
            
        else:
            print("✗ Данные не получены")
            
    except Exception as e:
        print(f"✗ Ошибка: {e}")
    finally:
        client.disconnect()

# ============================================================================
# ПРИМЕР 6: Диагностика проблем
# ============================================================================

def example_6_diagnostics():
    """Пример диагностики проблем с подключением."""
    
    print("=== ПРИМЕР 6: Диагностика проблем ===")
    
    # Тестируем разные настройки
    test_configs = [
        {"port": "COM3", "baudrate": 9600, "address": 1},
        {"port": "COM3", "baudrate": 19200, "address": 1},
        {"port": "COM3", "baudrate": 9600, "address": 2},
    ]
    
    for i, config in enumerate(test_configs, 1):
        print(f"\n🔍 Тест {i}: {config}")
        
        client = TEM104_Serial_Client(**config)
        
        try:
            # Пробуем подключиться
            client.connect()
            print("  ✓ Порт открыт")
            
            # Пробуем определить протокол
            protocol = client.auto_detect_protocol()
            if protocol:
                print(f"  ✓ Протокол: {protocol}")
                
                # Пробуем прочитать данные
                data = client.read_all_data()
                if data:
                    print(f"  ✓ Данные получены (Q: {data.get('Q', 0):.3f})")
                else:
                    print("  ⚠ Данные не прочитаны")
            else:
                print("  ✗ Протокол не определен")
                
        except Exception as e:
            print(f"  ✗ Ошибка: {e}")
        finally:
            client.disconnect()

# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================

def main():
    """Главная функция с меню выбора примеров."""
    
    print("🔥 ПРАКТИЧЕСКИЕ ПРИМЕРЫ РАБОТЫ С ТЭМ-104")
    print("=" * 50)
    
    examples = [
        ("1", "Простая идентификация", example_1_simple_identification),
        ("2", "Чтение всех данных", example_2_read_all_data),
        ("3", "Массовый опрос TCP/IP", example_3_mass_polling),
        ("4", "Мониторинг в реальном времени", example_4_real_time_monitoring),
        ("5", "Логирование данных", example_5_data_logging),
        ("6", "Диагностика проблем", example_6_diagnostics),
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