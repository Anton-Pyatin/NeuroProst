# 🚀 Быстрый старт ADS1256

## 📦 Установка (5 минут)

### 1. Arduino
```
1. Установить Arduino IDE
2. Добавить плату STM32: https://github.com/stm32duino/BoardManagerFiles/raw/main/package_stmicroelectronics_index.json
3. Установить библиотеку: ADS1256 by Curious Scientist
4. Загрузить ADS1256_Streaming.ino
```

### 2. Python
```bash
pip install pyqt5 pyqtgraph pyserial numpy pandas scipy
```

---

## 🔌 Распиновка

### STM32 → ADS1256
```
SPI2:
  PB13 → SCLK
  PB14 → DOUT (MISO)
  PB15 → DIN (MOSI)
  PB12 → CS
  PB10 → DRDY
  PB11 → RESET (опционально)
  
Питание:
  3.3V → AVDD, DVDD
  GND  → AGND, DGND
```

### Аналоговые входы
```
AIN0-AIN7: Дифференциальные входы ±VREF
AINCOM: Общий (GND для single-ended)
```

---

## ⚡ Запуск (30 секунд)

### Arduino
```
1. Подключить STM32 через USB
2. Выбрать COM порт
3. Загрузить код
4. Открыть Serial Monitor (921600 baud)
5. Ввести "STATUS" для проверки
```

### Python GUI
```bash
python ads1256_gui.py
```

```
1. Выбрать COM порт
2. Connect
3. Start
4. Готово! 📊
```

---

## 📊 Основные команды

### В Serial Monitor (Arduino):
```
START        - Начать передачу данных
STOP         - Остановить передачу
STATUS       - Показать статус
PGA 0-7      - Установить усиление (0=1x, 7=64x)
DRATE 2000   - Установить частоту (2000/5000/10000)
```

### В GUI:
```
Connect      - Подключиться к устройству
▶ Start      - Начать сбор данных
⏸ Pause      - Приостановить отображение
⏺ Record     - Записать в CSV
```

---

## 🎛️ Настройки для разных сигналов

### ЭЭГ/ЭКГ (биосигналы)
```cpp
// Arduino:
adc.setPGA(4);              // Усиление 16x
adc.setDRATE(DRATE_2000SPS); // 250 Гц на канал
```
```python
# GUI:
PGA: 16x
Data Rate: 2000 SPS
Time Window: 5s
Filter: Lowpass 50 Hz (сеть)
```

### Вибрация / акустика
```cpp
// Arduino:
adc.setPGA(0);               // Усиление 1x
adc.setDRATE(DRATE_10000SPS); // 1250 Гц
```
```python
# GUI:
Time Window: 1s
Filter: Highpass 10 Hz
```

### Медленные сигналы (температура)
```cpp
// Arduino:
adc.setDRATE(DRATE_2000SPS);
```
```python
# GUI:
Time Window: 30s
Filter: Lowpass 1 Hz
```

---

## 🔧 Устранение проблем

### Проблема: Нет связи с АЦП
```
✓ Проверить питание (3.3V на AVDD/DVDD)
✓ Проверить SPI подключение
✓ Проверить DRDY (должен "моргать")
```

### Проблема: Много потерянных пакетов
```
✓ Уменьшить BAUDRATE до 460800
✓ Использовать качественный USB кабель
✓ Увеличить SAMPLES_PER_PACKET
✓ Снизить DRATE
```

### Проблема: Большой шум
```
✓ Добавить конденсаторы 0.1µF + 10µF на питание
✓ Включить входной буфер: adc.setBuffer(1)
✓ Использовать экранированные провода
✓ Заземлить AINCOM
✓ Увеличить PGA
```

---

## 📁 Структура файлов

```
ADS1256_Project/
├── ADS1256_Streaming.ino     ← Arduino прошивка
├── ads1256_receiver.py       ← Приём данных
├── ads1256_gui.py            ← Главное GUI (ЗАПУСКАТЬ)
├── ads1256_analyzer.py       ← Анализ записей
├── system_test.py            ← Тестирование
├── requirements.txt          ← Зависимости Python
└── README.md                 ← Полная инструкция
```

---

## 🎯 Типичный рабочий процесс

```
1. Запустить GUI
2. Connect → Start
3. Настроить PGA и фильтры
4. Record → сохранить данные
5. Stop → закрыть GUI
6. Запустить Analyzer
7. Load CSV → анализ
8. Export Filtered → готово!
```

---

## 💾 Формат CSV файла

```csv
Time (s),Ch0 (V),Ch1 (V),Ch2 (V),Ch3 (V),Ch4 (V),Ch5 (V),Ch6 (V),Ch7 (V)
0.000,-0.000123,0.000456,-0.000234,0.000567,0.000012,-0.000345,0.000678,-0.000890
0.004,-0.000145,0.000478,-0.000256,0.000589,0.000034,-0.000367,0.000700,-0.000912
...
```

---

## 🔬 Спецификации

```
Разрешение:     24 бит
Входной диапазон: ±VREF (±2.5V типично)
Частота АЦП:    до 30000 SPS
Каналов:        8 дифференциальных
Частота на канал: до 3750 Гц (при 30000/8)
Шум (типично):  ~1 µV RMS при PGA=1
```

---

## 📞 Помощь

При проблемах:
1. Читать README.md (полная инструкция)
2. Запустить system_test.py
3. Проверить подключение мультиметром
4. Проверить SPI осциллографом (если есть)

---

**Удачи! 🚀**
