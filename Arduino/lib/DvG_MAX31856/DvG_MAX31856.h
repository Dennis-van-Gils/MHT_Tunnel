/***************************************************
  This is a library for the Adafruit Thermocouple Sensor w/MAX31855K

  Designed specifically to work with the Adafruit Thermocouple Sensor
  ----> https://www.adafruit.com/products/269

  These displays use SPI to communicate, 3 pins are required to
  interface
  Adafruit invests time and resources providing this open source code,
  please support Adafruit and open-source hardware by purchasing
  products from Adafruit!

  Written by Limor Fried/Ladyada for Adafruit Industries.
  BSD license, all text above must be included in any redistribution
 ****************************************************/

// Edited by:
// Dennis van Gils, 30-05-2018
// Changed to hardware SPI communication and added support for an Additional
// MCP23017 IO expander chip.

#ifndef DVG_MAX31856_H
#define DVG_MAX31856_H

#include <Arduino.h>
#include <SPI.h>
#include "Adafruit_MCP23017.h"

// SPI settings:
const SPISettings MAX31856_SPI(500000, MSBFIRST, SPI_MODE3);

// Register 0x00: CR0
#define CR0_REG                                 0x00  // MAX31856_CR0_REG
#define CR0_AUTOMATIC_CONVERSION                0x80  // MAX31856_CR0_AUTOCONVERT
#define CR0_ONE_SHOT                            0x40  // MAX31856_CR0_1SHOT
#define CR0_OPEN_CIRCUIT_FAULT1                 0x20  // MAX31856_CR0_OCFAULT1
#define CR0_OPEN_CIRCUIT_FAULT0                 0x10  // MAX31856_CR0_OCFAULT0
#define CR0_COLD_JUNCTION_DISABLED              0x08  // MAX31856_CR0_CJ
#define CR0_FAULT_INTERRUPT_MODE                0x04  // MAX31856_CR0_FAULT
#define CR0_FAULT_CLEAR                         0x02  // MAX31856_CR0_FAULTCLR
#define CR0_NOISE_FILTER_50HZ                   0x01

// Register 0x01: CR1
#define CR1_REG                                 0x01
#define CR1_AVERAGE_1_SAMPLE                    0x00  // ENUM MAX31856_TCTYPE
#define CR1_AVERAGE_2_SAMPLES                   0x10
#define CR1_AVERAGE_4_SAMPLES                   0x20
#define CR1_AVERAGE_8_SAMPLES                   0x30
#define CR1_AVERAGE_16_SAMPLES                  0x40
#define CR1_THERMOCOUPLE_TYPE_B                 0x00
#define CR1_THERMOCOUPLE_TYPE_E                 0x01
#define CR1_THERMOCOUPLE_TYPE_J                 0x02
#define CR1_THERMOCOUPLE_TYPE_K                 0x03
#define CR1_THERMOCOUPLE_TYPE_N                 0x04
#define CR1_THERMOCOUPLE_TYPE_R                 0x05
#define CR1_THERMOCOUPLE_TYPE_S                 0x06
#define CR1_THERMOCOUPLE_TYPE_T                 0x07
#define CR1_VOLTAGE_MODE_GAIN_8                 0x08
#define CR1_VOLTAGE_MODE_GAIN_32                0x0C

// Register 0x02: FAULT MASK
#define CR2_REG                                 0x02  // MAX31856_MASK_REG
#define MASK_COLD_JUNCTION_RANGE                0x80  // MAX31856_FAULT_CJRANGE
#define MASK_THERMOCOUPLE_RANGE                 0x40  // MAX31856_FAULT_TCRANGE
#define MASK_COLD_JUNCTION_HIGH_FAULT           0x20  // MAX31856_FAULT_CJHIGH
#define MASK_COLD_JUNCTION_LOW_FAULT            0x10  // MAX31856_FAULT_CJLOW
#define MASK_THERMOCOUPLE_HIGH_FAULT            0x08  // MAX31856_FAULT_TCHIGH
#define MASK_THERMOCOUPLE_LOW_FAULT             0x04  // MAX31856_FAULT_TCLOW
#define MASK_VOLTAGE_UNDER_OVER_FAULT           0x02  // MAX31856_FAULT_OVUV
#define MASK_THERMOCOUPLE_OPEN_FAULT            0x01  // MAX31856_FAULT_OPEN

// Other registers
#define MAX31856_CJHF_REG          0x03  // Cold-Junction High Fault Threshold
#define MAX31856_CJLF_REG          0x04  // Cold-Junction Low Fault Threshold
#define MAX31856_LTHFTH_REG        0x05  // Linearized Temperature High Fault Threshold MSB
#define MAX31856_LTHFTL_REG        0x06  // Linearized Temperature High Fault Threshold LSB
#define MAX31856_LTLFTH_REG        0x07  // Linearized Temperature Low Fault Threshold MSB
#define MAX31856_LTLFTL_REG        0x08  // Linearized Temperature Low Fault Threshold LSB
#define MAX31856_CJTO_REG          0x09  // Cold-Junction Temperature Offset Register
#define MAX31856_CJTH_REG          0x0A  // Cold-Junction Temperature Register, MSB
#define MAX31856_CJTL_REG          0x0B  // Cold-Junction Temperature Register, LSB
#define MAX31856_LTCBH_REG         0x0C  // Linearized TC Temperature, Byte 2
#define MAX31856_LTCBM_REG         0x0D  // Linearized TC Temperature, Byte 1
#define MAX31856_LTCBL_REG         0x0E  // Linearized TC Temperature, Byte 0
#define MAX31856_SR_REG            0x0F  // Fault Status Register

#if (ARDUINO >= 100)
 #include "Arduino.h"
#else
 #include "WProgram.h"
#endif

class MAX31856 {
 public:
  // Default constructor.
  // Pins DRDY and FAULT are not used.
  MAX31856(int8_t cs);

  // Custom constructor for the case where the CS pin is not on the Arduino
  // itself, but resides on an additionally installed MCP23017 IO expander chip.
  // Pins DRDY and FAULT are not used.
  MAX31856(uint8_t cs, Adafruit_MCP23017* mcp);

  void begin(uint8_t register_CR0, uint8_t register_CR1, uint8_t register_mask);

  uint8_t readFault(void);
  void oneShotTemperature(void);

  float readCJTemperature(void);
  float readThermocoupleTemperature(void);

  void setTempFaultThreshholds(float flow, float fhigh);
  void setColdJunctionFaultThreshholds(int8_t low, int8_t high);

 private:
  int8_t _cs;
  Adafruit_MCP23017* _mcp;

  void readRegisterN(uint8_t addr, uint8_t buffer[], uint8_t n);

  uint8_t  readRegister8(uint8_t addr);
  uint16_t readRegister16(uint8_t addr);
  uint32_t readRegister24(uint8_t addr);

  void     writeRegister8(uint8_t addr, uint8_t reg);
};

#endif
