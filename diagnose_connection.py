"""
Диагностика подключения ADS1256 / STM32
Запустите этот скрипт в PyCharm если GUI не подключается.
Он проверит все возможные проблемы и укажет на причину.
"""

import serial
import serial.tools.list_ports
import time


def check_ports():
    """Показать все доступные COM порты"""
    print("\n" + "="*50)
    print("1. ДОСТУПНЫЕ COM ПОРТЫ")
    print("="*50)
    
    ports = list(serial.tools.list_ports.comports())
    
    if not ports:
        print("❌ COM порты НЕ НАЙДЕНЫ!")
        print("   → Проверьте подключение USB кабеля")
        print("   → Установите драйвер CH340:")
        print("     https://sparks.gogo.co.nz/ch340.html")
        return None
    
    for p in ports:
        print(f"  ✅ {p.device:10} | {p.description}")
    
    return ports


def try_connect(port, baudrate):
    """Попытка подключения к порту"""
    print(f"\n  Тест {baudrate} baud ... ", end="", flush=True)
    try:
        ser = serial.Serial(port, baudrate, timeout=2)
        time.sleep(2)  # Ждём reset STM32
        ser.reset_input_buffer()
        
        # Отправляем STATUS
        ser.write(b"STATUS\n")
        time.sleep(0.3)
        
        response = ser.read(ser.in_waiting).decode(errors='replace').strip()
        ser.close()
        
        if response:
            print(f"✅ OK!")
            print(f"     Ответ устройства: {repr(response[:100])}")
            return True
        else:
            print(f"⚠️  Порт открылся, но устройство молчит")
            print(f"     → Проверьте что прошивка загружена")
            print(f"     → Закройте Serial Monitor в Arduino IDE")
            return False
            
    except serial.SerialException as e:
        msg = str(e)
        if "Access is denied" in msg or "PermissionError" in msg:
            print(f"❌ ПОРТ ЗАНЯТ!")
            print(f"     → Закройте Serial Monitor в Arduino IDE")
            print(f"     → Закройте другие программы, использующие {port}")
        elif "could not open" in msg.lower() or "FileNotFoundError" in msg:
            print(f"❌ Порт не найден")
        else:
            print(f"❌ Ошибка: {msg}")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def diagnose():
    print("\n" + "="*50)
    print("  ДИАГНОСТИКА ПОДКЛЮЧЕНИЯ ADS1256/STM32")
    print("="*50)
    
    # Шаг 1: Найти порты
    ports = check_ports()
    if not ports:
        print("\n❌ Решение: подключите STM32 и установите драйвер CH340")
        return
    
    # Шаг 2: Выбрать порт для теста
    print("\n" + "="*50)
    print("2. ТЕСТ ПОДКЛЮЧЕНИЯ")
    print("="*50)
    
    # Ищем STM32 / CH340 автоматически
    stm_port = None
    for p in ports:
        desc_lower = p.description.lower()
        if any(x in desc_lower for x in ['ch340', 'ch341', 'stm32', 'usb serial', 'uart']):
            stm_port = p.device
            print(f"  Найден STM32/CH340: {p.device} ({p.description})")
            break
    
    if not stm_port:
        print("  Автоопределение не удалось. Выберите порт вручную:")
        for i, p in enumerate(ports):
            print(f"    {i}: {p.device} - {p.description}")
        try:
            idx = int(input("  Номер порта: "))
            stm_port = ports[idx].device
        except:
            stm_port = ports[0].device
            print(f"  Использую: {stm_port}")
    
    # Шаг 3: Тест скоростей
    print(f"\n  Тестирую порт {stm_port}...")
    
    baudrates = [230400, 115200, 460800, 921600]
    success_baud = None
    
    for baud in baudrates:
        if try_connect(stm_port, baud):
            success_baud = baud
            break
    
    # Шаг 4: Итог
    print("\n" + "="*50)
    print("3. РЕЗУЛЬТАТ")
    print("="*50)
    
    if success_baud:
        print(f"\n✅ УСПЕШНО! Используйте:")
        print(f"   Порт:     {stm_port}")
        print(f"   Baudrate: {success_baud}")
        print(f"\n   В GUI выберите эти значения и нажмите Connect")
        
        if success_baud != 230400:
            print(f"\n⚠️  Baudrate отличается от 230400!")
            print(f"   Измените в Arduino коде:")
            print(f"   #define SERIAL_BAUDRATE {success_baud}")
    else:
        print("\n❌ Подключение не удалось. Проверьте:")
        print("  1. STM32 подключён к ПК по USB?")
        print("  2. Прошивка ADS1256_Streaming.ino загружена?")
        print("  3. Serial Monitor Arduino IDE ЗАКРЫТ?")
        print("  4. Драйвер CH340 установлен?")
        print("  5. Baudrate в коде: #define SERIAL_BAUDRATE 230400")
        print(f"\n  Попробуйте другой USB кабель или другой USB порт ПК")


if __name__ == "__main__":
    diagnose()
    input("\nНажмите Enter для выхода...")
