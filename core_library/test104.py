# -*- coding: utf-8 -*-
import socket
import serial
import time
import struct
from typing import Optional, Literal
import sys

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
    """Удобная функция для печати байт в HEX-формате. Не выводит в GUI."""
    if hasattr(sys.stdout, 'text_widget'):
        return
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
        """
        Опрос счетчика и возврат основных данных (Q, M1, T1, T2, G1, T_nar) в виде словаря.
        """
        if not self.protocol_type:
            self.protocol_type = self.auto_detect_protocol()
            if not self.protocol_type:
                raise RuntimeError("Не удалось определить протокол. Укажите его вручную.")
        time.sleep(0.5)
        if self.protocol_type == 'ARVAS_M1': return self._get_arvas_m1_data()
        elif self.protocol_type == 'ARVAS_M': return self._get_arvas_m_data()
        elif self.protocol_type == 'ARVAS_LEGACY_1': return self._get_arvas_legacy_1_data()
        elif self.protocol_type == 'ARVAS_LEGACY': return self._get_arvas_legacy_data()
        elif self.protocol_type == 'TESMART': return self._get_tesmart_data()
        else:
            raise NotImplementedError(f"Логика чтения для {self.protocol_type} не реализована.")

    # --- Методы для возврата данных по каждому протоколу ---
    def _get_arvas_m1_data(self):
        data = {}
        # Итоги
        addr_h, addr_l = (0x0180 >> 8) & 0xFF, 0x0180 & 0xFF
        packet = self._create_packet(CMD_GROUP_READ_MEM, CMD_READ_CONFIG, data=bytearray([addr_h, addr_l, 0xFF]))
        payload = self._send_and_receive(packet)
        if payload:
            try:
                data['Q'] = struct.unpack('>f', payload[0x20:0x24])[0] + struct.unpack('>L', payload[0x10:0x14])[0]
                data['M1'] = struct.unpack('>f', payload[0x1C:0x20])[0] + struct.unpack('>L', payload[0x0C:0x10])[0]
                data['T_nar'] = struct.unpack('>L', payload[0x30:0x34])[0]
            except Exception: pass
        # Мгновенные
        addr_h, addr_l = (0x4000 >> 8) & 0xFF, 0x4000 & 0xFF
        packet = self._create_packet(CMD_GROUP_READ_RAM, CMD_READ_RAM, data=bytearray([addr_h, addr_l, 0xFF]))
        payload = self._send_and_receive(packet)
        if payload:
            try:
                data['T1'] = struct.unpack('>f', payload[0x00:0x04])[0]
                data['T2'] = struct.unpack('>f', payload[0x04:0x08])[0]
                data['G1'] = struct.unpack('>f', payload[0x20:0x24])[0]
            except Exception: pass
        return data

    def _get_arvas_m_data(self):
        data = {}
        addr_h, addr_l = (0x0800 >> 8) & 0xFF, 0x0800 & 0xFF
        packet = self._create_packet(CMD_GROUP_READ_MEM, CMD_READ_CONFIG, data=bytearray([addr_h, addr_l, 0xFF]))
        payload = self._send_and_receive(packet)
        if payload:
            try:
                data['Q'] = struct.unpack('>f', payload[0x68:0x6C])[0] + struct.unpack('>L', payload[0x28:0x2C])[0]
                data['M1'] = struct.unpack('>f', payload[0x58:0x5C])[0] + struct.unpack('>L', payload[0x18:0x1C])[0]
                data['T_nar'] = struct.unpack('>L', payload[0xA0:0xA4])[0]
            except Exception: pass
        addr_h, addr_l = (0x0000 >> 8) & 0xFF, 0x0000 & 0xFF
        packet = self._create_packet(CMD_GROUP_READ_RAM, CMD_READ_RAM, data=bytearray([addr_h, addr_l, 0xFF]))
        payload = self._send_and_receive(packet)
        if payload:
            try:
                data['T1'] = struct.unpack('>f', payload[0x00:0x04])[0]
                data['T2'] = struct.unpack('>f', payload[0x04:0x08])[0]
                data['G1'] = struct.unpack('>f', payload[0x40:0x44])[0]
            except Exception: pass
        return data

    def _get_arvas_legacy_1_data(self):
        data = {}
        addr_h, addr_l = (0x0100 >> 8) & 0xFF, 0x0100 & 0xFF
        packet = self._create_packet(CMD_GROUP_READ_MEM, CMD_READ_CONFIG, data=bytearray([addr_h, addr_l, 0xFF]))
        payload = self._send_and_receive(packet)
        if payload:
            try:
                data['Q'] = struct.unpack('>f', payload[0x58:0x5C])[0] + struct.unpack('>L', payload[0x54:0x58])[0]
                data['M1'] = struct.unpack('>f', payload[0x50:0x54])[0] + struct.unpack('>L', payload[0x4C:0x50])[0]
                data['T_nar'] = struct.unpack('>L', payload[0x60:0x64])[0]
            except Exception: pass
        addr_h, addr_l = (0x00B8 >> 8) & 0xFF, 0x00B8 & 0xFF
        packet = self._create_packet(CMD_GROUP_READ_RAM, CMD_READ_RAM, data=bytearray([addr_h, addr_l, 0xFF]))
        payload = self._send_and_receive(packet)
        if payload:
            try:
                data['T1'] = struct.unpack('>f', payload[0x08:0x0C])[0]
                data['T2'] = struct.unpack('>f', payload[0x0C:0x10])[0]
                data['G1'] = struct.unpack('>f', payload[0x00:0x04])[0]
            except Exception: pass
        return data

    def _get_arvas_legacy_data(self):
        data = {}
        addr_h, addr_l = (0x0200 >> 8) & 0xFF, 0x0200 & 0xFF
        packet = self._create_packet(CMD_GROUP_READ_MEM, CMD_READ_CONFIG, data=bytearray([addr_h, addr_l, 0xFF]))
        payload = self._send_and_receive(packet)
        if payload:
            try:
                data['Q'] = struct.unpack('>f', payload[0x28:0x2C])[0] + struct.unpack('>L', payload[0x58:0x5C])[0]
                data['M1'] = struct.unpack('>f', payload[0x18:0x1C])[0] + struct.unpack('>L', payload[0x48:0x4C])[0]
                data['T_nar'] = struct.unpack('>L', payload[0x6C:0x70])[0]
            except Exception: pass
        addr_h, addr_l = (0x2200 >> 8) & 0xFF, 0x2200 & 0xFF
        packet = self._create_packet(CMD_GROUP_READ_RAM, CMD_READ_RAM, data=bytearray([addr_h, addr_l, 0xFF]))
        payload = self._send_and_receive(packet)
        if payload:
            try:
                data['T1'] = struct.unpack('>f', payload[0x00:0x04])[0]
                data['T2'] = struct.unpack('>f', payload[0x04:0x08])[0]
                data['G1'] = struct.unpack('>f', payload[0x40:0x44])[0]
            except Exception: pass
        return data

    def _get_tesmart_data(self):
        data = {}
        full_payload = bytearray()
        for i in range(5):
            addr_h, addr_l = ((i * 0x100) >> 8) & 0xFF, (i * 0x100) & 0xFF
            packet = self._create_packet(CMD_GROUP_READ_MEM, CMD_READ_CONFIG, data=bytearray([addr_h, addr_l, 0xFF]))
            payload_part = self._send_and_receive(packet)
            if not payload_part:
                continue
            full_payload.extend(payload_part)
            time.sleep(0.2)
        try:
            k_v = self._get_tesmart_coeff(full_payload[0x02FA], 'volume')
            k_q = self._get_tesmart_coeff(full_payload[0x02FA], 'energy')
            data['Q'] = (struct.unpack('>L', full_payload[0x0378:0x037C])[0] + struct.unpack('>f', full_payload[0x0360:0x0364])[0]) / k_q
            data['M1'] = (struct.unpack('>L', full_payload[0x0348:0x034C])[0] + struct.unpack('>f', full_payload[0x0330:0x0334])[0]) / k_v
            data['T_nar'] = struct.unpack('>L', full_payload[0x0404:0x0408])[0]
            data['T1'] = struct.unpack('>f', full_payload[0x0200:0x0204])[0]
            data['T2'] = struct.unpack('>f', full_payload[0x0204:0x0208])[0]
            data['G1'] = struct.unpack('>f', full_payload[0x0288:0x028C])[0]
        except Exception:
            pass
        return data

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
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            time.sleep(0.1)
            print("Порт успешно открыт.")
        except serial.SerialException as e:
            self.ser = None
            raise ConnectionError(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось открыть COM-порт. {e}")

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
            data = client.read_all_data()
            print("\n--- Результаты опроса ---")
            for key, value in data.items():
                print(f"{key}: {value}")

    except (ValueError, TypeError):
        print("\nОшибка: введено некорректное числовое значение. Пожалуйста, перезапустите программу.")
    except Exception as e:
        print(f"\nПроизошла глобальная ошибка: {e}")
    finally:
        if client:
            client.disconnect()

if __name__ == "__main__":
    main()