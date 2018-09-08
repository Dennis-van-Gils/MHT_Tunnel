/*******************************************************************************
  Twente MHT Tunnel - ARDUINO #2

  Hardware:
    - Arduino M0 Pro
    - [Deprecated]
      J-type thermocouple amplifier board from PlayingWithFusion.com
      SEN30103-R01 without voltage offset, Chip: ADB8494
      NOTE: ALL REMOVED ON 02-05-2018 AND REPLACED BY:
    - [Deprecated]
      J-type thermocouple amplifier board from PlayingWithFusion.com
      MAX31856 Thermocouple Sensor Breakout (4ch, J-Type)
      SEN-30008-J, Chip: MAX31856
      Each signal gets digitized on the amplifier board   [SPI bus]
      NOTE: ALSO ALL REMOVED ON 05-06-2018 AND REPLACED BY AN AGILENT
      34970A data acquisition/switch unit controlled by Python
    - Sainsmart 8ch. Relay Module board
    - 4 capacitive proximity switches
    - floater switch

  Connections:
    - prox_switch_1 : full barrel 1 (water)? (NC)
    - prox_switch_2 : full barrel 2 (brine)? (NC)
    - prox_switch_3 : empty barrel?
    - prox_switch_4 : empty tunnel?
    - floater_switch: full tunnel?   (NO wired, but mounted NC 'upside-down')

    For all above switches the following states are used, regardless of being
    connected NO or NC:
      0: no water present
      1: water present

    - empty_pipe    : empty pipe warning (DO2 from flow meter)

    - relay_01: filling_valve_1, 0 = barrel 1 (water), 1 = barrel 2 (brine)
    - relay_02: filling_valve_2
    - relay_03: filling_valve_3
    - relay_04: filling_valve_4
    - relay_05: filling_valve_5
    - relay_06: filling_valve_6
    - relay_07: filling_pump
    - relay_08: n.c.

    USB communications:
      - Programming USB port (UART): 'Serial'
        Windows name: Atmel Corp. EDBG USB Port
        Baudrate: 115200

        Clocked max. DAQ rate in Python: ~64 Hz

      - Native USB port (USART): 'SerialUSB'
        Windows name: Arduino M0 PRO Native Port
        Baudrate: not fixed and as fast as possible

        Clocked max. DAQ rate in Python: variable ~120 Hz

  Dennis van Gils
  04-09-2018
*******************************************************************************/

#include <Arduino.h>
#include "Adafruit_SleepyDog.h"              // Watchdog timer
#include "Bounce2.h"

#include "DvG_SerialCommand.h"
#include "DvG_SensorClasses.h"
#include "DvG_ArduinoState.h"
#include "DvG_RT_Click_mA.h"

#include "FiniteStateMachine.h"
#include "QueueList_modified.h"

// Serial port definitions
// Serial   : Programming USB port.
// SerialUSB: Native USB port. Baudrate ignored and is as fast as possible.
#define Ser_python SerialUSB
#define Ser_debug  Serial

// Initiate serial command listener
DvG_SerialCommand sc_python(Ser_python);
DvG_SerialCommand sc_debug(Ser_debug);

// -----------------------------------------------------------------------------
//   Pin definitions
// -----------------------------------------------------------------------------

#define PIN_PROX_SWITCH_1  2
#define PIN_PROX_SWITCH_2  3
#define PIN_PROX_SWITCH_3  4
#define PIN_PROX_SWITCH_4  5
#define PIN_FLOATER_SWITCH 13
#define PIN_EMPTY_PIPE     1

#define PIN_RELAY_01  0
#define PIN_RELAY_02  6
#define PIN_RELAY_03  7
#define PIN_RELAY_04  8
#define PIN_RELAY_05  9
#define PIN_RELAY_06  10
#define PIN_RELAY_07  11
#define PIN_RELAY_08  12

// -----------------------------------------------------------------------------
//   Relays
// -----------------------------------------------------------------------------

Relay relay_01(PIN_RELAY_01);
Relay relay_02(PIN_RELAY_02);
Relay relay_03(PIN_RELAY_03);
Relay relay_04(PIN_RELAY_04);
Relay relay_05(PIN_RELAY_05);
Relay relay_06(PIN_RELAY_06);
Relay relay_07(PIN_RELAY_07);
Relay relay_08(PIN_RELAY_08);

// -----------------------------------------------------------------------------
//   Input switches with software debounce feature
// -----------------------------------------------------------------------------

Bounce prox_switch_1 = Bounce();
Bounce prox_switch_2 = Bounce();
Bounce prox_switch_3 = Bounce();
Bounce prox_switch_4 = Bounce();
Bounce floater_switch = Bounce();

// Digital input without debounce
bool empty_pipe = true;     // TO DO: move variable to State

// -----------------------------------------------------------------------------
//   This class instance reflects the actual state and readings of the Arduino
// -----------------------------------------------------------------------------

State_Arduino_2 state;

// -----------------------------------------------------------------------------
//   Create a queue of string messages regarding the filling system (FS) to be
//   received by the Python control program
// -----------------------------------------------------------------------------

#define FS_MAX_MSG_QUEUE 10
QueueList <String> FS_msg_queue;

// Re-occuring messages
#define F_BARREL_1_IS_EMPTY "--> barrel 1 is empty"
#define F_BARREL_2_IS_EMPTY "--> barrel 2 is empty"
#define F_TUNNEL_IS_EMPTY   "--> tunnel is empty"
#define F_BARREL_1_IS_FULL  "--> barrel 1 is full"
#define F_BARREL_2_IS_FULL  "--> barrel 2 is full"
#define F_TUNNEL_IS_FULL    "--> tunnel is full"
const String F_CR         = "\r    ";

void FS_push_msg(String msg) {
  FS_msg_queue.push(msg);     // Push string message onto the queue
  msg.replace("\r", "\r\n");  // Change to CRLF conform the debug serial monitor
  Ser_debug.println(msg);     // Report message to the debug serial output
}

// -----------------------------------------------------------------------------
//   Finite State Machines
//   ALL the functions below are helper functions for the states of the program
//
//   Abbrevations:
//      FSM: finite state machine
//      FS : filling system
// -----------------------------------------------------------------------------

const uint32_t FS_TIMER1_DELAY = 5000;  // Filling system timer 1
const String F_WAIT = ("wait" + String(FS_TIMER1_DELAY/1000., 0) + " sec");

// -----------------------------------------------------------------------------
//   FS: Idle
// -----------------------------------------------------------------------------

void FS_idle__enter() {
  FS_push_msg("FS: idle");

  // Garantuee closed filling valves, apart from 3-way filling_valve_1,
  // and stop the pump
  relay_02.setStateToBeActuated(Relay::off);  // filling_valve_2
  relay_03.setStateToBeActuated(Relay::off);  // filling_valve_3
  relay_04.setStateToBeActuated(Relay::off);  // filling_valve_4
  relay_05.setStateToBeActuated(Relay::off);  // filling_valve_5
  relay_06.setStateToBeActuated(Relay::off);  // filling_valve_6
  relay_07.setStateToBeActuated(Relay::off);  // filling_pump
}

void FS_idle__update() {}
void FS_idle__exit() {}
State FS_idle = State(FS_idle__enter, FS_idle__update, FS_idle__exit);

FSM FSM_FS = FSM(FS_idle);

// -----------------------------------------------------------------------------
//   FS: Barrel 1 to tunnel
// -----------------------------------------------------------------------------

void FS_barrel_1_to_tunnel__enter() {
  FS_push_msg("FS: barrel 1 to tunnel");

  // First check if the tunnel isn't already full
  if (state.floater_switch) {
    FS_push_msg(F_TUNNEL_IS_FULL);
    FSM_FS.immediateTransitionTo(FS_idle);
  } else {
    // Switch 3-way filling_valve_1, open filling_valve_2 and wait to flood the
    // pipe at prox_switch_3
    FS_push_msg("--> switch to barrel 1" + F_CR + "open valve 2" + F_CR +
                F_WAIT);
    relay_01.setStateToBeActuated(Relay::off);  // filling_valve_1
    relay_02.setStateToBeActuated(Relay::on);   // filling_valve_2
  }
}

void FS_barrel_1_to_tunnel__update() {
  static uint8_t tracker = 0;

  if (FSM_FS.timeInCurrentState() < FS_TIMER1_DELAY) {
    // Filling_valve_2 is open and wait to flood the pipe at prox_switch_3
    tracker = 0;
  } else {
    if (state.floater_switch) {
      FS_push_msg(F_TUNNEL_IS_FULL);
      FSM_FS.immediateTransitionTo(FS_idle);
    } else if (!(state.prox_switch_3)) {
      FS_push_msg(F_BARREL_1_IS_EMPTY);
      FSM_FS.immediateTransitionTo(FS_idle);
    } else if (tracker == 0) {
      FS_push_msg("--> open valve 5" + F_CR + "pump");
      relay_05.setStateToBeActuated(Relay::on);   // filling_valve_5
      relay_07.setStateToBeActuated(Relay::on);   // filling_pump
      tracker = 1;
    }
  }
}

void FS_barrel_1_to_tunnel__exit() {
  relay_02.setStateToBeActuated(Relay::off);  // filling_valve_2
  relay_05.setStateToBeActuated(Relay::off);  // filling_valve_5
  relay_07.setStateToBeActuated(Relay::off);  // filling_pump
}

State FS_barrel_1_to_tunnel = State(FS_barrel_1_to_tunnel__enter,
                                    FS_barrel_1_to_tunnel__update,
                                    FS_barrel_1_to_tunnel__exit);

// -----------------------------------------------------------------------------
//   FS: Barrel 2 to tunnel
// -----------------------------------------------------------------------------

void FS_barrel_2_to_tunnel__enter() {
  FS_push_msg("FS: barrel 2 to tunnel");

  // First check if the tunnel isn't already full
  if (state.floater_switch) {
    FS_push_msg(F_TUNNEL_IS_FULL);
    FSM_FS.immediateTransitionTo(FS_idle);
  } else {
    // Switch 3-way filling_valve_2, open filling_valve_2 and wait to flood the
    // pipe at prox_switch_3
    FS_push_msg("--> switch to barrel 2" + F_CR + "open valve 2" + F_CR +
                F_WAIT);
    relay_01.setStateToBeActuated(Relay::on);   // filling_valve_1
    relay_02.setStateToBeActuated(Relay::on);   // filling_valve_2
  }
}

void FS_barrel_2_to_tunnel__update() {
  static uint8_t tracker = 0;

  if (FSM_FS.timeInCurrentState() < FS_TIMER1_DELAY) {
    // Filling_valve_2 is open and wait to flood the pipe at prox_switch_3
    tracker = 0;
  } else {
    if (state.floater_switch) {
      FS_push_msg(F_TUNNEL_IS_FULL);
      FSM_FS.immediateTransitionTo(FS_idle);
    } else if (!(state.prox_switch_3)) {
      FS_push_msg(F_BARREL_2_IS_EMPTY);
      FSM_FS.immediateTransitionTo(FS_idle);
    } else if (tracker == 0) {
      FS_push_msg("--> open valve 5" + F_CR + "pump");
      relay_05.setStateToBeActuated(Relay::on);   // filling_valve_5
      relay_07.setStateToBeActuated(Relay::on);   // filling_pump
      tracker = 1;
    }
  }
}

void FS_barrel_2_to_tunnel__exit() {
  relay_02.setStateToBeActuated(Relay::off);  // filling_valve_2
  relay_05.setStateToBeActuated(Relay::off);  // filling_valve_5
  relay_07.setStateToBeActuated(Relay::off);  // filling_pump
}

State FS_barrel_2_to_tunnel = State(FS_barrel_2_to_tunnel__enter,
                                    FS_barrel_2_to_tunnel__update,
                                    FS_barrel_2_to_tunnel__exit);

// -----------------------------------------------------------------------------
//  FS: Tunnel to barrel 1
// -----------------------------------------------------------------------------

void FS_tunnel_to_barrel_1__enter() {
  FS_push_msg("FS: tunnel to barrel 1");

  // First check if the tunnel isn't already empty
  if (!(state.prox_switch_4)) {
    FS_push_msg(F_TUNNEL_IS_EMPTY);
    FSM_FS.immediateTransitionTo(FS_idle);
  } else if (state.prox_switch_1) {
    FS_push_msg(F_BARREL_1_IS_FULL);
    FSM_FS.immediateTransitionTo(FS_idle);
  } else {
    // Switch 3-way filling_valve_1
    // Open filling_valve_3 and filling_valve 4
    // Start pump
    FS_push_msg("--> switch to barrel 1" + F_CR + "open valve 3" + F_CR +
                "open valve 4" + F_CR + "pump");
    relay_01.setStateToBeActuated(Relay::off);  // filling_valve_1
    relay_03.setStateToBeActuated(Relay::on);   // filling_valve_3
    relay_04.setStateToBeActuated(Relay::on);   // filling_valve_4
    relay_07.setStateToBeActuated(Relay::on);   // filling_pump
  }
}

void FS_tunnel_to_barrel_1__update() {
  if (!(state.prox_switch_4)) {
    FS_push_msg(F_TUNNEL_IS_EMPTY);
    FSM_FS.immediateTransitionTo(FS_idle);
  } else if (state.prox_switch_1) {
    FS_push_msg(F_BARREL_1_IS_FULL);
    FSM_FS.immediateTransitionTo(FS_idle);
  }
}

void FS_tunnel_to_barrel_1__exit() {
  relay_03.setStateToBeActuated(Relay::off);  // filling_valve_3
  relay_04.setStateToBeActuated(Relay::off);  // filling_valve_4
  relay_07.setStateToBeActuated(Relay::off);  // filling_pump
}

State FS_tunnel_to_barrel_1 = State(FS_tunnel_to_barrel_1__enter,
                                    FS_tunnel_to_barrel_1__update,
                                    FS_tunnel_to_barrel_1__exit);

// -----------------------------------------------------------------------------
//  FS: Tunnel to barrel 2
// -----------------------------------------------------------------------------

void FS_tunnel_to_barrel_2__enter() {
  FS_push_msg("FS: tunnel to barrel 2");

  // First check if the tunnel isn't already empty
  if (!(state.prox_switch_4)) {
    FS_push_msg(F_TUNNEL_IS_EMPTY);
    FSM_FS.immediateTransitionTo(FS_idle);
  } else if (state.prox_switch_2) {
    FS_push_msg(F_BARREL_2_IS_FULL);
    FSM_FS.immediateTransitionTo(FS_idle);
  } else {
    // Switch 3-way filling_valve_1
    // Open filling_valve_3 and filling_valve 4
    // Start pump
    FS_push_msg("--> switch to barrel 2" + F_CR +"open valve 3" + F_CR +
                "open valve 4" + F_CR + "pump");
    relay_01.setStateToBeActuated(Relay::on);   // filling_valve_1
    relay_03.setStateToBeActuated(Relay::on);   // filling_valve_3
    relay_04.setStateToBeActuated(Relay::on);   // filling_valve_4
    relay_07.setStateToBeActuated(Relay::on);   // filling_pump
  }
}

void FS_tunnel_to_barrel_2__update() {
  if (!(state.prox_switch_4)) {
    FS_push_msg(F_TUNNEL_IS_EMPTY);
    FSM_FS.immediateTransitionTo(FS_idle);
  } else if (state.prox_switch_2) {
    FS_push_msg(F_BARREL_2_IS_FULL);
    FSM_FS.immediateTransitionTo(FS_idle);
  }
}

void FS_tunnel_to_barrel_2__exit() {
  relay_03.setStateToBeActuated(Relay::off);  // filling_valve_3
  relay_04.setStateToBeActuated(Relay::off);  // filling_valve_4
  relay_07.setStateToBeActuated(Relay::off);  // filling_pump
}

State FS_tunnel_to_barrel_2 = State(FS_tunnel_to_barrel_2__enter,
                                    FS_tunnel_to_barrel_2__update,
                                    FS_tunnel_to_barrel_2__exit);

// -----------------------------------------------------------------------------
//   FS: Barrel 1 to sewer
// -----------------------------------------------------------------------------

void FS_barrel_1_to_sewer__enter() {
  FS_push_msg("FS: barrel 1 to sewer");

  // Switch 3-way filling_valve_1, open filling_valve_2 and wait to flood the
  // pipe at prox_switch_3
  FS_push_msg("--> switch to barrel 1" + F_CR + "open valve 2" + F_CR + F_WAIT);
  relay_01.setStateToBeActuated(Relay::off);  // filling_valve_1
  relay_02.setStateToBeActuated(Relay::on);   // filling_valve_2
}

void FS_barrel_1_to_sewer__update() {
  static uint8_t tracker = 0;

  if (FSM_FS.timeInCurrentState() < FS_TIMER1_DELAY) {
    // Filling_valve_2 is open and wait to flood the pipe at prox_switch_3
    tracker = 0;
  } else {
    if (!(state.prox_switch_3)) {
      FS_push_msg(F_BARREL_1_IS_EMPTY);
      FSM_FS.immediateTransitionTo(FS_idle);
    } else if (tracker == 0) {
      FS_push_msg("--> open valve 6" + F_CR + "pump");
      relay_06.setStateToBeActuated(Relay::on);   // filling_valve_6
      relay_07.setStateToBeActuated(Relay::on);   // filling_pump
      tracker = 1;
    }
  }
}

void FS_barrel_1_to_sewer__exit() {
  relay_02.setStateToBeActuated(Relay::off);  // filling_valve_2
  relay_06.setStateToBeActuated(Relay::off);  // filling_valve_6
  relay_07.setStateToBeActuated(Relay::off);  // filling_pump
}

State FS_barrel_1_to_sewer = State(FS_barrel_1_to_sewer__enter,
                                   FS_barrel_1_to_sewer__update,
                                   FS_barrel_1_to_sewer__exit);

// -----------------------------------------------------------------------------
//   FS: Barrel 2 to sewer
// -----------------------------------------------------------------------------

void FS_barrel_2_to_sewer__enter() {
  FS_push_msg("FS: barrel 2 to sewer");

  // Switch 3-way filling_valve_1, open filling_valve_2 and wait to flood the
  // pipe at prox_switch_3
  FS_push_msg("--> switch to barrel 2" + F_CR + "open valve 2" + F_CR + F_WAIT);
  relay_01.setStateToBeActuated(Relay::on);   // filling_valve_1
  relay_02.setStateToBeActuated(Relay::on);   // filling_valve_2
}

void FS_barrel_2_to_sewer__update() {
  static uint8_t tracker = 0;

  if (FSM_FS.timeInCurrentState() < FS_TIMER1_DELAY) {
    // Filling_valve_2 is open and wait to flood the pipe at prox_switch_3
    tracker = 0;
  } else {
    if (!(state.prox_switch_3)) {
      FS_push_msg(F_BARREL_2_IS_EMPTY);
      FSM_FS.immediateTransitionTo(FS_idle);
    } else if (tracker == 0) {
      FS_push_msg("--> open valve 6" + F_CR + "pump");
      relay_06.setStateToBeActuated(Relay::on);   // filling_valve_6
      relay_07.setStateToBeActuated(Relay::on);   // filling_pump
      tracker = 1;
    }
  }
}

void FS_barrel_2_to_sewer__exit() {
  relay_02.setStateToBeActuated(Relay::off);  // filling_valve_2
  relay_06.setStateToBeActuated(Relay::off);  // filling_valve_6
  relay_07.setStateToBeActuated(Relay::off);  // filling_pump
}

State FS_barrel_2_to_sewer = State(FS_barrel_2_to_sewer__enter,
                                   FS_barrel_2_to_sewer__update,
                                   FS_barrel_2_to_sewer__exit);

// -----------------------------------------------------------------------------
//  FS: Tunnel to sewer
// -----------------------------------------------------------------------------

void FS_tunnel_to_sewer__enter() {
  FS_push_msg("FS: tunnel to sewer");

  // First check if the tunnel isn't already empty
  if (!(state.prox_switch_4)) {
    FS_push_msg(F_TUNNEL_IS_EMPTY);
    FSM_FS.immediateTransitionTo(FS_idle);
  } else {
    // Open filling_valve_3 and filling_valve 6
    // Start pump
    FS_push_msg("--> open valve 3" + F_CR + "open valve 6" + F_CR + "pump");
    relay_03.setStateToBeActuated(Relay::on);   // filling_valve_3
    relay_06.setStateToBeActuated(Relay::on);   // filling_valve_6
    relay_07.setStateToBeActuated(Relay::on);   // filling_pump
  }
}

void FS_tunnel_to_sewer__update() {
  if (!(state.prox_switch_4)) {
    FS_push_msg(F_TUNNEL_IS_EMPTY);
    FSM_FS.immediateTransitionTo(FS_idle);
  }
}

void FS_tunnel_to_sewer__exit() {
  relay_03.setStateToBeActuated(Relay::off);  // filling_valve_3
  relay_06.setStateToBeActuated(Relay::off);  // filling_valve_6
  relay_07.setStateToBeActuated(Relay::off);  // filling_pump
}

State FS_tunnel_to_sewer = State(FS_tunnel_to_sewer__enter,
                                 FS_tunnel_to_sewer__update,
                                 FS_tunnel_to_sewer__exit);

// -----------------------------------------------------------------------------
// -----------------------------------------------------------------------------
//    setup
// -----------------------------------------------------------------------------
// -----------------------------------------------------------------------------

void setup() {
  // Initiate serial ports
  Serial.begin(115200);
  SerialUSB.begin(9600);

  Ser_debug.println("Arduino_#2 online");
  FS_msg_queue.setPrinter(Ser_debug);

  // Set up digital lines for the relays
  relay_01.begin();
  relay_02.begin();
  relay_03.begin();
  relay_04.begin();
  relay_05.begin();
  relay_06.begin();
  relay_07.begin();
  relay_08.begin();

  // Set up switches with debounce feature
  prox_switch_1.attach(PIN_PROX_SWITCH_1, INPUT_PULLUP);
  prox_switch_2.attach(PIN_PROX_SWITCH_2, INPUT_PULLUP);
  prox_switch_3.attach(PIN_PROX_SWITCH_3, INPUT_PULLUP);
  prox_switch_4.attach(PIN_PROX_SWITCH_4, INPUT_PULLUP);
  floater_switch.attach(PIN_FLOATER_SWITCH, INPUT_PULLUP);

  prox_switch_1.interval(500);    // debounce time [msec] full barrel 1?
  prox_switch_2.interval(500);    // debounce time [msec] full barrel 2?
  prox_switch_3.interval(100);    // debounce time [msec] empty barrel?
  prox_switch_4.interval(2000);   // debounce time [msec] empty tunnel?
  floater_switch.interval(100);   // debounce time [msec] full tunnel?

  // Set up digital inputs without debounce feature
  pinMode(PIN_EMPTY_PIPE, INPUT_PULLUP);

  // Enable watchdog timer
  Watchdog.enable(1000);   // [msec] 1000
}

// -----------------------------------------------------------------------------
// -----------------------------------------------------------------------------
//    loop
// -----------------------------------------------------------------------------
// -----------------------------------------------------------------------------

// Watchdog timer (WDT) reset rate. Do not reset the WDT every loop, because
// there is a 4 msec overhead each reset call. Instead, reset once per N msec.
uint32_t prevMillis_WDT_reset = 0;
uint16_t millisPeriod_WDT_reset = 800;  // [msec] 800

// DEBUG info
/*
uint32_t prevMillis = 0;
uint32_t curMicros  = 0;
uint32_t prevMicros_TC_AMP = 0;
uint16_t microsRate_TC_AMP = 0;
*/

void loop() {
  uint32_t curMillis = millis();
  char* strCmd;   // Incoming serial command string

  // This line is critical for the finite state machine
  FSM_FS.update();

  // Limit the number of messages in the queue to prevent memory overflow,
  // discard the oldest
  while (FS_msg_queue.count() > FS_MAX_MSG_QUEUE) {
    FS_msg_queue.pop();
    Ser_debug.println("Reached queue limit: discarded oldest");
  }

  // Store the number of messages in the queue
  state.FS_unread_msgs_count = FS_msg_queue.count();

  // ---------------------------------------------------------------------------
  //   Update switches
  // ---------------------------------------------------------------------------
  // Internal pull-up resistors are used hence invert the reading on the digital
  // input lines. The inversion wil be cancelled again if the switch is
  // used in a Nominally Open (NO) fashion.
  //
  // For all switches the following states are used, regardless of being
  // connected NO or NC:
  //   0: no water present
  //   1: water present

  prox_switch_1.update();
  prox_switch_2.update();
  prox_switch_3.update();
  prox_switch_4.update();
  floater_switch.update();
  state.prox_switch_1 = !prox_switch_1.read();      // NC
  state.prox_switch_2 = !prox_switch_2.read();      // NC
  state.prox_switch_3 = (prox_switch_3.read());     // NO
  state.prox_switch_4 = (prox_switch_4.read());     // NO
  state.floater_switch = !floater_switch.read();    // NO wired, mounted as NC
                                                    // i.e. mounted upside-down

  // ---------------------------------------------------------------------------
  //   Process incoming serial command when available
  // ---------------------------------------------------------------------------

  // Debug info
  if (sc_debug.available()) {
    strCmd = sc_debug.getCmd();

    if (strcmp(strCmd, "id?") == 0) {
      Ser_debug.println("Arduino_#2 debug channel: 04-09-2018");

    } else if (strcmp(strCmd, "reboot") == 0) {
      Ser_debug.println("Reboot triggered by watchdog timer in 1 sec");
      delay(1500);

    } else if (strcmp(strCmd, "?") == 0) {
      state.report(Ser_debug);
    }
  }

  // Python communication
  if (sc_python.available()) {
    strCmd = sc_python.getCmd();

    if (strcmpi(strCmd, "id?") == 0) {
      Ser_python.println("Arduino_#2");

    } else if (strcmp(strCmd, "soft_reset") == 0) {
      // Set filling system program to idle
      FSM_FS.immediateTransitionTo(FS_idle);

      // Switch all relays off
      relay_01.setStateToBeActuated(Relay::off);
      relay_02.setStateToBeActuated(Relay::off);
      relay_03.setStateToBeActuated(Relay::off);
      relay_04.setStateToBeActuated(Relay::off);
      relay_05.setStateToBeActuated(Relay::off);
      relay_06.setStateToBeActuated(Relay::off);
      relay_07.setStateToBeActuated(Relay::off);
      relay_08.setStateToBeActuated(Relay::off);

    } else if (strcmp(strCmd, "r1") == 0) {
      relay_01.setStateToBeActuated(Relay::toggle);
    } else if (strcmp(strCmd, "r1 on") == 0) {
      relay_01.setStateToBeActuated(Relay::on);
    } else if (strcmp(strCmd, "r1 off") == 0) {
      relay_01.setStateToBeActuated(Relay::off);

    } else if (strcmp(strCmd, "r2") == 0) {
      relay_02.setStateToBeActuated(Relay::toggle);
    } else if (strcmp(strCmd, "r2 on") == 0) {
      relay_02.setStateToBeActuated(Relay::on);
    } else if (strcmp(strCmd, "r2 off") == 0) {
      relay_02.setStateToBeActuated(Relay::off);

    } else if (strcmp(strCmd, "r3") == 0) {
      relay_03.setStateToBeActuated(Relay::toggle);
    } else if (strcmp(strCmd, "r3 on") == 0) {
      relay_03.setStateToBeActuated(Relay::on);
    } else if (strcmp(strCmd, "r3 off") == 0) {
      relay_03.setStateToBeActuated(Relay::off);

    } else if (strcmp(strCmd, "r4") == 0) {
      relay_04.setStateToBeActuated(Relay::toggle);
    } else if (strcmp(strCmd, "r4 on") == 0) {
      relay_04.setStateToBeActuated(Relay::on);
    } else if (strcmp(strCmd, "r4 off") == 0) {
      relay_04.setStateToBeActuated(Relay::off);

    } else if (strcmp(strCmd, "r5") == 0) {
      relay_05.setStateToBeActuated(Relay::toggle);
    } else if (strcmp(strCmd, "r5 on") == 0) {
      relay_05.setStateToBeActuated(Relay::on);
    } else if (strcmp(strCmd, "r5 off") == 0) {
      relay_05.setStateToBeActuated(Relay::off);

    } else if (strcmp(strCmd, "r6") == 0) {
      relay_06.setStateToBeActuated(Relay::toggle);
    } else if (strcmp(strCmd, "r6 on") == 0) {
      relay_06.setStateToBeActuated(Relay::on);
    } else if (strcmp(strCmd, "r6 off") == 0) {
      relay_06.setStateToBeActuated(Relay::off);

    } else if (strcmp(strCmd, "r7") == 0) {
      relay_07.setStateToBeActuated(Relay::toggle);
    } else if (strcmp(strCmd, "r7 on") == 0) {
      relay_07.setStateToBeActuated(Relay::on);
    } else if (strcmp(strCmd, "r7 off") == 0) {
      relay_07.setStateToBeActuated(Relay::off);

    } else if (strcmp(strCmd, "r8") == 0) {
      relay_08.setStateToBeActuated(Relay::toggle);
    } else if (strcmp(strCmd, "r8 on") == 0) {
      relay_08.setStateToBeActuated(Relay::on);
    } else if (strcmp(strCmd, "r8 off") == 0) {
      relay_08.setStateToBeActuated(Relay::off);

    } else if (strcmp(strCmd, "exec_FS_idle") == 0) {
                FSM_FS.immediateTransitionTo(FS_idle);  // Force immediate

    } else if (strcmp(strCmd, "exec_FS_barrel_1_to_tunnel") == 0) {
                FSM_FS.transitionTo(FS_barrel_1_to_tunnel);

    } else if (strcmp(strCmd, "exec_FS_barrel_2_to_tunnel") == 0) {
                FSM_FS.transitionTo(FS_barrel_2_to_tunnel);

    } else if (strcmp(strCmd, "exec_FS_tunnel_to_barrel_1") == 0) {
                FSM_FS.transitionTo(FS_tunnel_to_barrel_1);

    } else if (strcmp(strCmd, "exec_FS_tunnel_to_barrel_2") == 0) {
                FSM_FS.transitionTo(FS_tunnel_to_barrel_2);

    } else if (strcmp(strCmd, "exec_FS_barrel_1_to_sewer") == 0) {
                FSM_FS.transitionTo(FS_barrel_1_to_sewer);

    } else if (strcmp(strCmd, "exec_FS_barrel_2_to_sewer") == 0) {
                FSM_FS.transitionTo(FS_barrel_2_to_sewer);

    } else if (strcmp(strCmd, "exec_FS_tunnel_to_sewer") == 0) {
                FSM_FS.transitionTo(FS_tunnel_to_sewer);

    } else if (strcmp(strCmd, "FS_msg?") == 0) {
      // Pop a string message from the queue
      if (!FS_msg_queue.isEmpty())
        Ser_python.println(FS_msg_queue.pop());

    } else if (strcmp(strCmd, "FS_clear_msgs") == 0) {
      // Clear all string messages from the queue
      FS_msg_queue.clear();

    } else if (strcmp(strCmd, "?") == 0) {
      // Send the full state and readings of the Arduino over the serial port
      // tab delimited

      //uint32_t tick = millis();
      state.report(Ser_python);
      //Ser_debug << millis() - tick << endl;
    }
  }

  // ---------------------------------------------------------------------------
  //   Update relay states
  // ---------------------------------------------------------------------------

  state.relay_01 = relay_01.update();
  state.relay_02 = relay_02.update();
  state.relay_03 = relay_03.update();
  state.relay_04 = relay_04.update();
  state.relay_05 = relay_05.update();
  state.relay_06 = relay_06.update();
  state.relay_07 = relay_07.update();
  state.relay_08 = relay_08.update();

  // ---------------------------------------------------------------------------
  //   To report which filling system program is currently being executed
  // ---------------------------------------------------------------------------

  if               (FSM_FS.isInState(FS_idle)) {
    state.FSM_FS_exec = FSM_FS_PROGRAMS_idle;

  } else if        (FSM_FS.isInState(FS_barrel_1_to_tunnel)) {
    state.FSM_FS_exec = FSM_FS_PROGRAMS_barrel_1_to_tunnel;

  } else if        (FSM_FS.isInState(FS_barrel_2_to_tunnel)) {
    state.FSM_FS_exec = FSM_FS_PROGRAMS_barrel_2_to_tunnel;

  } else if        (FSM_FS.isInState(FS_tunnel_to_barrel_1)) {
    state.FSM_FS_exec = FSM_FS_PROGRAMS_tunnel_to_barrel_1;

  } else if        (FSM_FS.isInState(FS_tunnel_to_barrel_2)) {
    state.FSM_FS_exec = FSM_FS_PROGRAMS_tunnel_to_barrel_2;

  } else if        (FSM_FS.isInState(FS_barrel_1_to_sewer)) {
    state.FSM_FS_exec = FSM_FS_PROGRAMS_barrel_1_to_sewer;

  } else if        (FSM_FS.isInState(FS_barrel_2_to_sewer)) {
    state.FSM_FS_exec = FSM_FS_PROGRAMS_barrel_2_to_sewer;

  } else if        (FSM_FS.isInState(FS_tunnel_to_sewer)) {
    state.FSM_FS_exec = FSM_FS_PROGRAMS_tunnel_to_sewer;
  }

  // ---------------------------------------------------------------------------
  //   Reset the watchdog timer (WDT)
  // ---------------------------------------------------------------------------

  if (curMillis - prevMillis_WDT_reset > millisPeriod_WDT_reset) {
    Watchdog.reset(); // (Operation takes ~ 4250 usec when WDT enabled)
    prevMillis_WDT_reset = curMillis;
  }
}
