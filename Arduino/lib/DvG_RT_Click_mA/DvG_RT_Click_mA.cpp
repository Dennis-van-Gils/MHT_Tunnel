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

#include "DvG_RT_click_mA.h"

/*******************************************************************************
  T_Click
*******************************************************************************/

T_Click::T_Click(uint8_t SS_pin, float p1_mA, uint16_t p1_bitVal,
                                 float p2_mA, uint16_t p2_bitVal) {
  _SS_pin = SS_pin;
  _p1_mA = p1_mA;
  _p2_mA = p2_mA;
  _p1_bitVal = p1_bitVal;
  _p2_bitVal = p2_bitVal;
}

// Start SPI and set up GPIO
void T_Click::begin() {
  SPI.begin();                      // Start SPI
  digitalWrite(_SS_pin, HIGH);      // Disable the slave SPI device for now
  pinMode(_SS_pin, OUTPUT);         // Set up GPIO for output

  // Force output to 4 mA at the start
  set_mA(4.0);
}

// Set the output current [mA]
void T_Click::set_mA(float mA_value) {
  uint16_t bitVal;
  byte     bitVal_Hi;
  byte     bitVal_Lo;

  // Transform current [mA] to bit value
  bitVal = (int) round((mA_value - _p1_mA) / (_p2_mA - _p1_mA) *
           (_p2_bitVal - _p1_bitVal) + _p1_bitVal);
  _set_bitVal = bitVal;

  // The standard Arduino SPI library handles data of 8 bits long
  // The MIKROE T Click shield is 12 bits, hence transfer in two steps
  bitVal_Hi = (bitVal >> 8) & 0x0F;   // 0x0F = 15
  bitVal_Hi |= 0x30;                  // 0x30 = 48
  bitVal_Lo = bitVal;

  SPI.beginTransaction(RT_CLICK_SPI);
  digitalWrite(_SS_pin, LOW);         // enable slave device
  SPI.transfer(bitVal_Hi);            // transfer highbyte
  SPI.transfer(bitVal_Lo);            // transfer lowbyte
  digitalWrite(_SS_pin, HIGH);        // disable slave device
  SPI.endTransaction();
}

// Returns the bit value belonging to the last set current
uint16_t T_Click::get_last_set_bitVal() {
  return _set_bitVal;
}

/*******************************************************************************
  R_Click
*******************************************************************************/

R_Click::R_Click(uint8_t SS_pin, float p1_mA, uint16_t p1_bitVal,
                                 float p2_mA, uint16_t p2_bitVal) {
  _SS_pin = SS_pin;
  _p1_mA = p1_mA;
  _p2_mA = p2_mA;
  _p1_bitVal = p1_bitVal;
  _p2_bitVal = p2_bitVal;
}

// Start SPI and set up GPIO
void R_Click::begin() {
  SPI.begin();                   // Start SPI
  digitalWrite(_SS_pin, HIGH);   // Disable the slave SPI device for now
  pinMode(_SS_pin, OUTPUT);      // Set up GPIO for output
}

float R_Click::bitVal2mA(float bitVal) {
  return (_p1_mA + (bitVal - _p1_bitVal) /
          float(_p2_bitVal - _p1_bitVal) * (_p2_mA - _p1_mA));
}

// Reads and returns the bit value
uint32_t R_Click::read_bitVal() {
  byte incomingData_Hi;
  byte incomingData_Lo;

  // The standard Arduino SPI library handles data of 8 bits long
  // The MIKROE R Click shield is 12 bits, hence transfer in two steps
  SPI.beginTransaction(RT_CLICK_SPI);
  digitalWrite(_SS_pin, LOW);           // Enable slave device
  incomingData_Hi = SPI.transfer(JUNK) & 0x1F;
  incomingData_Lo = SPI.transfer(JUNK);
  digitalWrite(_SS_pin, HIGH);          // Disable slave device
  SPI.endTransaction();

  // Reconstruct bit value
  return (uint32_t) ((incomingData_Hi << 8) | incomingData_Lo) >> 1;
}

float R_Click::read_mA() {
  return bitVal2mA(R_Click::read_bitVal());
}
