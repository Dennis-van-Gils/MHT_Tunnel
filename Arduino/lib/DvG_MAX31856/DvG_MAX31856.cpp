/***************************************************
  This is a library for the Adafruit Thermocouple Sensor w/MAX31856

  Designed specifically to work with the Adafruit Thermocouple Sensor
  ----> https://www.adafruit.com/product/3263

  These sensors use SPI to communicate, 4 pins are required to
  interface
  Adafruit invests time and resources providing this open source code,
  please support Adafruit and open-source hardware by purchasing
  products from Adafruit!

  Written by Limor Fried/Ladyada for Adafruit Industries.
  BSD license, all text above must be included in any redistribution
 ****************************************************/

// Edited by:
// Dennis van Gils, 30-05-2018
// - Changed to hardware SPI communication
// - Added support for an additional MCP23017 IO expander chip
// - Changed to auto-conversion mode, instead of single-shot

#include "DvG_MAX31856.h"
#ifdef __AVR
  #include <avr/pgmspace.h>
#elif defined(ESP8266)
  #include <pgmspace.h>
#endif

#include <stdlib.h>

// Default constructor.
// The DRDY and FAULT outputs from the MAX31856 are not used in this library.
MAX31856::MAX31856(int8_t cs) {
  _cs = cs;
  _mcp = NULL;
}

// Custom constructor for the case where the CS pin is not on the Arduino
// itself, but resides on an additionally installed MCP23017 IO expander chip.
// The DRDY and FAULT outputs from the MAX31856 are not used in this library.
MAX31856::MAX31856(uint8_t cs, Adafruit_MCP23017* mcp) {
  _cs = cs;
  _mcp = mcp;
}

void MAX31856::begin(uint8_t register_CR0,
                     uint8_t register_CR1,
                     uint8_t register_mask) {
  // Initialize the slave select pin
  if (_mcp) {
    _mcp->pinMode(_cs, OUTPUT);
    _mcp->digitalWrite(_cs, HIGH);
  } else {
    pinMode(_cs, OUTPUT);
    digitalWrite(_cs, HIGH);
  }

  SPI.begin();

  // Initializing the MAX31855's registers
  writeRegister8(CR0_REG, register_CR0);
  writeRegister8(CR1_REG, register_CR1);
  writeRegister8(CR2_REG, register_mask);
}

uint8_t MAX31856::readFault(void) {
  return readRegister8(MAX31856_SR_REG);
}

void MAX31856::setColdJunctionFaultThreshholds(int8_t low, int8_t high) {
  writeRegister8(MAX31856_CJLF_REG, low);
  writeRegister8(MAX31856_CJHF_REG, high);
}

void MAX31856::setTempFaultThreshholds(float flow, float fhigh) {
  int16_t low, high;

  flow *= 16;
  low = flow;

  fhigh *= 16;
  high = fhigh;

  writeRegister8(MAX31856_LTHFTH_REG, high >> 8);
  writeRegister8(MAX31856_LTHFTL_REG, high);

  writeRegister8(MAX31856_LTLFTH_REG, low >> 8);
  writeRegister8(MAX31856_LTLFTL_REG, low);
}

float MAX31856::readCJTemperature(void) {
  int16_t temp16 = readRegister16(MAX31856_CJTH_REG);
  float tempfloat = temp16;
  tempfloat /= 256.0;

  return tempfloat;
}

float MAX31856::readThermocoupleTemperature(void) {
  // One-shot temperature
  writeRegister8(CR0_REG, CR0_ONE_SHOT + CR0_NOISE_FILTER_50HZ);
  delay(150);

  int32_t temp24 = readRegister24(MAX31856_LTCBH_REG);

  if (temp24 & 0x800000) {
    temp24 |= 0xFF000000;  // fix sign
  }

  temp24 >>= 5;  // bottom 5 bits are unused

  float tempfloat = temp24;
  tempfloat *= 0.0078125; // deg C
  //tempfloat /= 1677.7216;  // millivolts

  return tempfloat;
}

/**********************************************/

uint8_t MAX31856::readRegister8(uint8_t addr) {
  uint8_t ret = 0;
  readRegisterN(addr, &ret, 1);

  return ret;
}

uint16_t MAX31856::readRegister16(uint8_t addr) {
  uint8_t buffer[2] = {0, 0};
  readRegisterN(addr, buffer, 2);

  uint16_t ret = buffer[0];
  ret <<= 8;
  ret |=  buffer[1];

  return ret;
}

uint32_t MAX31856::readRegister24(uint8_t addr) {
  uint8_t buffer[3] = {0, 0, 0};
  readRegisterN(addr, buffer, 3);

  uint32_t ret = buffer[0];
  ret <<= 8;
  ret |=  buffer[1];
  ret <<= 8;
  ret |=  buffer[2];

  return ret;
}

void MAX31856::readRegisterN(uint8_t addr, uint8_t buffer[], uint8_t n) {
  addr &= 0x7F; // make sure top bit is not set

  SPI.beginTransaction(MAX31856_SPI);
  if (_mcp) {_mcp->digitalWrite(_cs, LOW);} else {digitalWrite(_cs, LOW);}

  SPI.transfer(addr);
  //Serial.print("$"); Serial.print(addr, HEX); Serial.print(": ");

  while (n--) {
    buffer[0] = SPI.transfer(0xFF);
    //Serial.print(" 0x"); Serial.print(buffer[0], HEX);
    buffer++;
  }
  //Serial.println();

  if (_mcp) {_mcp->digitalWrite(_cs, HIGH);} else {digitalWrite(_cs, HIGH);}
  SPI.endTransaction();
}


void MAX31856::writeRegister8(uint8_t addr, uint8_t data) {
  addr |= 0x80; // make sure top bit is set

  SPI.beginTransaction(MAX31856_SPI);
  if (_mcp) {_mcp->digitalWrite(_cs, LOW);} else {digitalWrite(_cs, LOW);}

  SPI.transfer(addr);
  SPI.transfer(data);
  //Serial.print("$"); Serial.print(addr, HEX);
  //Serial.print(" = 0x"); Serial.println(data, HEX);

  if (_mcp) {_mcp->digitalWrite(_cs, HIGH);} else {digitalWrite(_cs, HIGH);}
  SPI.endTransaction();
}
