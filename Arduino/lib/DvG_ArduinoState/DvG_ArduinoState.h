/*******************************************************************************
  DvG_ArduinoState

  Dennis van Gils
  15-06-2018
*******************************************************************************/

#ifndef DvG_ArduinoState_h
#define DvG_ArduinoState_h

#include <Arduino.h>

char* float2string(float value, uint8_t precision);

// Calculate free SRAM during run-time (32 KB available on M0 Pro)
extern "C" char *sbrk(int i);
size_t get_free_RAM();

// Finite state machine (FSM) programs of the filling system (FS)
enum FSM_FS_PROGRAMS : uint8_t {FSM_FS_PROGRAMS_idle,
                                FSM_FS_PROGRAMS_barrel_1_to_tunnel,
                                FSM_FS_PROGRAMS_barrel_2_to_tunnel,
                                FSM_FS_PROGRAMS_tunnel_to_barrel_1,
                                FSM_FS_PROGRAMS_tunnel_to_barrel_2,
                                FSM_FS_PROGRAMS_barrel_1_to_sewer,
                                FSM_FS_PROGRAMS_barrel_2_to_sewer,
                                FSM_FS_PROGRAMS_tunnel_to_sewer};

/*******************************************************************************
  State_Arduino_1
  Reflects the actual state and readings of Arduino #1
*******************************************************************************/

class State_Arduino_1 {
public:
  State_Arduino_1();

  // Relay states
  bool relay_01, relay_02, relay_03, relay_04, relay_05, relay_06, relay_07,
       relay_08, relay_09;

  // Setpoint of the 4-20 mA current transmitter: tunnel pump speed
  float set_pump_speed_mA;
  float set_pump_speed_pct;   // Is not reported, for internal use only

  // Readings of the 4-20 mA current receiver: gas volume fraction differential
  // pressure
  float read_GVF_P_diff_bitV;
  float read_GVF_P_diff_mA;
  float read_GVF_P_diff_mbar;

  // Readings of the 4-20 mA current receiver: mass flow rate
  float read_flow_rate_bitV;
  float read_flow_rate_mA;
  float read_flow_rate_m3h;   // Is not reported, for internal use only

  // PID control parameters of the tunnel flow rate
  bool  ENA_PID_pump;
  float setpoint_flow_rate_m3h;

  // Over-temperature protection (OTP) heaters
  bool ENA_OTP;

  // Send the full state and readings of the Arduino over the serial port.
  // Tab delimited
  void report(Stream& ser);
};

/*******************************************************************************
  State_Arduino_2
  Reflects the actual state and readings of Arduino #1
*******************************************************************************/

class State_Arduino_2 {
public:
  State_Arduino_2();

  // Relay states
  bool relay_01, relay_02, relay_03, relay_04, relay_05, relay_06, relay_07,
       relay_08;

  // Input switch states
  bool prox_switch_1, prox_switch_2, prox_switch_3, prox_switch_4,
       floater_switch;

  // Finite state machine (FSM) program of the filling system (FS) currently
  // being executed
  enum FSM_FS_PROGRAMS FSM_FS_exec;

  // Number of unread filling system messages (by the Python control program or
  // another external listener) in the queue
  uint8_t FS_unread_msgs_count;

  // Send the full state and readings of the Arduino over the serial port.
  // Tab delimited
  void report(Stream& ser);
};

#endif
