#include <SPI.h>

// =========== НАСТРОЙКИ ===========
#define SERIAL_BAUDRATE 230400
#define CHANNELS 8
#define SAMPLES_PER_PACKET 25

// Пины SPI2 и управления
#define PIN_DRDY PB10
#define PIN_CS   PB12
#define PIN_RST  PB11

SPIClass spi2(PB15, PB14, PB13);

static int32_t  pktData[SAMPLES_PER_PACKET * CHANNELS];
static uint16_t pktCounter = 0;
static uint16_t sampleIndex = 0;
static bool     streaming = false;
unsigned long   lastScanTime = 0;

// Команды ADS1256
#define CMD_WREG  0x50
#define CMD_RDATA 0x01
#define CMD_SYNC  0xFC
#define CMD_WAKEUP 0x00

uint8_t currentDRATE = 0xB0; // По умолчанию 2000 SPS
uint8_t currentPGA = 0x00;   // По умолчанию 1x

// =========== ПРЯМАЯ РАБОТА С SPI ===========
void writeReg(uint8_t reg, uint8_t val) {
  digitalWrite(PIN_CS, LOW);
  spi2.transfer(CMD_WREG | reg);
  spi2.transfer(0x00); // 1 byte
  spi2.transfer(val);
  digitalWrite(PIN_CS, HIGH);
  delayMicroseconds(10);
}

void setup() {
  Serial.begin(SERIAL_BAUDRATE);
  pinMode(PIN_DRDY, INPUT_PULLUP);
  pinMode(PIN_CS, OUTPUT);
  pinMode(PIN_RST, OUTPUT);
  
  digitalWrite(PIN_RST, LOW); delay(10); digitalWrite(PIN_RST, HIGH); // Hard Reset
  
  spi2.begin();
  spi2.beginTransaction(SPISettings(2000000, MSBFIRST, SPI_MODE1)); 
  
  delay(500);

  // Настройка: Buffer ON (0x32), PGA 1 (0x00), 2000 SPS (0xB0)
  writeReg(0x00, 0x32); 
  writeReg(0x02, 0x00); 
  writeReg(0x03, 0xB0); 
  
  Serial.println(F("DIRECT SPI MODE. Send START"));
}

int32_t readRawData() {
  digitalWrite(PIN_CS, LOW);
  spi2.transfer(CMD_RDATA);
  delayMicroseconds(10); // t6 delay
  uint32_t val = spi2.transfer(0) << 16;
  val |= spi2.transfer(0) << 8;
  val |= spi2.transfer(0);
  digitalWrite(PIN_CS, HIGH);
  
  // Расширение знака для 24-битного числа
  if (val & 0x800000) val |= 0xFF000000;
  return (int32_t)val;
}

bool readOneScan() {
  unsigned long start = micros();
  
  for (uint8_t i = 0; i < CHANNELS; i++) {
    // 1. Смена канала (MUX)
    digitalWrite(PIN_CS, LOW);
    spi2.transfer(CMD_WREG | 0x01); // MUX Register
    spi2.transfer(0x00);
    spi2.transfer((i << 4) | 0x08); // AINi + AINCOM
    digitalWrite(PIN_CS, HIGH);
    
    // 2. Команда на обновление
    digitalWrite(PIN_CS, LOW);
    spi2.transfer(CMD_SYNC);
    delayMicroseconds(2);
    spi2.transfer(CMD_WAKEUP);
    digitalWrite(PIN_CS, HIGH);

    // 3. ЖЕСТКИЙ ТАЙМАУТ DRDY (2мс вместо 300мс)
    uint32_t wait = micros();
    while(digitalRead(PIN_DRDY) == HIGH) {
      if(micros() - wait > 2000) break; 
    }

    // 4. Чтение
    pktData[sampleIndex * CHANNELS + i] = readRawData();
  }
  
  lastScanTime = micros() - start;
  sampleIndex++;
  return true;
}

// === ОТПРАВКА ПАКЕТА ===
void sendPacket() {
  uint16_t dataLen = SAMPLES_PER_PACKET * CHANNELS;
  
  // Заголовок
  Serial.write(0xAA);
  Serial.write(0x55);
  Serial.write((pktCounter >> 8) & 0xFF);
  Serial.write(pktCounter & 0xFF);
  Serial.write((uint8_t)SAMPLES_PER_PACKET);

  // Считаем XOR заголовка
  uint8_t xorSum = 0xAA ^ 0x55 ^ ((pktCounter >> 8) & 0xFF) ^ (pktCounter & 0xFF) ^ (uint8_t)SAMPLES_PER_PACKET;

  // Данные
  for (uint16_t i = 0; i < dataLen; i++) {
    int32_t val = pktData[i];
    uint8_t b3 = (val >> 24) & 0xFF;
    uint8_t b2 = (val >> 16) & 0xFF;
    uint8_t b1 = (val >> 8) & 0xFF;
    uint8_t b0 = val & 0xFF;
    
    Serial.write(b3); Serial.write(b2);
    Serial.write(b1); Serial.write(b0);
    
    xorSum ^= b3 ^ b2 ^ b1 ^ b0;
  }

  Serial.write(xorSum); // Отправляем реальный XOR
  pktCounter++;
  sampleIndex = 0;
}

void updateConfig() {
  // Применяем настройки к регистрам
  writeReg(0x00, 0x32); // STATUS: Buffer ON
  writeReg(0x02, currentPGA); 
  writeReg(0x03, currentDRATE);
  
  // После изменения DRATE или PGA обязательно нужна калибровка
  digitalWrite(PIN_CS, LOW);
  spi2.transfer(0xF0); // SELFCAL
  digitalWrite(PIN_CS, HIGH);
  delay(400); 
}

void processCommands() 
{
  if (Serial.available()) 
  {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    
    if (cmd == "START") 
    {
      streaming = true;
      pktCounter = 0;
      sampleIndex = 0;
      // При старте принудительно обновляем конфиг, чтобы быть уверенными в параметрах
      updateConfig();
      Serial.println(F("STREAMING:STARTED"));
    }
    else if (cmd == "STOP") 
    {
      streaming = false;
      Serial.println(F("STREAMING:STOPPED"));
    } 
    else if (cmd.startsWith("PGA ")) 
    {
      // GUI присылает индекс 0-6
      int pgaIdx = cmd.substring(4).toInt();
      if (pgaIdx >= 0 && pgaIdx <= 7) 
      {
        currentPGA = (uint8_t)pgaIdx;
        if (!streaming) updateConfig(); // Обновляем сразу, если не в потоке
        Serial.print(F("PGA:SET:")); Serial.println(pgaIdx);
      }
    } 
    else if (cmd.startsWith("DRATE ")) 
    {
      int rate = cmd.substring(6).toInt();
      // Соответствие SPS -> байт регистра DRATE
      if (rate == 2000) currentDRATE = 0xB0;
      else if (rate == 5000) currentDRATE = 0xD1; // 7500 у ADS1256 это 0xD1, 3750 это 0xC0
      else if (rate == 10000) currentDRATE = 0xE1; // 15000 SPS
      
      if (!streaming) updateConfig();
      Serial.print(F("DRATE:SET:")); Serial.println(rate);
    }
    else if (cmd == "STATUS") 
    {
      Serial.print(F("STAT:DRATE:0x")); Serial.println(currentDRATE, HEX);
      Serial.print(F("STAT:PGA:")); Serial.println(currentPGA);
    }
  }
}

void loop() {
  processCommands();
  if (streaming) {
    if (readOneScan()) {
      if (sampleIndex >= SAMPLES_PER_PACKET) sendPacket();
    }
  }
}
// #include <ADS1256.h>
// #include <SPI.h>

// // ==== КОНФИГУРАЦИЯ =====
// #define SERIAL_BAUDRATE 230400     // High speed UART (can use 921600 460800 if unstable)
// #define CHANNELS 8                   // Number of ADC channels
// #define SAMPLES_PER_PACKET 25        // Samples per channel in one packet
// #define ADC_DRATE DRATE_2000SPS      // 2000 SPS for 250 Hz per channel

// // Пины для HC-06
// #define BT_TX_PIN PA2   // USART2 TX
// #define BT_RX_PIN PA3   // USART2 RX

// // Пины
// #define PIN_DRDY PB10  // Data Ready - ОБЯЗАТЕЛЬНО!
// #define PIN_RST  PB11  // Reset (опционально, но используется в библиотеке)
// #define PIN_SYNC PA1  // Sync (опционально)
// #define PIN_CS   PB12  // Chip Select

// // SPI
// SPIClass spi2(PB15, PB14, PB13);
// // Конструктор: ADS1256(DRDY_pin, RESET_pin, SYNC_pin, CS_pin, VREF, spi_bus)
// ADS1256 adc(PB10, PB11, PB1, PB12, 2.500, &spi2 );

// // =========== ПРОТОКОЛ ===========
// // [0xAA][0x55][PKT_HI][PKT_LO][N_SAMPLES][DATA: N*8*4 bytes][XOR]
// #define SYNC1 0xAA
// #define SYNC2 0x55

// static int32_t  pktData[SAMPLES_PER_PACKET * CHANNELS];
// static uint16_t pktCounter  = 0;
// static uint16_t sampleIndex = 0;

// static uint32_t totalSamples  = 0;
// static uint32_t drdy_timeouts = 0;
// static bool     streaming     = false;

// // =========== DRDY С ТАЙМАУТОМ ===========
// // Без таймаута один застрявший DRDY вешает систему на секунды!
// inline bool waitDRDY_safe(uint32_t timeout_us = 2000) {
//   uint32_t t0 = micros();
//   while (digitalRead(PIN_DRDY) == HIGH) {
//     if ((micros() - t0) > timeout_us) {
//       drdy_timeouts++;
//       return false;
//     }
//   }
//   return true;
// }

// // =========== СБРОС АЦП ===========
// void resetADC() {
//   adc.sendDirectCommand(0xFE);
//   delay(100);
//   adc.InitializeADC();
//   delay(200);
//   adc.setPGA(0);
//   adc.setDRATE(ADC_DRATE);
//   adc.setBuffer(1);
//   adc.setAutoCal(0);
//   adc.sendDirectCommand(0xF0);
//   delay(200);
// }

// // // Глобальные переменные
// // enum DisplayMode { PLOTTER, LABELS, CSV, BINARY };
// // DisplayMode displayMode = PLOTTER;

// // struct {
// //   float channels[8];
// //   float min[8] = {0, 0, 0, 0, 0, 0, 0, 0};
// //   float max[8] = {0, 0, 0, 0, 0, 0, 0, 0};
// //   float avg[8] = {0, 0, 0, 0, 0, 0, 0, 0};
// //   unsigned long count[8] = {0, 0, 0, 0, 0, 0, 0, 0};
// // } data;

// // unsigned long lastStatsTime = 0;
// // const unsigned long STATS_INTERVAL = 5000; // 5 секунд

// // // Структура для хранения данных канала
// // struct ChannelData {
// //   int32_t raw;
// //   float voltage;
// //   uint8_t channel;
// // };

// void printAllRegisters() {
//   const char* regNames[] = {"STATUS", "MUX", "ADCON", "DRATE", "IO", "OFC0", "OFC1", "OFC2", "FSC0", "FSC1", "FSC2"};
//   for(int i = 0; i < 11; i++) {
//     Serial.print(regNames[i]);
//     Serial.print(" (0x"); Serial.print(i, HEX); Serial.print("): 0x");
//     Serial.println(adc.readRegister(i), HEX);
//   }
// }

// // // последовательное чтение значений с 8 каналов
// // void readAllChannels(ChannelData* data, bool useBuffer = true) {
// //   uint8_t channels[] = {
// //   SING_0, SING_1, SING_2, SING_3,
// //   SING_4, SING_5, SING_6, SING_7 };
// //   for (int i = 0; i < 8; i++) {
// //     adc.setMUX(channels[i]);  // 1. Установка канала
// //     //delay(25);                 // 2. Задержка стабилизации (25 мс)
// //     data[i].raw = adc.readSingle();  // 3. Чтение
// //     data[i].voltage = adc.convertToVoltage(data[i].raw);
// //   }
// // }

// // // Чтение и сразу подготовка следующего 
// // void readAllChannelsOptimized(ChannelData* data) {
  
// //   uint8_t channels[] = {SING_0, SING_1, SING_2, SING_3, SING_4, SING_5, SING_6, SING_7};
  
// //   // Первый канал с задержкой
// //   adc.setMUX(channels[0]);
// //   delay(5); // Уменьшили с 25 мс до 5 мс
  
// //   for (int i = 0; i < 8; i++) {
// //     // Если не последний, готовим следующий канал заранее
// //     if (i < 7) {
// //       // Асинхронно готовим следующий канал
// //       adc.writeRegister(MUX_REG, channels[i+1]);
// //     }
  
// //     // Читаем текущий канал
// //     data[i].raw = adc.readSingle();
// //     data[i].voltage = adc.convertToVoltage(data[i].raw);
// //     data[i].channel = i;
// //   }
// // }

// // void readAllChannelsCyclic(ChannelData* data) {
// //   // Начинаем циклическое чтение
// //   adc.setMUX(SING_0);
// //   adc.readSingleContinuous(); // Запускаем непрерывный режим
  
// //   for (int i = 0; i < 8; i++) {
// //     data[i].raw = adc.readSingleContinuous();
// //     data[i].voltage = adc.convertToVoltage(data[i].raw);
// //     data[i].channel = i;
// //   }
  
// //   // Останавливаем
// //   adc.stopConversion();
// // }
// // //непрерывное чтение 
// // void continuousScan(uint32_t numScans = 0) {
// //   while (true) {
// //     for (int ch = 0; ch < 8; ch++) {
// //       long raw_value = adc.cycleSingle(); 
// //       // int channel = ch % 8;
// //       // Serial.print("  Цикл ");
// //       // Serial.print(ch);
// //       // Serial.print(", Канал ");
// //       // Serial.print(channel);
// //       // Serial.print(": ");
// //       // Serial.print(raw_value);
// //       // Serial.print(" = ");
// //       // Serial.print(adc.convertToVoltage(raw_value), 6);
// //       // Serial.println(" V");
// //     }
// //   }
// // }
// //ChannelData channelDataArray[8];
// // // Тест производительности
// // void testPerformance() {
// //   Serial.println("\n=== ТЕСТ ПРОИЗВОДИТЕЛЬНОСТИ v2 ===");
  
// //   // Устанавливаем высокую скорость для теста
// //   uint8_t originalDRATE = adc.readRegister(DRATE_REG);
// //   adc.setDRATE(DRATE_1000SPS);
// //   delay(100);
  
// //   ChannelData data[8];
  
// //   // Тест быстрого метода
// //   Serial.println("\n1. Быстрый метод (без задержек между каналами):");
  
// //   unsigned long start = micros();
// //   int scans = 20;
  
// //   for (int s = 0; s < scans; s++) {
// //     // Устанавливаем все каналы за один раз (в идеале)
// //     adc.setMUX(SING_0);
// //     delay(1);
    
// //     for (int i = 0; i < 8; i++) {
// //       if (i > 0) {
// //         // Быстрое переключение канала
// //         adc.writeRegister(MUX_REG, SING_0 + (i << 4) | 0x0F);
// //         delayMicroseconds(1); // 100 мкс вместо 25 мс!
// //       }
      
// //       data[i].raw = adc.readSingle();
// //     }
// //   }
  
// //   unsigned long elapsed = micros() - start;
// //   float time_per_scan = elapsed / (float)scans / 1000.0;
  
// //   Serial.print("  Время на скан: ");
// //   Serial.print(time_per_scan, 1);
// //   Serial.println(" мс");
// //   Serial.print("  Сканов в секунду: ");
// //   Serial.println(1000.0 / time_per_scan, 1);
  
// //   // Восстанавливаем скорость
// //   adc.setDRATE(originalDRATE);
// // }

// // ====== НАСТРОЙКА =====
// void setup() {
//   Serial.begin(SERIAL_BAUDRATE);
//   while (!Serial && millis() < 3000); // Wait max 3 seconds for Serial

//   Serial.println("=== ADS1256 Test ===");

//   // 1. Инициализация SPI
//   spi2.begin();
//   // 2. Инициализация ADS1256 с настройками по умолчанию
//   adc.InitializeADC();
//   delay(500);

//   // Проверяем регистры
//   Serial.print("Проверка STATUS: 0x");
//   Serial.println(adc.readRegister(0x00), HEX);
  
//   if (adc.readRegister(0x00) == 0) {
//     Serial.println("ОШИБКА: STATUS регистр равен 0!");
//     Serial.println("Проверьте подключение SPI.");
//     while(1);  // Останавливаем выполнение
//   }
  
//   Serial.println("ADC инициализирован со значениями по умолчанию");
//   // 3. НАСТРОЙКА ПОД НУЖНЫЕ ПАРАМЕТРЫ (после инициализации)
//   // Установка канала (одиночный AIN0)
//   // SING_0 = AIN0+ и AINCOM (одиночный замер на AIN0)
//   //adc.setMUX(SING_0);
//   Serial.print("Канал установлен: ");
//   Serial.println(adc.readRegister(MUX_REG), HEX);

//   adc.setPGA(0);          // Gain = 1 (can adjust: 0-7 for gains 1-64)
//   adc.setDRATE(ADC_DRATE); // Скорость чтения
//   adc.setBuffer(1);       // Enable буфер
//   adc.setAutoCal(0);      // Disable автоколибровка
  
//   // Perform one-time calibration
//   Serial.println("Calibrating...");
//   adc.sendDirectCommand(0xF0); // SELFCAL command
//   delay(300);
  
//   // Устанавливаем стартовый канал для cycleSingle()
//   adc.setMUX(SING_0);
//   delay(10);

//   Serial.print(F("DRATE=0x")); Serial.print(adc.readRegister(0x03), HEX);
//   Serial.print(F("  PGA="));   Serial.println(1 << adc.getPGA());
//   Serial.println(F("Commands: START | STOP | STATUS | PGA <0-7> | DRATE <2000|3750|7500>"));
//   Serial.println(F("Ready.\n"));
// }

// bool readOneScan() {
//   for (uint8_t ch = 0; ch < CHANNELS; ch++) {
//     if (!waitDRDY_safe(2000)) {
//       // 10 подряд таймаутов — сбрасываем АЦП
//       if (drdy_timeouts % 10 == 0) {
//         resetADC();
//         adc.setMUX(SING_0);
//       }
//       return false;
//     }
//     int32_t raw = adc.cycleSingle();
//     pktData[sampleIndex * CHANNELS + ch] = raw;
//   }
//   sampleIndex++;
//   totalSamples++;
//   return true;
// }

// // =========== ОТПРАВКА ПАКЕТА ===========
// void sendPacket() {
//   uint16_t dataLen = SAMPLES_PER_PACKET * CHANNELS;

//   Serial.write(SYNC1);
//   Serial.write(SYNC2);
//   Serial.write((pktCounter >> 8) & 0xFF);
//   Serial.write(pktCounter & 0xFF);
//   Serial.write((uint8_t)SAMPLES_PER_PACKET);

//   uint8_t xorSum = SYNC1 ^ SYNC2
//                  ^ ((pktCounter >> 8) & 0xFF)
//                  ^ (pktCounter & 0xFF)
//                  ^ (uint8_t)SAMPLES_PER_PACKET;

//   for (uint16_t i = 0; i < dataLen; i++) {
//     uint8_t b3 = (pktData[i] >> 24) & 0xFF;
//     uint8_t b2 = (pktData[i] >> 16) & 0xFF;
//     uint8_t b1 = (pktData[i] >>  8) & 0xFF;
//     uint8_t b0 =  pktData[i]        & 0xFF;
//     Serial.write(b3); Serial.write(b2);
//     Serial.write(b1); Serial.write(b0);
//     xorSum ^= b3 ^ b2 ^ b1 ^ b0;
//   }

//   Serial.write(xorSum);
//   pktCounter++;
//   sampleIndex = 0;
// }

// // =========== КОМАНДЫ ===========
// void processCommands() {
//   if (!Serial.available()) return;

//   String cmd = Serial.readStringUntil('\n');
//   cmd.trim();
//   cmd.toUpperCase();

//   if (cmd == "START") {
//     pktCounter = sampleIndex = totalSamples = drdy_timeouts = 0;
//     adc.setMUX(SING_0);
//     delay(5);
//     streaming = true;
//     Serial.println(F("STREAMING:STARTED"));

//   } else if (cmd == "STOP") {
//     streaming = false;
//     Serial.println(F("STREAMING:STOPPED"));

//   } else if (cmd == "STATUS") {
//     Serial.println(F("STATUS:"));
//     Serial.print(F("  Streaming: "));  Serial.println(streaming ? F("YES") : F("NO"));
//     Serial.print(F("  Samples:   "));  Serial.println(totalSamples);
//     Serial.print(F("  Packets:   "));  Serial.println(pktCounter);
//     Serial.print(F("  Timeouts:  "));  Serial.println(drdy_timeouts);
//     Serial.print(F("  DRATE=0x"));     Serial.println(adc.readRegister(0x03), HEX);
//     Serial.print(F("  PGA="));         Serial.println(adc.getPGA());

//   } else if (cmd.startsWith("PGA")) {
//     int pga = cmd.substring(3).toInt();
//     if (pga >= 0 && pga <= 7) {
//       streaming = false;
//       adc.setPGA(pga);
//       delay(10);
//       Serial.print(F("PGA=")); Serial.println(pga);
//     } else { Serial.println(F("ERROR: PGA 0..7")); }

//   } else if (cmd.startsWith("DRATE")) {
//     streaming = false;
//     int rate = cmd.substring(5).toInt();
//     if      (rate == 2000) { adc.setDRATE(DRATE_2000SPS); Serial.println(F("DRATE=2000")); }
//     else if (rate == 3750) { adc.setDRATE(DRATE_3750SPS); Serial.println(F("DRATE=3750")); }
//     else if (rate == 7500) { adc.setDRATE(DRATE_7500SPS); Serial.println(F("DRATE=7500")); }
//     else { Serial.println(F("ERROR: use 2000|3750|7500")); }
//     delay(20);

//   } else {
//     Serial.print(F("Unknown: ")); Serial.println(cmd);
//   }
// }

// void loop() {
//   // Process incoming commands
//   processCommands();
//   if (streaming) {
//     if (readOneScan()) {
//       if (sampleIndex >= SAMPLES_PER_PACKET) {
//         sendPacket();
//       }
//     }
//   }

//   // // ТЕСТ 1: Простое чтение одного значения
//   // Serial.println("\n--- Тест readSingle() ---");
//   // long single_value = adc.readSingle();
//   // Serial.print("readSingle(): ");
//   // Serial.print(single_value);
//   // Serial.print(" = ");
//   // Serial.print(adc.convertToVoltage(single_value), 6);
//   // Serial.println(" V");
  
//   // delay(1000);

//   // // ТЕСТ 2: cycleSingle() - должен переключать каналы
//   // Serial.println("\n--- Тест cycleSingle() ---");
//   // Serial.println("Читаем 16 значений (2 полных цикла по 8 каналов):");
  
//   // for(int i = 0; i < 16; i++) {
//   //   long value = adc.cycleSingle();  // Читаем и автоматически переключаем канал
    
//   //   // Определяем текущий канал (можно вычислить из _cycle, если он public)
//   //   int channel = i % 8;
    
//   //   Serial.print("Цикл ");
//   //   Serial.print(i);
//   //   Serial.print(", Канал ");
//   //   Serial.print(channel);
//   //   Serial.print(": ");
//   //   Serial.print(value);
//   //   Serial.print(" = ");
//   //   Serial.print(adc.convertToVoltage(value), 6);
//   //   Serial.println(" V");
    
//   //   delay(10); // Пауза для видимости в Serial
//   // }
  
//   // // ТЕСТ 3: Остановка и перезапуск
//   // Serial.println("\n--- Останавливаем и перезапускаем ---");
//   // adc.stopConversion();
//   // delay(500);

//   // Способ 2: Ручное управление (для более сложных сценариев)
//   /*
//   // Ждем готовности данных
//   adc.waitForLowDRDY();
  
//   // Запускаем преобразование вручную
//   adc.sendDirectCommand(ADS1256_CMD_SYNC); // Если есть константа
//   delayMicroseconds(10);
//   adc.sendDirectCommand(ADS1256_CMD_WAKEUP);
//   delayMicroseconds(10);
  
//   // Читаем значение
//   int32_t raw_value = adc.readSingle();
//   */
// }
