"""
Диагностика сырых данных ADS1256
Показывает что именно приходит из COM порта
"""

import serial
import serial.tools.list_ports
import struct

# Выбор порта
ports = list(serial.tools.list_ports.comports())
print("Доступные порты:")
for i, p in enumerate(ports):
    print(f"  {i}: {p.device} - {p.description}")

port_idx = int(input("Выберите порт: "))
port = ports[port_idx].device

# Подключение
ser = serial.Serial(port, 230400, timeout=2)
print(f"\nПодключён к {port}")
print("Отправляю START...")

import time
time.sleep(2)
ser.reset_input_buffer()
ser.write(b"START\n")
time.sleep(0.5)

# Читаем первые байты
print("\nПервые 100 байт (hex):")
data = ser.read(100)
print(' '.join(f'{b:02X}' for b in data))

# Ищем синхропоследовательность
print("\n\nПоиск пакетов (0xAA 0x55)...")
total_read = 0
packets_found = 0

while total_read < 2000 and packets_found < 3:
    chunk = ser.read(100)
    total_read += len(chunk)
    
    for i in range(len(chunk) - 1):
        if chunk[i] == 0xAA and chunk[i+1] == 0x55:
            packets_found += 1
            print(f"\n✅ Пакет #{packets_found} найден на байте {total_read - len(chunk) + i}")
            
            # Показываем заголовок
            if i + 10 < len(chunk):
                header = chunk[i:i+10]
                pkt_num = struct.unpack('>H', header[2:4])[0]
                samples = header[4]
                print(f"   Заголовок: {' '.join(f'{b:02X}' for b in header)}")
                print(f"   Packet #: {pkt_num}")
                print(f"   Samples: {samples}")
                print(f"   Ожидаемый размер пакета: {5 + samples * 8 * 4 + 1} байт")
                
                # Пытаемся прочитать первое значение канала 0
                if i + 10 + 4 <= len(chunk):
                    first_val_bytes = chunk[i+5:i+9]
                    first_val = struct.unpack('>i', first_val_bytes)[0]
                    voltage = (first_val * 2.0 * 2.5) / 8388608.0
                    print(f"   Первое значение (Ch0): raw={first_val}, voltage={voltage:.6f}V")

ser.close()
print("\nГотово!")
input("Enter для выхода...")
