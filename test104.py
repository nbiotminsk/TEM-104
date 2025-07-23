# -*- coding: utf-8 -*-
import socket
import serial
import time
import struct
from typing import Optional, Literal

# --- КОНСТАНТЫ ПРОТОКОЛА ---
REQUEST_START_BYTE = 0x55
RESPONSE_START_BYTE = 0xAA
CMD_GROUP_CONNECTION = 0x00
CMD_GROUP_READ_MEM = 0x0F
CMD_GROUP_READ_RAM = 0x0C
CMD_IDENTIFY = 0x00
CMD_READ_CONFIG = 0x01
CMD_READ_RTC = 0x02
CMD_READ_RAM = 0x01

ProtocolType = Literal['ARVAS_LEGACY', 'ARVAS_LEGACY_1', 'TESMART', 'ARVAS_M', 'ARVAS_M1']

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def print_hex(data: bytes or bytearray, prefix: str = ""):
    """Удобная функция для печати байт в HEX-формате."""
    print(f"{prefix}{' '.join(f'{b:02X}' for b in data)}")

def bcd_to_int(bcd_byte: int) -> int:
    """Преобразует один байт BCD в integer."""
    return (bcd_byte >> 4) * 10 + (bcd_byte & 0x0F)

# --- БАЗОВЫЙ КЛАСС С ЛОГИКОЙ ПРОТОКОЛА ---
class TEM104_Base_Client:
    """
    Базовый класс, содержащий всю логику протокола ТЭМ-104,
    независимую от способа подключения (COM или TCP).
    """
    def __init__(self, address: int, protocol: Optional[ProtocolType] = None):
        self.address = address
        self.protocol_type = protocol

    def connect(self):
        raise NotImplementedError("Метод connect должен быть реализован в дочернем классе.")

    def disconnect(self):
        raise NotImplementedError("Метод disconnect должен быть реализован в дочернем классе.")

    def _send_and_receive(self, packet: bytearray) -> Optional[bytearray]:
        raise NotImplementedError("Метод _send_and_receive должен быть реализован в дочернем классе.")

    def _create_packet(self, group: int, cmd: int, data: bytes = b'') -> bytearray:
        inv_addr = (~self.address) & 0xFF
        packet = bytearray([REQUEST_START_BYTE, self.address, inv_addr, group, cmd, len(data)]) + data
        packet.append((~sum(packet)) & 0xFF)
        return packet

    def auto_detect_protocol(self) -> Optional[ProtocolType]:
        print("\n--- 1. Автоматическое определение протокола ---")
        packet = self._create_packet(CMD_GROUP_CONNECTION, CMD_IDENTIFY)
        payload = self._send_and_receive(packet)
        if payload:
            device_name = payload.decode('ascii', errors='ignore').strip()
            print(f"Устройство ответило: '{device_name}'")
            if "TEM-104M-1" in device_name: return 'ARVAS_M1'
            if "TEM-104M" in device_name: return 'ARVAS_M'
            if "TSM104" in device_name: return 'TESMART'
            if "TEM-104-1" in device_name: return 'ARVAS_LEGACY_1'
            if "TEM-104" in device_name: return 'ARVAS_LEGACY'
        print("Не удалось определить модель по ответу.")
        return None

    def read_all_data(self):
        if not self.protocol_type:
            self.protocol_type = self.auto_detect_protocol()
            if not self.protocol_type:
                raise RuntimeError("Не удалось определить протокол. Укажите его вручную.")
        
        print(f"\nИспользуется протокол: {self.protocol_type}")
        time.sleep(0.5)

        # Маршрутизатор: вызываем нужный метод для определенного протокола
        if self.protocol_type == 'ARVAS_M1': self._read_arvas_m1_data()
        elif self.protocol_type == 'ARVAS_M': self._read_arvas_m_data()
        elif self.protocol_type == 'ARVAS_LEGACY_1': self._read_arvas_legacy_1_data()
        elif self.protocol_type == 'ARVAS_LEGACY': self._read_arvas_legacy_data()
        elif self.protocol_type == 'TESMART': self._read_tesmart_data()
        else:
            print(f"Логика чтения для {self.protocol_type} не реализована.")
    
    # --- БЛОКИ ЧТЕНИЯ ДАННЫХ ДЛЯ КАЖДОГО ПРОТОКОЛА ---

    def _read_arvas_m1_data(self):
        """
        Протокол: ARVAS_M1 (ТЭМ-104М-1)
        Источник: TEM-104M1_PO_v_1_1.pdf
        """
        print("\n--- Чтение данных (протокол ARVAS_M1) ---")
        # Время: команда 0F02, адрес 0x00 (стр. 15)
        self._read_rtc_decimal()
        time.sleep(0.5)
        # Итоги: команда 0F01, базовый адрес 0x0180 (стр. 10, 14)
        self._read_totals(CMD_READ_CONFIG, 0x0180, {'h_v': 0x08, 'h_m': 0x0C, 'h_q': 0x10, 'i_v': 0x18, 'i_m': 0x1C, 'i_q': 0x20})
        time.sleep(0.5)
        # Мгновенные: команда 0C01, базовый адрес 0x4000 (стр. 15)
        self._read_instantaneous(0x4000, {'t': 0x00, 'pwr': 0x28}, num_temps=2)

    def _read_arvas_m_data(self):
        """
        Протокол: ARVAS_M (ТЭМ-104М)
        Источник: TEM104M_PO_v1-3.pdf
        """
        print("\n--- Чтение данных (протокол ARVAS_M) ---")
        # Время: команда 0F02, адрес 0x00 (стр. 15)
        self._read_rtc_decimal()
        time.sleep(0.5)
        # Итоги: команда 0F01, базовый адрес 0x0800 (стр. 10, 14)
        self._read_totals(CMD_READ_CONFIG, 0x0800, {'h_v': 0x08, 'h_m': 0x18, 'h_q': 0x28, 'i_v': 0x48, 'i_m': 0x58, 'i_q': 0x68})
        time.sleep(0.5)
        # Мгновенные: команда 0C01, базовый адрес 0x0000 (стр. 15)
        self._read_instantaneous(0x0000, {'t': 0x00, 'pwr': 0x60}, num_temps=4)

    def _read_arvas_legacy_1_data(self):
        """
        Протокол: ARVAS_LEGACY_1 (ТЭМ-104-1)
        Источник: tem-104-1_po.pdf
        """
        print("\n--- Чтение данных (протокол ARVAS_LEGACY_1) ---")
        # Время: команда 0F02, адрес 0x00 (стр. 11)
        self._read_rtc_bcd()
        time.sleep(0.5)
        # Итоги: команда 0F01, базовый адрес 0x0100 (стр. 10, параметр VH на 0x0144)
        self._read_totals(CMD_READ_CONFIG, 0x0100, {'h_v': 0x44, 'i_v': 0x48, 'h_m': 0x4C, 'i_m': 0x50, 'h_q': 0x54, 'i_q': 0x58})
        time.sleep(0.5)
        # Мгновенные: команда 0C01, базовый адрес 0x00B8 (стр. 12, параметр tmp на 0x0C0)
        self._read_instantaneous(0x00B8, {'t': 0x08, 'pwr': -1}, num_temps=2)

    def _read_arvas_legacy_data(self):
        """
        Протокол: ARVAS_LEGACY (старый ТЭМ-104)
        Источник: TEM-104_PO.pdf
        """
        print("\n--- Чтение данных (протокол ARVAS_LEGACY) ---")
        # Время: команда 0F02, адрес 0x10 (стр. 12)
        self._read_rtc_bcd()
        time.sleep(0.5)
        # Итоги: команда 0F01, базовый адрес 0x0200 (стр. 10, структура SysInt_copy1)
        self._read_totals(CMD_READ_CONFIG, 0x0200, {'h_v': 0x38, 'i_v': 0x08, 'h_m': 0x48, 'i_m': 0x18, 'h_q': 0x58, 'i_q': 0x28})
        time.sleep(0.5)
        # Мгновенные: команда 0C01, базовый адрес 0x2200 (стр. 13)
        self._read_instantaneous(0x2200, {'t': 0x00, 'pwr': 0x60}, num_temps=4)
        
    def _read_tesmart_data(self):
        """
        Протокол: TESMART (ТЭМ-104 ТЭСМАРТ)
        Источник: tem-104(tesmart)_po.pdf
        """
        print("\n--- Чтение данных (протокол ТЭСМАРТ) ---")
        # В этой модели все данные лежат в одном большом блоке памяти таймера 2К.
        # Читаем его по частям и собираем в единый payload.
        full_payload = bytearray()
        for i in range(5):
            addr_h, addr_l = i, 0x00
            packet = self._create_packet(CMD_GROUP_READ_MEM, CMD_READ_CONFIG, data=bytearray([addr_h, addr_l, 0xFF]))
            payload_part = self._send_and_receive(packet)
            if not payload_part:
                print("ОШИБКА: не удалось прочитать все блоки памяти ТЭСМАРТ.")
                return
            full_payload.extend(payload_part)
            time.sleep(0.5)
        self._parse_tesmart_payload(full_payload)

    def _parse_tesmart_payload(self, payload: bytes):
        """Разбор единого блока данных для протокола ТЭСМАРТ."""
        try:
            print("\n--- Разбор данных ТЭСМАРТ ---")
            # Время: адрес 0x0482 (стр. 8)
            ss, mm, hh, dd, MM, YY = (bcd_to_int(payload[a]) for a in range(0x482, 0x488))
            print(f"Текущее время: 20{YY:02d}-{MM:02d}-{dd:02d} {hh:02d}:{mm:02d}:{ss:02d}")
            
            # Коэффициенты для расчета итогов: адрес 0x02FA (стр. 8, 11)
            comma_v = payload[0x02FA:0x0300]
            k_v, k_q = ([self._get_tesmart_coeff(c, 'volume') for c in comma_v], [self._get_tesmart_coeff(c, 'energy') for c in comma_v])
            
            # Итоги: базовый адрес 0x0300 (стр. 8)
            i_vol, h_vol = struct.unpack('>6f', payload[0x0300:0x0318]), struct.unpack('>6L', payload[0x0318:0x0330])
            i_mass, h_mass = struct.unpack('>6f', payload[0x0330:0x0348]), struct.unpack('>6L', payload[0x0348:0x0360])
            i_energy, h_energy = struct.unpack('>6f', payload[0x0360:0x0378]), struct.unpack('>6L', payload[0x0378:0x0390])
            
            total_v = [(h + i) / k for h, i, k in zip(h_vol, i_vol, k_v)]
            total_m = [(h + i) / k for h, i, k in zip(h_mass, i_mass, k_v)]
            total_q = [(h + i) / k for h, i, k in zip(h_energy, i_energy, k_q)]

            print("\nНакопленные итоги:")
            print(f"  Объем (V, м³): {[f'{v:.3f}' for v in total_v]}")
            print(f"  Масса (M, т): {[f'{m:.3f}' for m in total_m]}")
            print(f"  Энергия (Q, МВт*ч): {[f'{q:.4f}' for q in total_q]}")
        except (struct.error, IndexError) as e: print(f"ОШИБКА разбора данных ТЭСМАРТ: {e}")

    # --- УНИФИЦИРОВАННЫЕ МЕТОДЫ ЧТЕНИЯ ---

    def _read_rtc_decimal(self):
        """Читает время в десятичном формате (для моделей М и М-1)."""
        print("\n--- 2a. Чтение времени (Decimal) ---")
        packet = self._create_packet(CMD_GROUP_READ_MEM, CMD_READ_RTC, data=b'\x00\x07')
        payload = self._send_and_receive(packet)
        if payload and len(payload) >= 6:
            ss, mm, hh, dd, MM, YY = payload[:6]
            print(f"Успешно: Текущее время: 20{YY:02d}-{MM:02d}-{dd:02d} {hh:02d}:{mm:02d}:{ss:02d}")

    def _read_rtc_bcd(self):
        """Читает время в BCD формате, учитывая различия в старых протоколах."""
        print("\n--- 2a. Чтение времени (BCD) ---")
        if self.protocol_type == 'ARVAS_LEGACY':
            req_data = bytearray([0x10, 0x0A])
            packet = self._create_packet(CMD_GROUP_READ_MEM, CMD_READ_RTC, data=req_data)
            payload = self._send_and_receive(packet)
            if payload and len(payload) >= 10:
                ss, mm, hh = bcd_to_int(payload[0]), bcd_to_int(payload[2]), bcd_to_int(payload[4])
                dd, MM, YY = bcd_to_int(payload[7]), bcd_to_int(payload[8]), bcd_to_int(payload[9])
                print(f"Успешно: Текущее время: 20{YY:02d}-{MM:02d}-{dd:02d} {hh:02d}:{mm:02d}:{ss:02d}")
        elif self.protocol_type == 'ARVAS_LEGACY_1':
            req_data = bytearray([0x00, 0x07])
            packet = self._create_packet(CMD_GROUP_READ_MEM, CMD_READ_RTC, data=req_data)
            payload = self._send_and_receive(packet)
            if payload and len(payload) >= 7:
                ss, mm, hh = bcd_to_int(payload[0]), bcd_to_int(payload[1]), bcd_to_int(payload[2])
                dd, MM, YY = bcd_to_int(payload[4]), bcd_to_int(payload[5]), bcd_to_int(payload[6])
                print(f"Успешно: Текущее время: 20{YY:02d}-{MM:02d}-{dd:02d} {hh:02d}:{mm:02d}:{ss:02d}")

    def _read_totals(self, command: int, base_addr: int, offsets: dict):
        """Унифицированный метод чтения итоговых значений."""
        print("\n--- 2b. Чтение накопленных итогов ---")
        addr_h, addr_l = (base_addr >> 8) & 0xFF, base_addr & 0xFF
        packet = self._create_packet(CMD_GROUP_READ_MEM, command, data=bytearray([addr_h, addr_l, 0xFF]))
        payload = self._send_and_receive(packet)
        if payload:
            try:
                h_v, i_v = struct.unpack('>L', payload[offsets['h_v']:offsets['h_v']+4])[0], struct.unpack('>f', payload[offsets['i_v']:offsets['i_v']+4])[0]
                h_m, i_m = struct.unpack('>L', payload[offsets['h_m']:offsets['h_m']+4])[0], struct.unpack('>f', payload[offsets['i_m']:offsets['i_m']+4])[0]
                h_q, i_q = struct.unpack('>L', payload[offsets['h_q']:offsets['h_q']+4])[0], struct.unpack('>f', payload[offsets['i_q']:offsets['i_q']+4])[0]
                print("Успешно: Накопленные итоги прочитаны.")
                print(f"  Объем (V, м³): {h_v + i_v:.3f}")
                print(f"  Масса (M, т): {h_m + i_m:.3f}")
                print(f"  Энергия (Q, Гкал/МВт*ч): {h_q + i_q:.4f}")
            except (struct.error, IndexError) as e: print(f"ОШИБКА разбора итогов: {e}")

    def _read_instantaneous(self, base_addr: int, offsets: dict, num_temps: int):
        """Унифицированный метод чтения мгновенных значений."""
        print("\n--- 2c. Чтение мгновенных параметров ---")
        addr_h, addr_l = (base_addr >> 8) & 0xFF, base_addr & 0xFF
        packet = self._create_packet(CMD_GROUP_READ_RAM, CMD_READ_RAM, data=bytearray([addr_h, addr_l, 0xFF]))
        payload = self._send_and_receive(packet)
        if payload:
            try:
                temps = struct.unpack(f'>{num_temps}f', payload[offsets['t']:offsets['t'] + 4 * num_temps])
                print("Успешно: Мгновенные параметры прочитаны.")
                print(f"  Температуры (°C): {[f'{t:.2f}' for t in temps]}")
                if offsets['pwr'] != -1:
                    power = struct.unpack('>f', payload[offsets['pwr']:offsets['pwr']+4])[0]
                    print(f"  Мощность (Гкал/ч): {power:.4f}")
                else:
                    print("  Мощность (Q): не доступна в этом запросе для данной модели.")
            except (struct.error, IndexError) as e: print(f"ОШИБКА разбора мгновенных параметров: {e}")
            
    @staticmethod
    def _get_tesmart_coeff(comma_val: int, param_type: str) -> int:
        coeffs = {'energy': {6: 100000, 5: 10000, 4: 1000, 3: 100, 2: 10}, 'volume': {5: 1000, 4: 100, 3: 10}}
        return coeffs.get(param_type, {}).get(comma_val, 1)

# --- КЛАССЫ ТРАНСПОРТНОГО УРОВНЯ ---
class TEM104_Serial_Client(TEM104_Base_Client):
    """Реализация транспортного уровня для локального COM-порта."""
    def __init__(self, port: str, baudrate: int, address: int, **kwargs):
        super().__init__(address, **kwargs)
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.timeout = kwargs.get('timeout', 2.0)

    def connect(self):
        if self.ser and self.ser.is_open: return
        try:
            print(f"Попытка подключения к {self.port} со скоростью {self.baudrate}...")
            self.ser = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=self.timeout)
            print("Порт успешно открыт.")
        except serial.SerialException as e:
            raise ConnectionError(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось открыть порт {self.port}. {e}")

    def disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("\nПорт закрыт.")

    def _send_and_receive(self, packet: bytearray) -> Optional[bytearray]:
        if not self.ser or not self.ser.is_open: raise ConnectionError("Порт не открыт.")
        self.ser.reset_input_buffer()
        self.ser.write(packet)
        print_hex(packet, "-> Отправка: ")
        # "Умное" чтение: сначала читаем заголовок (6 байт)
        header = self.ser.read(6)
        if len(header) < 6:
            print("ОШИБКА: не получен заголовок ответа.")
            return None
        # Длина полезной нагрузки в 6-м байте
        payload_len = header[5]
        # Читаем payload и контрольную сумму
        payload_and_crc = self.ser.read(payload_len + 1)
        if len(payload_and_crc) < payload_len + 1:
            print("ОШИБКА: не получен полный ответ.")
            return None
        response = header + payload_and_crc
        print_hex(response, "<- Получено: ")
        if response[0] != RESPONSE_START_BYTE or response[1] != self.address or (sum(response) & 0xFF) != 0xFF:
            print("ОШИБКА: Неверный заголовок или контрольная сумма ответа.")
            return None
        return response[6:-1]

class TEM104_TCP_Client(TEM104_Base_Client):
    """Реализация транспортного уровня для сети TCP/IP."""
    def __init__(self, host: str, port: int, address: int, **kwargs):
        super().__init__(address, **kwargs)
        self.host = host
        self.port = port
        self.sock = None
        self.timeout = kwargs.get('timeout', 5.0)

    def connect(self):
        if self.sock: return
        try:
            print(f"Попытка подключения к {self.host}:{self.port}...")
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect((self.host, self.port))
            print("Соединение успешно установлено.")
        except socket.error as e:
            self.sock = None
            raise ConnectionError(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось подключиться к модему. {e}")

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.sock = None
            print("\nСоединение закрыто.")

    def _send_and_receive(self, packet: bytearray) -> Optional[bytearray]:
        if not self.sock: raise ConnectionError("Соединение не установлено.")
        try:
            print_hex(packet, "-> Отправка: ")
            self.sock.sendall(packet)
            # "Умное" чтение: сначала читаем заголовок (6 байт)
            header = b''
            while len(header) < 6:
                chunk = self.sock.recv(6 - len(header))
                if not chunk:
                    print("ОШИБКА: не получен заголовок ответа.")
                    return None
                header += chunk
            payload_len = header[5]
            # Читаем payload и контрольную сумму
            payload_and_crc = b''
            while len(payload_and_crc) < payload_len + 1:
                chunk = self.sock.recv(payload_len + 1 - len(payload_and_crc))
                if not chunk:
                    print("ОШИБКА: не получен полный ответ.")
                    return None
                payload_and_crc += chunk
            response = header + payload_and_crc
            print_hex(response, "<- Получено: ")
            if response[0] != RESPONSE_START_BYTE or response[1] != self.address or (sum(response) & 0xFF) != 0xFF:
                print("ОШИБКА: Неверный заголовок или контрольная сумма ответа.")
                return None
            return response[6:-1]
        except socket.timeout:
            print("ОШИБКА: Таймаут ожидания ответа от модема.")
            return None
        except socket.error as e:
            print(f"ОШИБКА СОКЕТА: {e}")
            self.disconnect()
            return None

# --- ГЛАВНЫЙ БЛОК ЗАПУСКА С ИНТЕРАКТИВНЫМ МЕНЮ ---
def main():
    """Основная функция, запускающая интерактивное меню для пользователя."""
    print("--- Утилита для опроса счетчиков ТЭМ-104 ---")
    
    client = None
    
    while True:
        choice = input("Как вы хотите подключиться?\n 1 - Локальный COM-порт\n 2 - Сеть TCP/IP (модем)\nВаш выбор: ").strip()
        if choice in ('1', '2'):
            break
        print("Неверный ввод. Пожалуйста, введите 1 или 2.")

    try:
        if choice == '1':
            port_name = input("Введите имя COM-порта (например, COM3): ").strip()
            baud_rate_str = input("Введите скорость (9600, 19200 и т.д.) [9600]: ").strip() or "9600"
            address_str = input("Введите сетевой адрес счетчика [1]: ").strip() or "1"
            baud_rate, address = int(baud_rate_str), int(address_str)
            client = TEM104_Serial_Client(port=port_name, baudrate=baud_rate, address=address)
        
        elif choice == '2':
            host = input("Введите IP-адрес модема: ").strip()
            port_str = input("Введите TCP-порт модема [5009]: ").strip() or "5009"
            address_str = input("Введите сетевой адрес счетчика [1]: ").strip() or "1"
            port, address = int(port_str), int(address_str)
            client = TEM104_TCP_Client(host=host, port=port, address=address)

        if client:
            client.connect()
            client.read_all_data()

    except (ValueError, TypeError):
        print("\nОшибка: введено некорректное числовое значение. Пожалуйста, перезапустите программу.")
    except Exception as e:
        print(f"\nПроизошла глобальная ошибка: {e}")
    finally:
        if client:
            client.disconnect()

if __name__ == "__main__":
    main()