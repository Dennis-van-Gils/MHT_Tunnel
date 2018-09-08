/*******************************************************************************
  DvG_RT_click_mA

  A library for the 4-20 mA current controllers of MIKROE
  - 4-20 mA R click (receiver)
  - 4-20 mA T Click (transmitter)
  Both operate over the SPI bus

  Maximal SPI clock frequency for MCP3204 (R click) and MCP3201 (T click)
  running at 3.3V is 1 MHz.

  Dennis van Gils
  30-08-2017
*******************************************************************************/
/*******************************************************************************
Additional notes from John Cabrer, wildseyed@gmail.com

According to other code examples for PIC, the 4-20 mA T click takes values from
~ 800 to ~ 4095 for the current control. The four most significant bits are for
control, and should be 0011 where:

bit 15
  1 = Ignore this command
  0 = Write to DAC register
bit 14 BUF: VREF Input Buffer Control bit
  1 = Buffered
  0 = Unbuffered
bit 13 GA: Output Gain Selection bit
  1 = 1x (VOUT = VREF * D/4096)
  0 = 2x (VOUT = 2 * VREF * D/4096)
bit 12 SHDN: Output Shutdown Control bit
  1 = Active mode operation. VOUT is available.
  0 = Shutdown the device. Analog output is not available. VOUT pin is
      connected to 500 kOhm (typical)
bit 11-0 D11:D0: DAC Input Data bits. Bit x is ignored
*******************************************************************************/

#ifndef DvG_RT_click_mA_h
#define DvG_RT_click_mA_h

#include <Arduino.h>
#include <SPI.h>

// SPI settings:
// Maximal SPI clock frequency for MCP3204 (R click) and MCP3201 (T click)
// running at 3.3V is 1 MHz.
const SPISettings RT_CLICK_SPI(1000000, MSBFIRST, SPI_MODE0);

const byte JUNK = 0xFF;

/*******************************************************************************
  T_Click
*******************************************************************************/

class T_Click {
public:
  // Constructor
  // SS_pin          : slave select pin corresponding to the T click board
  // p1_mA, p1_bitVal: point 1 for the linear interpolation
  // p2_mA, p2_bitVal: point 2 for the linear interpolation
  // Points 1 and 2 should be determined per R click board by calibration
  // against a digital multimeter, e.g.
  // p1_mA =  4.00 (read from multimeter), p1_bitVal =  798 (set by Arduino)
  // p2_mA = 20.51 (read from multimeter), p2_bitVal = 4095 (set by Arduino)
  T_Click(uint8_t SS_pin, float p1_mA, uint16_t p1_bitVal,
                          float p2_mA, uint16_t p2_bitVal);

  // Start SPI and set up GPIO
  void begin();

  // Set the output current [mA]
  void set_mA(float mA_value);

  // Returns the bit value belonging to the last set current
  uint16_t get_last_set_bitVal();

private:
  uint8_t _SS_pin;        // Slave Select pin
  float   _p1_mA;         // point 1 for linear interpolation [mA]
  float   _p2_mA;         // point 2 for linear interpolation [mA]
  uint16_t _p1_bitVal;    // point 1 for linear interpolation [bit value]
  uint16_t _p2_bitVal;    // point 2 for linear interpolation [bit value]
  uint16_t _set_bitVal;   // last set bit value
};

/*******************************************************************************
  R_Click
*******************************************************************************/

class R_Click {
public:
  // Constructor
  // SS_pin          : slave select pin corresponding to the R click board
  // p1_mA, p1_bitVal: point 1 for the linear interpolation
  // p2_mA, p2_bitVal: point 2 for the linear interpolation
  // Points 1 and 2 should be determined per R click board by calibration
  // against a digital multimeter, e.g.
  // p1_mA =  4.0 (read from multimeter), p1_bitVal =  781 (read by Arduino)
  // p2_mA = 20.0 (read from multimeter), p2_bitVal = 3963 (read by Arduino)
  R_Click(uint8_t SS_pin, float p1_mA, uint16_t p1_bitVal,
                          float p2_mA, uint16_t p2_bitVal);

  // Start SPI and set up GPIO
  void begin();

  // NB: Keep input argument of type 'float' to accomodate for a running average
  // that could have been applied to the bit value
  float bitVal2mA(float bitVal);

  // Reads and returns the bit value
  uint32_t read_bitVal();

  // Reads the bit value and returns the corresponding current in [mA]
  float read_mA();

private:
  uint8_t _SS_pin;        // Slave Select pin [DO]
  float   _p1_mA;         // point 1 for linear interpolation [mA]
  float   _p2_mA;         // point 2 for linear interpolation [mA]
  uint16_t _p1_bitVal;    // point 1 for linear interpolation [bit value]
  uint16_t _p2_bitVal;    // point 2 for linear interpolation [bit value]
};

#endif
