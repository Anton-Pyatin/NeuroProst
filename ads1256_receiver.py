"""
=============================================================================
ADS1256 Data Receiver Module - Оптимизированная версия
=============================================================================
Отвечает за:
  - Подключение к COM-порту
  - Приём и парсинг бинарных пакетов
  - Преобразование raw → voltage
  - Буферизацию данных для отображения

Версия: 2.0 (оптимизированная)
=============================================================================
"""

import serial
import serial.tools.list_ports
import struct
import numpy as np
from collections import deque
import time


class ADS1256Receiver:
    """
    Класс для приёма данных от ADS1256 через Serial
    
    Формат пакета:
    ┌─────────┬─────────┬─────────────┬──────────────┬──────────────┬──────────┐
    │ SYNC1   │ SYNC2   │ PACKET_NUM  │ SAMPLE_COUNT │     DATA     │ CHECKSUM │
    │ 0xAA    │ 0x55    │  2 bytes    │   1 byte     │ N*8*4 bytes  │  1 byte  │
    └─────────┴─────────┴─────────────┴──────────────┴──────────────┴──────────┘
    
    Параметры при создании:
        port (str): COM-порт (например, 'COM3')
        baudrate (int): Скорость (230400 для STM32 8MHz)
        buffer_size (int): Размер циркулярного буфера (в сэмплах)
    """
    
    # Константы протокола
    SYNC_BYTE1 = 0xAA
    SYNC_BYTE2 = 0x55
    CHANNELS = 8
    VREF = 2.5  # Опорное напряжение АЦП (Вольт)
    
    def __init__(self, port=None, baudrate=230400, buffer_size=2000):
        """Инициализация приёмника"""
        # Значение по умолчанию
        self.current_pga = 1.0

        # Параметры подключения
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.is_connected = False
        self.is_streaming = False
        
        # Буферы данных (циркулярные через deque)
        self.buffer_size = buffer_size
        self.data_buffers = [deque(maxlen=buffer_size) for _ in range(self.CHANNELS)]
        self.time_buffer = deque(maxlen=buffer_size)
        
        # Статистика
        self.packets_received = 0
        self.packets_lost = 0
        self.last_packet_num = -1
        self.bytes_received = 0
        self.start_time = None
        self.last_update_time = 0
        
        # Буфер для неполных пакетов (carry-over между вызовами read)
        self._leftover_bytes = b''
    
    # =========================================================================
    # Методы работы с портом
    # =========================================================================
    
    def list_ports(self):
        """
        Получить список доступных COM-портов
        
        Returns:
            list: [(port, description), ...] — список кортежей
        """
        ports = serial.tools.list_ports.comports()
        return [(p.device, p.description) for p in ports]
    
    def connect(self, port=None):
        """
        Подключиться к COM-порту
        
        Args:
            port (str): Имя порта ('COM3', '/dev/ttyUSB0' и т.д.)
        
        Returns:
            tuple: (успех: bool, сообщение об ошибке: str)
        """
        if port:
            self.port = port
            
        if not self.port:
            return False, "Порт не указан"
        
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.5
            )
            
            self.is_connected = True
            self.start_time = time.time()
            print(f"✅ Подключён: {self.port} @ {self.baudrate} baud")
            return True, ""
            
        except serial.SerialException as e:
            self.is_connected = False
            msg = str(e)
            # Более понятные сообщения для частых ошибок
            if "Access is denied" in msg or "PermissionError" in msg:
                msg = "Порт занят другой программой"
            elif "FileNotFoundError" in msg or "could not open port" in msg.lower():
                msg = f"Порт {port} не найден"
            
            print(f"❌ Ошибка подключения: {msg}")
            return False, msg
            
        except Exception as e:
            self.is_connected = False
            return False, str(e)
    
    def disconnect(self):
        """Отключиться от порта"""
        if self.serial and self.serial.is_open:
            self.stop_streaming()
            self.serial.close()
            self.is_connected = False
            print("Отключён от порта")
    
    # =========================================================================
    # Команды управления Arduino
    # =========================================================================
    
    def send_command(self, command):
        """
        Отправить текстовую команду Arduino
        
        Args:
            command (str): Команда (START, STOP, STATUS и т.д.)
        
        Returns:
            str or bool: Ответ от устройства или False при ошибке
        """
        if not self.is_connected:
            return False
        
        try:
            self.serial.write(f"{command}\n".encode())
            time.sleep(0.05)
            
            # Читаем ответ
            if self.serial.in_waiting:
                response = self.serial.readline().decode(errors='ignore').strip()
                print(f"← Arduino: {response}")
                return response
            return True
            
        except Exception as e:
            print(f"Ошибка отправки команды: {e}")
            return False
    
    def start_streaming(self):
        """Начать потоковую передачу данных"""
        response = self.send_command("START")
        if response:
            self.is_streaming = True
            self.packets_received = 0
            self.packets_lost = 0
            self.last_packet_num = -1
            self._leftover_bytes = b''
            
            # Очистка буферов
            for buf in self.data_buffers:
                buf.clear()
            self.time_buffer.clear()
            
            self.start_time = time.time()
            return True
        return False
    
    def stop_streaming(self):
        """Остановить передачу"""
        response = self.send_command("STOP")
        if response:
            self.is_streaming = False
            return True
        return False
    
    def set_pga(self, gain_index):
        """
        Установить коэффициент усиления PGA
        
        Args:
            gain_index (int): 0-7, где gain = 2^index
                             0 → ×1, 1 → ×2, 2 → ×4, ..., 6 → ×64
        """
        pga_map = {0: 1.0, 1: 2.0, 2: 4.0, 3: 8.0, 4: 16.0, 5: 32.0, 6: 64.0}
        self.current_pga = pga_map.get(gain_index, 1.0)
        return self.send_command(f"PGA {gain_index}")
    
    def set_drate(self, rate):
        """
        Установить частоту дискретизации
        
        Args:
            rate (int): 2000, 3750, 7500 SPS
        """
        return self.send_command(f"DRATE {rate}")
    
    def get_status(self):
        """Запросить статус устройства"""
        return self.send_command("STATUS")
    
    # =========================================================================
    # Парсинг данных
    # =========================================================================
    
    def find_sync_pattern(self, data):
        """
        Найти синхропоследовательность в массиве байт
        
        Args:
            data (bytes): Массив байт для поиска
        
        Returns:
            int: Позиция начала пакета или -1 если не найдено
        """
        for i in range(len(data) - 1):
            if data[i] == self.SYNC_BYTE1 and data[i + 1] == self.SYNC_BYTE2:
                return i
        return -1
    
    def parse_packet(self, packet_bytes):
        """
        Распарсить бинарный пакет
        
        Args:
            packet_bytes (bytes): Массив байт пакета
        
        Returns:
            dict or None: {
                'packet_num': int,
                'sample_count': int,
                'data': ndarray(sample_count, 8),  # int32
                'checksum_ok': bool
            }
        """
        if len(packet_bytes) < 6:
            return None
        
        # Проверка синхробайтов
        if packet_bytes[0] != self.SYNC_BYTE1 or packet_bytes[1] != self.SYNC_BYTE2:
            return None
        
        # Заголовок: [0xAA][0x55][PKT_HI][PKT_LO][N_SAMPLES]
        packet_num = struct.unpack('>H', packet_bytes[2:4])[0]  # Big-endian uint16
        sample_count = packet_bytes[4]
        
        # Ожидаемый размер: 5 (заголовок) + N*8*4 (данные) + 1 (checksum)
        data_size = sample_count * self.CHANNELS * 4
        total_size = 5 + data_size + 1
        
        if len(packet_bytes) < total_size:
            return None
        
        # Извлечение данных (int32 big-endian)
        data_start = 5
        data_end = data_start + data_size
        data_bytes = packet_bytes[data_start:data_end]
        
        try:
            data_array = np.array(
                struct.unpack(f'>{sample_count * self.CHANNELS}i', data_bytes),
                dtype=np.int32
            ).reshape(sample_count, self.CHANNELS)
        except Exception as e:
            print(f"Ошибка распаковки данных: {e}")
            return None
        
        # Проверка контрольной суммы (XOR всех байт до checksum)
        received_checksum = packet_bytes[data_end]
        calculated_checksum = 0
        for b in packet_bytes[:data_end]:
            calculated_checksum ^= b
        
        checksum_ok = (received_checksum == calculated_checksum)
        
        return {
            'packet_num': packet_num,
            'sample_count': sample_count,
            'data': data_array,
            'checksum_ok': checksum_ok
        }
    
    def convert_to_voltage(self, raw_value):
        """
        Преобразовать raw значение АЦП в напряжение
        
        ADS1256: 24-bit signed, биполярный ±VREF
        LSB = (2 * VREF) / 2^23 = (2 * 2.5) / 8388608 ≈ 0.596 мкВ
        
        Args:
            raw_value (int): Сырое 24-битное значение
        
        Returns:
            float: Напряжение в вольтах
        """
        return (raw_value * 2.0 * self.VREF) / (self.current_pga * 8388608.0)
    
    # =========================================================================
    # Чтение и буферизация данных
    # =========================================================================
    
    def read_data(self):
        """
        Прочитать данные из порта и добавить в буферы
        
        Обрабатывает:
          - Поиск синхропоследовательностей
          - Парсинг пакетов
          - Проверку целостности
          - Детекцию потерянных пакетов
          - Преобразование в вольты
        
        Returns:
            int: Количество новых сэмплов
        """
        if not self.is_connected or not self.serial.is_open:
            return 0
        
        new_samples = 0
        
        try:
            # Читаем доступные байты
            if self.serial.in_waiting > 0:
                incoming = self._leftover_bytes + self.serial.read(self.serial.in_waiting)
                self.bytes_received += len(incoming) - len(self._leftover_bytes)
                
                # Поиск пакетов в потоке
                processed_up_to = 0
                
                while True:
                    # Ищем синхропоследовательность
                    sync_pos = self.find_sync_pattern(incoming[processed_up_to:])
                    if sync_pos < 0:
                        break  # Синхробайты не найдены
                    
                    sync_pos += processed_up_to
                    
                    # Проверяем наличие заголовка (минимум 5 байт)
                    if len(incoming) - sync_pos < 5:
                        self._leftover_bytes = incoming[sync_pos:]
                        return new_samples
                    
                    # Вычисляем размер пакета
                    sample_count = incoming[sync_pos + 4]
                    packet_size = 5 + (sample_count * self.CHANNELS * 4) + 1
                    
                    # Проверяем полноту пакета
                    if len(incoming) - sync_pos < packet_size:
                        self._leftover_bytes = incoming[sync_pos:]
                        return new_samples
                    
                    # Извлекаем пакет
                    packet_bytes = incoming[sync_pos:sync_pos + packet_size]
                    processed_up_to = sync_pos + packet_size
                    
                    # Парсим пакет
                    result = self.parse_packet(packet_bytes)
                    
                    if result and result['checksum_ok']:
                        # Детекция потерянных пакетов
                        if self.last_packet_num >= 0:
                            expected = (self.last_packet_num + 1) % 65536
                            if result['packet_num'] != expected:
                                lost = (result['packet_num'] - expected) % 65536
                                self.packets_lost += lost
                                print(f"⚠ Пропущено {lost} пакетов (#{self.last_packet_num} → #{result['packet_num']})")
                        
                        self.last_packet_num = result['packet_num']
                        self.packets_received += 1
                        
                        # Добавляем данные в буферы
                        current_time = time.time() - self.start_time
                        
                        for sample_idx in range(result['sample_count']):
                            for ch in range(self.CHANNELS):
                                raw = result['data'][sample_idx, ch]
                                voltage = self.convert_to_voltage(raw)
                                self.data_buffers[ch].append(voltage)
                            
                            self.time_buffer.append(current_time)
                            current_time += (1.0 / 162.0)  # 250 Гц = период 4 мс
                            new_samples += 1
                        
                        self.last_update_time = time.time()
                    
                    elif result and not result['checksum_ok']:
                        print(f"❌ Ошибка checksum пакета #{result['packet_num']}")
                
                # Сохраняем необработанный хвост
                self._leftover_bytes = incoming[processed_up_to:]
        
        except Exception as e:
            print(f"Ошибка чтения: {e}")
        
        return new_samples
    
    # =========================================================================
    # Получение данных для отображения
    # =========================================================================
    
    def get_data_arrays(self):
        """
        Получить данные как numpy массивы для построения графиков
        
        Returns:
            tuple: (time_array, [ch0_array, ch1_array, ..., ch7_array])
        """
        time_array = np.array(self.time_buffer)
        data_arrays = [np.array(buf) for buf in self.data_buffers]
        return time_array, data_arrays
    
    def get_statistics(self, channel):
        """
        Получить статистику по каналу
        
        Args:
            channel (int): Номер канала 0-7
        
        Returns:
            dict or None: {
                'min': float,
                'max': float,
                'mean': float,
                'std': float,
                'peak_to_peak': float,
                'rms': float
            }
        """
        if not self.data_buffers[channel]:
            return None
        
        data = np.array(self.data_buffers[channel])
        
        return {
            'min': np.min(data),
            'max': np.max(data),
            'mean': np.mean(data),
            'std': np.std(data),
            'peak_to_peak': np.max(data) - np.min(data),
            'rms': np.sqrt(np.mean(data**2))
        }
    
    def get_connection_stats(self):
        """
        Получить статистику подключения
        
        Returns:
            dict: Статистика (connected, streaming, packets, loss_rate, etc.)
        """
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        total_packets = self.packets_received + self.packets_lost
        loss_rate = self.packets_lost / max(1, total_packets)
        
        return {
            'connected': self.is_connected,
            'streaming': self.is_streaming,
            'packets_received': self.packets_received,
            'packets_lost': self.packets_lost,
            'packet_loss_rate': loss_rate,
            'bytes_received': self.bytes_received,
            'elapsed_time': elapsed,
            'data_rate': self.bytes_received / max(1, elapsed) if elapsed > 0 else 0
        }
