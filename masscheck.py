# -*- coding: utf-8 -*-
import socket
import json
import os
import time
import struct
from typing import Optional, Literal, Dict, Any

# --- КОНСТАНТЫ ---
# Глобальные настройки для массового опроса
TCP_PORT = 5009
METER_ADDRESS = 1
JSON_FILENAME = "ip_list.json"

# Константы протокола (неизменны)
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
def bcd_to_int(bcd_byte: int) -> int:
    """Преобразует один байт BCD в integer."""
    return (bcd_byte >> 4) * 10 + (bcd_byte & 0x0F)

# --- ЛОГИКА ПРОТОКОЛА И ТРАНСПОРТА ---
class TEM104_Base_Client:
    """
    Базовый класс, содержащий всю логику протокола ТЭМ-104.
    """
    def __init__(self, address: int, protocol: Optional[ProtocolType] = None):
        self.address = address
        self.protocol_type = protocol

    def connect(self):
        raise NotImplementedError

    def disconnect(self):
        raise NotImplementedError

    def _send_and_receive(self, packet: bytearray) -> Optional[bytearray]:
        raise NotImplementedError

    def _create_packet(self, group: int, cmd: int, data: bytes = b'') -> bytearray:
        inv_addr = (~self.address) & 0xFF
        packet = bytearray([REQUEST_START_BYTE, self.address, inv_addr, group, cmd, len(data)]) + data
        packet.append((~sum(packet)) & 0xFF)
        return packet

    def auto_detect_protocol(self) -> Optional[ProtocolType]:
        packet = self._create_packet(CMD_GROUP_CONNECTION, CMD_IDENTIFY)
        payload = self._send_and_receive(packet)
        if payload:
            try:
                device_name = payload.decode('ascii', errors='ignore').strip()
                if "TEM-104M-1" in device_name: return 'ARVAS_M1'
                if "TEM-104M" in device_name: return 'ARVAS_M'
                if "TSM104" in device_name: return 'TESMART'
                if "TEM-104-1" in device_name: return 'ARVAS_LEGACY_1'
                if "TEM-104" in device_name: return 'ARVAS_LEGACY'
            except Exception: return None
        return None

    def get_specific_data(self) -> Dict[str, Any]:
        """
        Главный метод для получения требуемых данных.
        Определяет протокол и вызывает соответствующий парсер.
        """
        if not self.protocol_type:
            self.protocol_type = self.auto_detect_protocol()
        
        if not self.protocol_type:
            # Улучшенное сообщение об ошибке
            raise ValueError("Не удалось определить протокол. Устройство не ответило на команду идентификации.")
        
        # Маршрутизатор вызовов в зависимости от протокола
        if self.protocol_type == 'ARVAS_M1': return self._parse_arvas_m1_data()
        if self.protocol_type == 'ARVAS_M': return self._parse_arvas_m_data()
        if self.protocol_type == 'ARVAS_LEGACY_1': return self._parse_arvas_legacy_1_data()
        if self.protocol_type == 'ARVAS_LEGACY': return self._parse_arvas_legacy_data()
        if self.protocol_type == 'TESMART': return self._parse_tesmart_data()

        raise NotImplementedError(f"Парсер для протокола {self.protocol_type} не реализован.")

    # --- МЕТОДЫ-ПАРСЕРЫ ДЛЯ КАЖДОЙ МОДЕЛИ ---
    def _parse_arvas_m1_data(self) -> Dict[str, Any]:
        data = {'Time': self._get_current_time()}
        # Итоги @ 0x0180
        totals_payload = self._read_block(CMD_GROUP_READ_MEM, CMD_READ_CONFIG, 0x0180)
        if totals_payload:
            data['Q'] = self._unpack_float(totals_payload, 0x20) + self._unpack_long(totals_payload, 0x10)
            data['M1'] = self._unpack_float(totals_payload, 0x1C) + self._unpack_long(totals_payload, 0x0C)
            data['V1'] = self._unpack_float(totals_payload, 0x18) + self._unpack_long(totals_payload, 0x08)
            data['T_nar'] = self._unpack_long(totals_payload, 0x30)
        # Мгновенные @ 0x4000
        instant_payload = self._read_block(CMD_GROUP_READ_RAM, CMD_READ_RAM, 0x4000)
        if instant_payload:
            data['T1'] = self._unpack_float(instant_payload, 0x00)
            data['T2'] = self._unpack_float(instant_payload, 0x04)
            data['G1'] = self._unpack_float(instant_payload, 0x20)
            data['G2'] = self._unpack_float(instant_payload, 0x24)
        return data

    def _parse_arvas_m_data(self) -> Dict[str, Any]:
        data = {'Time': self._get_current_time()}
        # Итоги @ 0x0800
        totals_payload = self._read_block(CMD_GROUP_READ_MEM, CMD_READ_CONFIG, 0x0800)
        if totals_payload:
            data['Q'] = self._unpack_float(totals_payload, 0x68) + self._unpack_long(totals_payload, 0x28)
            data['M1'] = self._unpack_float(totals_payload, 0x58) + self._unpack_long(totals_payload, 0x18)
            data['V1'] = self._unpack_float(totals_payload, 0x48) + self._unpack_long(totals_payload, 0x08)
            data['V2'] = self._unpack_float(totals_payload, 0x4C) + self._unpack_long(totals_payload, 0x0C)
            data['T_nar'] = self._unpack_long(totals_payload, 0xA0)
        # Мгновенные @ 0x0000
        instant_payload = self._read_block(CMD_GROUP_READ_RAM, CMD_READ_RAM, 0x0000)
        if instant_payload:
            data['T1'] = self._unpack_float(instant_payload, 0x00)
            data['T2'] = self._unpack_float(instant_payload, 0x04)
            data['G1'] = self._unpack_float(instant_payload, 0x40)
            data['G2'] = self._unpack_float(instant_payload, 0x44)
        return data

    def _parse_arvas_legacy_1_data(self) -> Dict[str, Any]:
        data = {'Time': self._get_current_time()}
        # Итоги @ 0x0100
        totals_payload = self._read_block(CMD_GROUP_READ_MEM, CMD_READ_CONFIG, 0x0100)
        if totals_payload:
            data['Q'] = self._unpack_float(totals_payload, 0x58) + self._unpack_long(totals_payload, 0x54)
            data['M1'] = self._unpack_float(totals_payload, 0x50) + self._unpack_long(totals_payload, 0x4C)
            data['V1'] = self._unpack_float(totals_payload, 0x48) + self._unpack_long(totals_payload, 0x44)
            data['T_nar'] = self._unpack_long(totals_payload, 0x60)
        # Мгновенные @ 0x00B8
        instant_payload = self._read_block(CMD_GROUP_READ_RAM, CMD_READ_RAM, 0x00B8)
        if instant_payload:
            data['T1'] = self._unpack_float(instant_payload, 0x08)
            data['T2'] = self._unpack_float(instant_payload, 0x0C)
            data['G1'] = self._unpack_float(instant_payload, 0x00)
        return data
        
    def _parse_arvas_legacy_data(self) -> Dict[str, Any]:
        data = {'Time': self._get_current_time()}
        # Итоги @ 0x0200
        totals_payload = self._read_block(CMD_GROUP_READ_MEM, CMD_READ_CONFIG, 0x0200)
        if totals_payload:
            data['Q'] = self._unpack_float(totals_payload, 0x28) + self._unpack_long(totals_payload, 0x58)
            data['M1'] = self._unpack_float(totals_payload, 0x18) + self._unpack_long(totals_payload, 0x48)
            data['V1'] = self._unpack_float(totals_payload, 0x08) + self._unpack_long(totals_payload, 0x38)
            data['V2'] = self._unpack_float(totals_payload, 0x0C) + self._unpack_long(totals_payload, 0x3C)
            data['T_nar'] = self._unpack_long(totals_payload, 0x6C)
        # Мгновенные @ 0x2200
        instant_payload = self._read_block(CMD_GROUP_READ_RAM, CMD_READ_RAM, 0x2200)
        if instant_payload:
            data['T1'] = self._unpack_float(instant_payload, 0x00)
            data['T2'] = self._unpack_float(instant_payload, 0x04)
            data['G1'] = self._unpack_float(instant_payload, 0x40)
            data['G2'] = self._unpack_float(instant_payload, 0x44)
        return data

    def _parse_tesmart_data(self) -> Dict[str, Any]:
        full_payload = bytearray()
        for i in range(5):
            payload_part = self._read_block(CMD_GROUP_READ_MEM, CMD_READ_CONFIG, i * 0x100, length=0xFF)
            if not payload_part: raise IOError("Не удалось прочитать все блоки памяти ТЭСМАРТ.")
            full_payload.extend(payload_part)
            time.sleep(0.2)
            
        data = {}
        try:
            ss, mm, hh = bcd_to_int(full_payload[0x482]), bcd_to_int(full_payload[0x483]), bcd_to_int(full_payload[0x484])
            dd, MM, YY = bcd_to_int(full_payload[0x485]), bcd_to_int(full_payload[0x486]), bcd_to_int(full_payload[0x487])
            data['Time'] = f"20{YY:02d}-{MM:02d}-{dd:02d} {hh:02d}:{mm:02d}:{ss:02d}"

            k_v1 = self._get_tesmart_coeff(full_payload[0x02FA], 'volume')
            k_v2 = self._get_tesmart_coeff(full_payload[0x02FB], 'volume')
            k_q1 = self._get_tesmart_coeff(full_payload[0x02FA], 'energy')

            data['Q'] = (self._unpack_long(full_payload, 0x0378) + self._unpack_float(full_payload, 0x0360)) / k_q1
            data['M1'] = (self._unpack_long(full_payload, 0x0348) + self._unpack_float(full_payload, 0x0330)) / k_v1
            data['V1'] = (self._unpack_long(full_payload, 0x0318) + self._unpack_float(full_payload, 0x0300)) / k_v1
            data['V2'] = (self._unpack_long(full_payload, 0x031C) + self._unpack_float(full_payload, 0x0304)) / k_v2
            data['T_nar'] = self._unpack_long(full_payload, 0x0404)
            
            data['T1'] = self._unpack_float(full_payload, 0x0200)
            data['T2'] = self._unpack_float(full_payload, 0x0204)
            data['G1'] = self._unpack_float(full_payload, 0x0288)
            data['G2'] = self._unpack_float(full_payload, 0x028C)
        except (IndexError, struct.error) as e:
            raise ValueError(f"Ошибка разбора данных ТЭСМАРТ: {e}")
        return data
        
    # --- ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ---
    def _get_current_time(self) -> str:
        """
        Читает и форматирует время, создавая
        корректный запрос для команды 0F02.
        """
        req_data = b''
        # Определяем данные запроса (start_addr, length) в зависимости от протокола
        if self.protocol_type in ['ARVAS_M', 'ARVAS_M1', 'ARVAS_LEGACY_1']:
            req_data = bytearray([0x00, 0x07])
        elif self.protocol_type == 'ARVAS_LEGACY':
            req_data = bytearray([0x10, 0x0A])
        
        # Для TESMART время читается из общего блока, поэтому здесь для него нет логики
        if not req_data:
            return "N/A"

        # Создаем и отправляем пакет вручную, а не через _read_block
        packet = self._create_packet(CMD_GROUP_READ_MEM, CMD_READ_RTC, data=req_data)
        payload = self._send_and_receive(packet)

        if not payload:
            return "N/A"
            
        # Разбираем ответ в зависимости от протокола
        try:
            if self.protocol_type in ['ARVAS_M', 'ARVAS_M1']:
                if len(payload) >= 6:
                    ss, mm, hh, dd, MM, YY = payload[:6]
                    return f"20{YY:02d}-{MM:02d}-{dd:02d} {hh:02d}:{mm:02d}:{ss:02d}"
            elif self.protocol_type == 'ARVAS_LEGACY':
                if len(payload) >= 10:
                    ss, mm, hh = bcd_to_int(payload[0]), bcd_to_int(payload[2]), bcd_to_int(payload[4])
                    dd, MM, YY = bcd_to_int(payload[7]), bcd_to_int(payload[8]), bcd_to_int(payload[9])
                    return f"20{YY:02d}-{MM:02d}-{dd:02d} {hh:02d}:{mm:02d}:{ss:02d}"
            elif self.protocol_type == 'ARVAS_LEGACY_1':
                if len(payload) >= 7:
                    ss, mm, hh = bcd_to_int(payload[0]), bcd_to_int(payload[1]), bcd_to_int(payload[2])
                    dd, MM, YY = bcd_to_int(payload[4]), bcd_to_int(payload[5]), bcd_to_int(payload[6])
                    return f"20{YY:02d}-{MM:02d}-{dd:02d} {hh:02d}:{mm:02d}:{ss:02d}"
        except IndexError:
            return "Ошибка разбора времени"
            
        return "N/A"

    def _read_block(self, group, cmd, base_addr, length=0xFF) -> Optional[bytes]:
        """Универсальная функция для чтения блока данных (кроме RTC)."""
        addr_h, addr_l = (base_addr >> 8) & 0xFF, base_addr & 0xFF
        packet = self._create_packet(group, cmd, data=bytearray([addr_h, addr_l, length]))
        return self._send_and_receive(packet)

    def _unpack_float(self, payload, offset):
        return struct.unpack('>f', payload[offset:offset+4])[0] if payload and len(payload) >= offset + 4 else 0.0

    def _unpack_long(self, payload, offset):
        return struct.unpack('>L', payload[offset:offset+4])[0] if payload and len(payload) >= offset + 4 else 0

    def _get_tesmart_coeff(self, comma_val: int, param_type: str) -> int:
        coeffs = {'energy': {6: 100000, 5: 10000, 4: 1000, 3: 100, 2: 10}, 'volume': {5: 1000, 4: 100, 3: 10}}
        return coeffs.get(param_type, {}).get(comma_val, 1)

class TEM104_TCP_Client(TEM104_Base_Client):
    """Реализация транспортного уровня для сети TCP/IP."""
    def __init__(self, host: str, port: int, address: int, **kwargs):
        protocol = kwargs.get('protocol', None)
        super().__init__(address, protocol=protocol)
        self.host = host
        self.port = port
        self.sock = None
        self.timeout = kwargs.get('timeout', 5.0)

    def connect(self):
        if self.sock: return
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect((self.host, self.port))
        except socket.error as e:
            self.sock = None
            raise ConnectionError(f"Не удалось подключиться. Причина: {e}")

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def _send_and_receive(self, packet: bytearray) -> Optional[bytearray]:
        if not self.sock: raise ConnectionError("Соединение не установлено.")
        try:
            self.sock.sendall(packet)
            header = self.sock.recv(6)
            if not header or len(header) < 6: return None
            if header[0] != RESPONSE_START_BYTE or header[1] != self.address: return None
            
            data_len = header[5]
            bytes_to_read = data_len + 1
            body = b''
            # ИСПРАВЛЕНИЕ: Убран слишком агрессивный таймаут в 2 секунды.
            # Теперь используется общий таймаут сокета (5 секунд), что
            # более надежно для медленных сетей.
            # self.sock.settimeout(2.0) 
            while len(body) < bytes_to_read:
                chunk = self.sock.recv(bytes_to_read - len(body))
                if not chunk: raise ConnectionError("Соединение разорвано.")
                body += chunk
            
            response = header + body
            if (sum(response) & 0xFF) != 0xFF: return None
            return response[6:-1]
        except (socket.timeout, socket.error):
            return None

# --- ЛОГИКА МАССОВОГО СБОРА ДАННЫХ ---
def run_data_harvesting():
    """
    Основная функция, которая читает JSON, опрашивает каждый
    счетчик и выводит запрошенные данные.
    """
    if not os.path.exists(JSON_FILENAME):
        print(f"ОШИБКА: Файл '{JSON_FILENAME}' не найден. Создайте его.")
        return
    try:
        with open(JSON_FILENAME, 'r', encoding='utf-8') as f:
            devices = json.load(f)
        if not isinstance(devices, list): raise ValueError("JSON должен быть списком.")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"ОШИБКА: Некорректный формат файла '{JSON_FILENAME}'. {e}")
        return

    print("--- ЗАПУСК МАССОВОГО СБОРА ДАННЫХ ---")
    print(f"TCP-порт: {TCP_PORT}, Адрес счетчика: {METER_ADDRESS}\n")
    
    for device in devices:
        name = device.get("name", "N/A")
        ip = device.get("ip")
        
        print(f"--- Объект: {name} ({ip}) ---")

        if not ip:
            print("  Статус: ОШИБКА (IP-адрес не указан)\n")
            continue
            
        client = None
        try:
            client = TEM104_TCP_Client(host=ip, port=TCP_PORT, address=METER_ADDRESS, timeout=5)
            client.connect()
            
            data = client.get_specific_data()
            
            # Форматированный вывод
            print(f"  Статус: ОНЛАЙН | Протокол: {client.protocol_type}")
            print(f"    Время счетчика:   {data.get('Time', '---')}")
            print(f"    Q (Энергия):      {data.get('Q', '---'):.3f}")
            print(f"    M1 (Масса 1):     {data.get('M1', '---'):.3f}")
            print(f"    V1 (Объем 1):     {data.get('V1', '---'):.3f}")
            print(f"    V2 (Объем 2):     {data.get('V2', '---'):.3f}")
            print(f"    T1 (Темп. 1):     {data.get('T1', '---'):.2f} °C")
            print(f"    T2 (Темп. 2):     {data.get('T2', '---'):.2f} °C")
            print(f"    G1 (Расход 1):    {data.get('G1', '---'):.3f} м³/ч")
            print(f"    G2 (Расход 2):    {data.get('G2', '---'):.3f} м³/ч")
            print(f"    T_нар (Наработка):  {int(data.get('T_nar', 0) / 3600)} ч.\n")

        except (ConnectionError, ValueError, IOError, NotImplementedError) as e:
            print(f"  Статус: ОШИБКА | {e}\n")
        except Exception as e:
            print(f"  Статус: КРИТИЧЕСКАЯ ОШИБКА | {e}\n")
        finally:
            if client: client.disconnect()
        
        time.sleep(0.5)

if __name__ == "__main__":
    run_data_harvesting()