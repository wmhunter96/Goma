// OLED bring-up test for Sesame: scans I2C, then cycles test patterns on the SSD1306.
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1

// ESP32-DevKitC / Distro Board V1 pins (see firmware README for other boards)
#define I2C_SDA 21
#define I2C_SCL 22

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
uint8_t oledAddr = 0;

void scanI2C() {
  Serial.println("Scanning I2C bus...");
  int found = 0;
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.printf("  Found device at 0x%02X\n", addr);
      if (addr == 0x3C || addr == 0x3D) oledAddr = addr;
      found++;
    }
  }
  if (!found) Serial.println("  No I2C devices found - check wiring (SDA=21, SCL=22, VCC, GND).");
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== Sesame OLED test ===");

  Wire.begin(I2C_SDA, I2C_SCL);
  scanI2C();

  if (!oledAddr) {
    Serial.println("No SSD1306 at 0x3C/0x3D. Halting.");
    return;
  }
  if (!display.begin(SSD1306_SWITCHCAPVCC, oledAddr)) {
    Serial.println("SSD1306 init failed. Halting.");
    oledAddr = 0;
    return;
  }
  Serial.printf("SSD1306 OK at 0x%02X\n", oledAddr);
}

void loop() {
  if (!oledAddr) {
    delay(1000);
    return;
  }

  // 1. Text
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(2);
  display.setCursor(10, 8);
  display.println("SESAME");
  display.setTextSize(1);
  display.setCursor(10, 36);
  display.printf("OLED @ 0x%02X", oledAddr);
  display.setCursor(10, 50);
  display.print("128x64 OK");
  display.display();
  Serial.println("Pattern: text");
  delay(2000);

  // 2. Full white (checks for dead pixels)
  display.fillScreen(SSD1306_WHITE);
  display.display();
  Serial.println("Pattern: full white");
  delay(1500);

  // 3. Border + checkerboard
  display.clearDisplay();
  for (int y = 0; y < SCREEN_HEIGHT; y += 8)
    for (int x = (y / 8) % 2 * 8; x < SCREEN_WIDTH; x += 16)
      display.fillRect(x, y, 8, 8, SSD1306_WHITE);
  display.drawRect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, SSD1306_WHITE);
  display.display();
  Serial.println("Pattern: checkerboard");
  delay(1500);

  // 4. Simple face
  display.clearDisplay();
  display.fillRoundRect(28, 18, 20, 28, 6, SSD1306_WHITE);
  display.fillRoundRect(80, 18, 20, 28, 6, SSD1306_WHITE);
  display.display();
  Serial.println("Pattern: face");
  delay(2000);
}
