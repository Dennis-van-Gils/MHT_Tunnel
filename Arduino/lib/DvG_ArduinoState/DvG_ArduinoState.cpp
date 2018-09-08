/*******************************************************************************
  DvG_ArduinoState

  Dennis van Gils
  15-06-2018
*******************************************************************************/

#include "DvG_ArduinoState.h"
#include <avr/dtostrf.h>

char buff[10];     // Float to string conversion buffer

char* float2string(float value, uint8_t precision) {
  dtostrf(value, 9, precision, buff);
  return buff;
}

// Calculate free SRAM during run-time (32 KB available on M0 Pro)
size_t get_free_RAM() {
  char stack_dummy = 0;
  return (&stack_dummy - sbrk(0));
}

/*******************************************************************************
  State_Arduino_1
  Reflects the actual state and readings of Arduino #1
*******************************************************************************/

State_Arduino_1::State_Arduino_1() {
  // Relay states
  relay_01 = false;
  relay_02 = false;
  relay_03 = false;
  relay_04 = false;
  relay_05 = false;
  relay_06 = false;
  relay_07 = false;
  relay_08 = false;
  relay_09 = false;

  // Setpoint of the 4-20 mA current transmitter: tunnel pump speed
  set_pump_speed_mA = 4.0;
  set_pump_speed_pct = 0.0;

  // Readings of the 4-20 mA current receiver: gas volume fraction differential
  // pressure
  read_GVF_P_diff_bitV = NAN;
  read_GVF_P_diff_mA   = NAN;
  read_GVF_P_diff_mbar = NAN;

  // Readings of the 4-20 mA current receiver: mass flow rate
  read_flow_rate_bitV = NAN;
  read_flow_rate_mA   = NAN;
  read_flow_rate_m3h  = NAN;

  // PID control parameters of the tunnel flow rate
  ENA_PID_pump = false;
  setpoint_flow_rate_m3h = 0.0;

  // Over-temperature protection (OTP) heaters
  ENA_OTP = true;
}

// Send the full state and readings of the Arduino over the passed serial port
// tab delimited
void State_Arduino_1::report(Stream& Ser) {
  String msg;

  msg = String(get_free_RAM()) + '\t' +
        ENA_OTP + '\t' +
        relay_01 + '\t' + relay_02 + '\t' + relay_03 + '\t' + relay_04 + '\t' +
        relay_05 + '\t' + relay_06 + '\t' + relay_07 + '\t' + relay_08 + '\t' +
        relay_09 + '\t' +
        String(read_GVF_P_diff_bitV) + '\t' +
        String(read_GVF_P_diff_mA) + '\t' +
        String(read_GVF_P_diff_mbar) + '\t' +
        String(float2string(set_pump_speed_mA, 3)) + '\t' +
        String(read_flow_rate_bitV) + '\t' +
        String(float2string(read_flow_rate_mA, 3)) + '\t' +
        ENA_PID_pump + '\t' +
        String(setpoint_flow_rate_m3h);
  Ser.println(msg);
}

/*******************************************************************************
  State_Arduino_2
  Reflects the actual state and readings of Arduino #2
*******************************************************************************/

State_Arduino_2::State_Arduino_2() {
  // Relay states
  relay_01 = false;
  relay_02 = false;
  relay_03 = false;
  relay_04 = false;
  relay_05 = false;
  relay_06 = false;
  relay_07 = false;
  relay_08 = false;

  // Input switch states
  prox_switch_1  = false;
  prox_switch_2  = false;
  prox_switch_3  = false;
  prox_switch_4  = false;
  floater_switch = false;

  // Finite state machine (FSM) program of the filling system (FS) currently
  // being executed
  FSM_FS_exec = FSM_FS_PROGRAMS_idle;

  // Number of unread messages (by the Python control program or another
  // external listener) in the queue
  FS_unread_msgs_count = 0;
}

// Send the full state and readings of the Arduino over the passed serial port
// tab delimited
void State_Arduino_2::report(Stream& Ser) {
  String msg;

  msg = String(get_free_RAM()) + '\t' +
        relay_01 + '\t' + relay_02 + '\t' + relay_03 + '\t' + relay_04 + '\t' +
        relay_05 + '\t' + relay_06 + '\t' + relay_07 + '\t' + relay_08 + '\t' +
        prox_switch_1 + '\t' + prox_switch_2 + '\t' +
        prox_switch_3 + '\t' + prox_switch_4 + '\t' +
        floater_switch + '\t' + FSM_FS_exec + '\t' + FS_unread_msgs_count;
  Ser.println(msg);
}
