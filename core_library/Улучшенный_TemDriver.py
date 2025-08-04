# -*- coding: utf-8 -*-
"""
Улучшенный TemDriver для работы с теплосчетчиками ТЭМ-104
На основе руководства "Опрос счетчиков ТЭМ-104 на Python_ Полное руководство"
Интегрирован с существующей библиотекой test104.py
"""

import serial
import time
import struct
from datetime import datetime
from typing import Optional, Dict, Any, Union
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TemDriver:
    """
    Базовый драйвер для работы с теплосчетчиками ТЭМ-104.
    Обеспечивает низкоуровневую связь с устройством через COM-порт.
    """
    
    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 2.0):
        """
        Инициализация драйвера.
        
        Args:
            port: Имя COM-порта (например, 'COM3' или '/dev/ttyUSB0')
            baudrate: Скорость передачи (9600, 19200, 38400, 57600, 115200)
            timeout: Таймаут чтения в секундах
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        logger.info(f"Инициализирован TemDriver для порта {self.port} на скорости {self.baudrate}")

    def connect(self) -> bool:
        """
        Подключение к COM-порту.
        
        Returns:
            True если подключение успешно, False в противном случае
        """
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            logger.info(f"Подключение к порту {self.port} установлено")
            return True
        except serial.SerialException as e:
            logger.error(f"Ошибка: Не удалось подключиться к порту {self.port}. {e}")
            return False

    def disconnect(self):
        """Отключение от COM-порта."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            logger.info(f"Подключение к порту {self.port} закрыто")

    def _calculate_checksum(self, packet: bytearray) -> int:
        """
        Рассчитывает контрольную сумму для пакета ТЭМ-104.
        
        Args:
            packet: Пакет данных
            
        Returns:
            Контрольная сумма
        """
        return (~sum(packet) & 0xFF)

    def _create_request(self, address: int, cgrp: int, cmd: int, data: Optional[list] = None) -> bytearray:
        """
        Создает пакет запроса для отправки устройству.
        
        Args:
            address: Адрес устройства (1-240)
            cgrp: Группа команд
            cmd: Команда
            data: Данные (опционально)
            
        Returns:
            Пакет запроса в формате bytearray
        """
        if data is None:
            data = []
        
        # Инвертируем адрес для защиты от ошибок
        inv_address = ~address & 0xFF
        
        # Формируем пакет: [SIG][ADDR][!ADDR][CGRP][CMD][LEN][DATA...]
        packet = [0x55, address, inv_address, cgrp, cmd, len(data)]
        packet.extend(data)
        
        # Добавляем контрольную сумму
        packet.append(self._calculate_checksum(packet))
        return bytearray(packet)

    def _send_and_receive(self, request_packet: bytearray) -> Optional[bytearray]:
        """
        Отправляет пакет и получает ответ от устройства.
        Выполняет проверку корректности ответа.
        
        Args:
            request_packet: Пакет запроса
            
        Returns:
            Данные ответа или None в случае ошибки
        """
        if not self.ser or not self.ser.is_open:
            logger.error("Ошибка: Порт не открыт. Вызовите connect().")
            return None

        try:
            # Очищаем буфер входа перед отправкой
            self.ser.reset_input_buffer()
            
            # Отправляем пакет
            self.ser.write(request_packet)
            logger.debug(f"-> Отправлено: {' '.join(f'{b:02X}' for b in request_packet)}")

            # Читаем ответ (максимум 262 байта: заголовок + данные + контрольная сумма)
            response_bytes = self.ser.read(262)

            if not response_bytes:
                logger.warning("<- Ответ: Устройство не ответило.")
                return None

            logger.debug(f"<- Получено: {' '.join(f'{b:02X}' for b in response_bytes)}")

            # Проверяем корректность ответа
            if len(response_bytes) < 6:
                logger.error("Ошибка ответа: Слишком короткий ответ.")
                return None

            # Проверяем стартовый байт
            if response_bytes[0] != 0xAA:
                logger.error("Ошибка ответа: Неверный стартовый байт.")
                return None

            # Проверяем контрольную сумму
            if self._calculate_checksum(response_bytes[:-1]) != response_bytes[-1]:
                logger.error("Ошибка ответа: Неверная контрольная сумма.")
                return None
                
            # Извлекаем данные
            length = response_bytes[5]
            data = response_bytes[6:-1]

            if len(data) != length:
                logger.error("Ошибка ответа: Длина данных не совпадает с заявленной в пакете.")
                return None

            return data

        except serial.SerialException as e:
            logger.error(f"Ошибка связи: {e}")
            return None

    def identify_device(self, address: int) -> Optional[str]:
        """
        Идентификация устройства по адресу.
        
        Args:
            address: Адрес устройства
            
        Returns:
            Имя устройства или None в случае ошибки
        """
        logger.info(f"[Шаг 1] Идентификация устройства с адресом {address}...")
        request = self._create_request(address, 0x00, 0x00)
        response_data = self._send_and_receive(request)

        if response_data:
            try:
                device_name = response_data.decode('ascii', errors='ignore').strip()
                logger.info(f"Устройство ответило: {device_name}")
                return device_name
            except UnicodeDecodeError as e:
                logger.error(f"Ошибка декодирования имени устройства: {e}")
                return None
        else:
            logger.warning("Устройство не ответило на команду идентификации.")
            return None

    def __enter__(self):
        """Поддержка контекстного менеджера."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Автоматическое закрытие соединения при выходе из контекста."""
        self.disconnect()


class Tem104Protocol:
    """
    Протокол-специфичный класс для работы с ТЭМ-104/104-1/ТЭСМАРТ.
    Реализует чтение данных для старых моделей счетчиков.
    """
    
    def __init__(self, driver: TemDriver, address: int):
        """
        Инициализация протокола.
        
        Args:
            driver: Экземпляр TemDriver
            address: Адрес устройства
        """
        self.driver = driver
        self.address = address
        logger.info(f"Инициализирован Tem104Protocol для адреса {address}")

    def _bcd_to_dec(self, bcd: int) -> int:
        """
        Преобразует байт BCD в десятичное число.
        
        Args:
            bcd: Байт в BCD формате
            
        Returns:
            Десятичное число
        """
        return (bcd >> 4) * 10 + (bcd & 0x0F)

    def read_datetime(self) -> Optional[datetime]:
        """
        Читает текущее время с устройства.
        
        Returns:
            Объект datetime или None в случае ошибки
        """
        logger.info(f"[Шаг 2] Чтение времени с устройства...")
        
        # Команда 0F02, адрес 0x0010, 10 байт (для старых моделей)
        request = self.driver._create_request(self.address, 0x0F, 0x02, [0x10, 0x0A])
        data = self.driver._send_and_receive(request)

        if data and len(data) >= 10:
            try:
                # Разбор BCD времени для старых моделей
                sec = self._bcd_to_dec(data[0])
                minute = self._bcd_to_dec(data[2])  # Пропускаем неиспользуемый байт
                hour = self._bcd_to_dec(data[4])
                day = self._bcd_to_dec(data[7])
                month = self._bcd_to_dec(data[8])
                year = 2000 + self._bcd_to_dec(data[9])
                
                dt = datetime(year, month, day, hour, minute, sec)
                logger.info(f"Время с устройства: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                return dt
            except (ValueError, IndexError) as e:
                logger.error(f"Ошибка разбора времени: {e}")
                return None
        
        logger.warning("Не удалось прочитать время с устройства.")
        return None

    def read_current_values(self) -> Optional[Dict[str, float]]:
        """
        Читает мгновенные параметры (температуры, расходы).
        
        Returns:
            Словарь с мгновенными параметрами или None в случае ошибки
        """
        logger.info(f"[Шаг 3] Чтение мгновенных (текущих) параметров...")
        
        # Команда 0C01, адрес RAM 0x2200, 116 байт
        request = self.driver._create_request(self.address, 0x0C, 0x01, [0x22, 0x00, 116])
        data = self.driver._send_and_receive(request)

        if data and len(data) >= 100:
            try:
                # Разбор float значений в формате Big-Endian
                t1 = struct.unpack('>f', data[0:4])[0]
                t2 = struct.unpack('>f', data[4:8])[0]
                flow1 = struct.unpack('>f', data[64:68])[0]
                power1 = struct.unpack('>f', data[96:100])[0]
                
                result = {
                    't1': round(t1, 2),
                    't2': round(t2, 2),
                    'flow1': round(flow1, 3),
                    'power1': round(power1, 4)
                }
                
                logger.info("Мгновенные параметры:")
                for key, value in result.items():
                    logger.info(f"  {key}: {value}")
                return result
                
            except (struct.error, IndexError) as e:
                logger.error(f"Ошибка разбора мгновенных параметров: {e}")
                return None
        
        logger.warning("Не удалось прочитать мгновенные параметры с устройства.")
        return None
        
    def read_total_values(self) -> Optional[Dict[str, float]]:
        """
        Читает накопленные итоги устройства.
        
        Returns:
            Словарь с накопленными итогами или None в случае ошибки
        """
        logger.info(f"[Шаг 4] Чтение накопленных итогов...")
        
        # Команда 0F01, адрес конфигурации 0x0200, 256 байт
        request = self.driver._create_request(self.address, 0x0F, 0x01, [0x02, 0x00, 0xFF])
        data = self.driver._send_and_receive(request)

        if data and len(data) >= 120:
            try:
                # Разбор итоговых значений
                # V1 (объем 1) - целая часть (long) + дробная часть (float)
                v1_h = struct.unpack('>L', data[8:12])[0]
                v1_l = struct.unpack('>f', data[56:60])[0]
                v1_total = v1_h + v1_l

                # Q1 (энергия 1) - целая часть (long) + дробная часть (float)
                q1_h = struct.unpack('>L', data[40:44])[0]
                q1_l = struct.unpack('>f', data[88:92])[0]
                q1_total = q1_h + q1_l
                
                result = {
                    'V1_total': round(v1_total, 3),
                    'Q1_total': round(q1_total, 4)
                }
                
                logger.info("Накопленные итоги:")
                for key, value in result.items():
                    logger.info(f"  {key}: {value}")
                return result
                
            except (struct.error, IndexError) as e:
                logger.error(f"Ошибка разбора накопленных итогов: {e}")
                return None
        
        logger.warning("Не удалось прочитать накопленные итоги с устройства.")
        return None


class Tem104MProtocol:
    """
    Протокол-специфичный класс для работы с ТЭМ-104М/104М-1.
    Реализует чтение данных для новых моделей счетчиков.
    """
    
    def __init__(self, driver: TemDriver, address: int):
        """
        Инициализация протокола.
        
        Args:
            driver: Экземпляр TemDriver
            address: Адрес устройства
        """
        self.driver = driver
        self.address = address
        logger.info(f"Инициализирован Tem104MProtocol для адреса {address}")

    def _bcd_to_dec(self, bcd: int) -> int:
        """
        Преобразует байт BCD в десятичное число.
        
        Args:
            bcd: Байт в BCD формате
            
        Returns:
            Десятичное число
        """
        return (bcd >> 4) * 10 + (bcd & 0x0F)

    def read_datetime(self) -> Optional[datetime]:
        """
        Читает текущее время с устройства (новые модели).
        
        Returns:
            Объект datetime или None в случае ошибки
        """
        logger.info(f"[Шаг 2] Чтение времени с устройства (новые модели)...")
        
        # Команда 0F02, адрес 0x0000, 7 байт (для новых моделей)
        request = self.driver._create_request(self.address, 0x0F, 0x02, [0x00, 0x07])
        data = self.driver._send_and_receive(request)

        if data and len(data) >= 7:
            try:
                # Разбор десятичного времени для новых моделей
                sec = data[0]
                minute = data[1]
                hour = data[2]
                day = data[3]
                month = data[4]
                year = 2000 + data[5]
                
                dt = datetime(year, month, day, hour, minute, sec)
                logger.info(f"Время с устройства: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                return dt
            except (ValueError, IndexError) as e:
                logger.error(f"Ошибка разбора времени: {e}")
                return None
        
        logger.warning("Не удалось прочитать время с устройства.")
        return None

    def read_current_values(self) -> Optional[Dict[str, float]]:
        """
        Читает мгновенные параметры (новые модели).
        
        Returns:
            Словарь с мгновенными параметрами или None в случае ошибки
        """
        logger.info(f"[Шаг 3] Чтение мгновенных параметров (новые модели)...")
        
        # Команда 0C01, адрес RAM 0x4000, 116 байт
        request = self.driver._create_request(self.address, 0x0C, 0x01, [0x40, 0x00, 116])
        data = self.driver._send_and_receive(request)

        if data and len(data) >= 100:
            try:
                # Разбор float значений в формате Big-Endian
                t1 = struct.unpack('>f', data[0:4])[0]
                t2 = struct.unpack('>f', data[4:8])[0]
                flow1 = struct.unpack('>f', data[32:36])[0]  # Смещение для новых моделей
                power1 = struct.unpack('>f', data[96:100])[0]
                
                result = {
                    't1': round(t1, 2),
                    't2': round(t2, 2),
                    'flow1': round(flow1, 3),
                    'power1': round(power1, 4)
                }
                
                logger.info("Мгновенные параметры:")
                for key, value in result.items():
                    logger.info(f"  {key}: {value}")
                return result
                
            except (struct.error, IndexError) as e:
                logger.error(f"Ошибка разбора мгновенных параметров: {e}")
                return None
        
        logger.warning("Не удалось прочитать мгновенные параметры с устройства.")
        return None
        
    def read_total_values(self) -> Optional[Dict[str, float]]:
        """
        Читает накопленные итоги (новые модели).
        
        Returns:
            Словарь с накопленными итогами или None в случае ошибки
        """
        logger.info(f"[Шаг 4] Чтение накопленных итогов (новые модели)...")
        
        # Команда 0F01, адрес конфигурации 0x0180, 256 байт
        request = self.driver._create_request(self.address, 0x0F, 0x01, [0x01, 0x80, 0xFF])
        data = self.driver._send_and_receive(request)

        if data and len(data) >= 120:
            try:
                # Разбор итоговых значений для новых моделей
                # V1 (объем 1) - целая часть (long) + дробная часть (float)
                v1_h = struct.unpack('>L', data[8:12])[0]
                v1_l = struct.unpack('>f', data[24:28])[0]  # Смещение для новых моделей
                v1_total = v1_h + v1_l

                # Q1 (энергия 1) - целая часть (long) + дробная часть (float)
                q1_h = struct.unpack('>L', data[16:20])[0]
                q1_l = struct.unpack('>f', data[32:36])[0]  # Смещение для новых моделей
                q1_total = q1_h + q1_l
                
                result = {
                    'V1_total': round(v1_total, 3),
                    'Q1_total': round(q1_total, 4)
                }
                
                logger.info("Накопленные итоги:")
                for key, value in result.items():
                    logger.info(f"  {key}: {value}")
                return result
                
            except (struct.error, IndexError) as e:
                logger.error(f"Ошибка разбора накопленных итогов: {e}")
                return None
        
        logger.warning("Не удалось прочитать накопленные итоги с устройства.")
        return None


def main():
    """
    Главная функция для демонстрации работы с устройством.
    """
    # --- Настройки ---
    # Замените на ваш COM-порт и адрес устройства
    PORT = 'COM3'  # Для Windows. Для Linux/macOS может быть '/dev/ttyUSB0'
    DEVICE_ADDRESS = 1
    
    logger.info("=== Демонстрация работы с ТЭМ-104 ===")
    
    # Используем контекстный менеджер для автоматического закрытия соединения
    with TemDriver(port=PORT) as driver:
        if not driver.ser:
            logger.error("Не удалось подключиться к устройству.")
            return

        # 1. Идентификация устройства
        device_name = driver.identify_device(DEVICE_ADDRESS)
        
        if not device_name:
            logger.error("Устройство не найдено. Проверьте подключение и адрес устройства.")
            return

        # 2. Выбор протокола в зависимости от модели
        if 'M' in device_name:
            logger.info("Используется протокол для новых моделей (ТЭМ-104М/104М-1)")
            protocol = Tem104MProtocol(driver, DEVICE_ADDRESS)
        else:
            logger.info("Используется протокол для старых моделей (ТЭМ-104/104-1)")
            protocol = Tem104Protocol(driver, DEVICE_ADDRESS)
            
        # 3. Последовательное выполнение операций
        try:
            # Чтение времени
            dt = protocol.read_datetime()
            if dt:
                logger.info(f"✓ Время успешно прочитано: {dt}")
            
            # Чтение мгновенных параметров
            current = protocol.read_current_values()
            if current:
                logger.info("✓ Мгновенные параметры успешно прочитаны")
            
            # Чтение накопленных итогов
            totals = protocol.read_total_values()
            if totals:
                logger.info("✓ Накопленные итоги успешно прочитаны")
                
        except Exception as e:
            logger.error(f"Ошибка при чтении данных: {e}")

        logger.info("=== Опрос устройства завершен! ===")


if __name__ == "__main__":
    main() 