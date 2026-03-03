"""
Простой тест ADS1256 Receiver
Показывает первые полученные значения для проверки
"""

from ads1256_receiver import ADS1256Receiver
import time

print("=== Тест ADS1256 Receiver ===\n")

# Создаём receiver
receiver = ADS1256Receiver(baudrate=230400)

# Список портов0
ports = receiver.list_ports()
print("Доступные порты:")
for i, (port, desc) in enumerate(ports):
    print(f"  {i}: {port} - {desc}")

# Выбор порта
port_idx = int(input("\nВыберите порт: "))
selected_port = ports[port_idx][0]

# Подключение
print(f"\nПодключаюсь к {selected_port}...")
ok, msg = receiver.connect(selected_port)

if not ok:
    print(f"❌ Ошибка: {msg}")
    exit(1)

print("✅ Подключён!")

# Запуск
print("\nЗапускаю сбор данных...")
receiver.start_streaming()
time.sleep(0.5)

# Собираем данные 3 секунды
print("Собираю данные 3 секунды...\n")
for i in range(30):
    new_samples = receiver.read_data()
    if new_samples > 0:
        print(f"  +{new_samples} samples")
    time.sleep(0.1)

# Статистика
stats = receiver.get_connection_stats()
print(f"\n📊 Статистика:")
print(f"  Пакетов принято: {stats['packets_received']}")
print(f"  Пакетов потеряно: {stats['packets_lost']} ({stats['packet_loss_rate']*100:.1f}%)")
print(f"  Скорость: {stats['data_rate']/1024:.1f} кБ/с")

# Показываем первые значения каждого канала
print(f"\n📈 Первые значения по каналам (mV):")
time_arr, data_arrays = receiver.get_data_arrays()

if len(time_arr) > 0:
    print(f"  Времени: {len(time_arr)} точек")
    for ch in range(8):
        if len(data_arrays[ch]) > 0:
            first_val = data_arrays[ch][0] * 1000  # в mV
            last_val = data_arrays[ch][-1] * 1000
            mean_val = sum(data_arrays[ch]) / len(data_arrays[ch]) * 1000
            print(f"  Ch{ch}: первое={first_val:+8.3f} mV, последнее={last_val:+8.3f} mV, среднее={mean_val:+8.3f} mV")
else:
    print("  ❌ Данных не получено!")

# Останов
receiver.stop_streaming()
receiver.disconnect()

print("\nГотово!")
input("Enter для выхода...")
