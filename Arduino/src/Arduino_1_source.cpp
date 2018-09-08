/*******************************************************************************
  Twente MHT Tunnel - ARDUINO #1

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
    - Sainsmart 8ch. Relay Module board
    - 20 mA MIKROE T click: current transmitter           [SPI bus]
    - 20 mA MIKROE R click: current receiver              [SPI bus]
    - 20 mA MIKROE R click: current receiver              [SPI bus]
    - MCP23017: IO expander, 16 DIO channels              [I2C bus]

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
  07-09-2018
*******************************************************************************/

#include <Arduino.h>
#include "Adafruit_SleepyDog.h"   // Watchdog timer
#include "Adafruit_MCP23017.h"

#include "DvG_SerialCommand.h"
#include "DvG_SensorClasses.h"
#include "DvG_ArduinoState.h"
#include "DvG_RT_Click_mA.h"

#include "PID_v1.h"

// Serial port definitions
// Serial   : Programming USB port.
// SerialUSB: Native USB port. Baudrate ignored and is as fast as possible.
#define Ser_python SerialUSB
#define Ser_debug  Serial

// Initiate serial command listener
DvG_SerialCommand sc_python(Ser_python);
DvG_SerialCommand sc_debug(Ser_debug);

// -----------------------------------------------------------------------------
//   Pin definitions Arduino
// -----------------------------------------------------------------------------

#define PIN_RELAY_01  0
#define PIN_RELAY_02  1
#define PIN_RELAY_03  2
#define PIN_RELAY_04  3
#define PIN_RELAY_05  4
#define PIN_RELAY_06  6
#define PIN_RELAY_07  7
#define PIN_RELAY_08  8
#define PIN_RELAY_09  12

#define PIN_SS_SET_PUMP_SPEED  9  // Slave Select pin for 20mA MIKROE T click
#define PIN_SS_READ_GVF_P_DIFF 10 // Slave Select pin for 20mA MIKROE R click #1
#define PIN_SS_READ_FLOW_READ  11 // Slave Select pin for 20mA MIKROE R click #2

// -----------------------------------------------------------------------------
//   MCP23017 IO expander, 16 DIO channels
// -----------------------------------------------------------------------------

Adafruit_MCP23017 mcp;

// -----------------------------------------------------------------------------
//   MIKROE R/T click, 20 mA current control
// -----------------------------------------------------------------------------

// Calibration date 25-08-2017
// 4-20 mA T click, nr 1
T_Click T_click_1(PIN_SS_SET_PUMP_SPEED, 4.00, 790, 20.5, 4095);

// 4-20 mA R click, nr 1
R_Click R_click_1(PIN_SS_READ_GVF_P_DIFF, 4.00, 763, 20.11, 3967);   // 04-07-2018

// 4-20 mA R click, nr 2
//R_Click R_click_2(PIN_SS_READ_FLOW_READ, 4.00, 755, 20.00, 3928);  // 14-11-2017
R_Click R_click_2(PIN_SS_READ_FLOW_READ, 4.00, 758, 20.00, 3928);    // 19-02-2018

uint32_t read_R_click_1() {return R_click_1.read_bitVal();}
uint32_t read_R_click_2() {return R_click_2.read_bitVal();}

// These instances manage the data acquisition on the [4-20 mA] R_Click
// readings whenever IIR_LP_DAQ::pollUpdate is called.
#define R_CLICK_1_DAQ_INTERVAL_MS  2   // Polling interval for readings [msec] 2
#define R_CLICK_1_DAQ_LP_FILTER_Hz 1   // Low-pass filter cut-off frequency [Hz] 1
#define R_CLICK_2_DAQ_INTERVAL_MS  25  // Polling interval for readings [msec] 25
#define R_CLICK_2_DAQ_LP_FILTER_Hz 0.2 // Low-pass filter cut-off frequency [Hz] 0.2

IIR_LP_DAQ R_click_1_DAQ(R_CLICK_1_DAQ_INTERVAL_MS,
                         R_CLICK_1_DAQ_LP_FILTER_Hz,
                         read_R_click_1);
IIR_LP_DAQ R_click_2_DAQ(R_CLICK_2_DAQ_INTERVAL_MS,
                         R_CLICK_2_DAQ_LP_FILTER_Hz,
                         read_R_click_2);

// -----------------------------------------------------------------------------
//   Relays
// -----------------------------------------------------------------------------

Relay relay_01(PIN_RELAY_01); // ENA_PSU_1
Relay relay_02(PIN_RELAY_02); // ENA_PSU_2
Relay relay_03(PIN_RELAY_03); // ENA_PSU_3
Relay relay_04(PIN_RELAY_04); // bubble_valve_1
Relay relay_05(PIN_RELAY_05); // bubble_valve_2
Relay relay_06(PIN_RELAY_06); // bubble_valve_3
Relay relay_07(PIN_RELAY_07); // bubble_valve_4
Relay relay_08(PIN_RELAY_08); // bubble_valve_5
Relay relay_09(PIN_RELAY_09); // ENA_tunnel_pump

// -----------------------------------------------------------------------------
//   This class instance reflects the actual state and readings of the Arduino
// -----------------------------------------------------------------------------

State_Arduino_1 state;

// -----------------------------------------------------------------------------
//   PID control: Tunnel flow rate
//   Takes readings from the mass flow meter and drives the pump power to
//   tune the mass flow rate.
// -----------------------------------------------------------------------------

// The maximum flow rate that corresponds to 20 mA output of the mass flow meter
// NOTE: this can be explicitly set in the flow meter parameter menu
#define QMAX_FLOW_METER 30        // m3/h

// Two sets of PID parameters are used.
// Set 1 is tuned for fast settling times when a new setpoint has been set.
// Set 2 is tuned for stable operation at statistically stationary conditions
// and is extremely slow to adopt to large setpoint changes.
// Switching between the sets happens automatically depending on the distance
// between the setpoint and the current measured flow rate.
int PID_pump_sample_time = 1000;   // 1000 [ms]

// Set 1: fast settling
float PID_pump_set_1_Kp = 0.75;    // 0.75
float PID_pump_set_1_Ki = 0.2;     // 0.2
float PID_pump_set_1_Kd = 0.0;     // 0.0

// Set 2: stable stat. stat. operation
float PID_pump_set_2_Kp = 0.3;     // 0.3
float PID_pump_set_2_Ki = 0.05;    // 0.05
float PID_pump_set_2_Kd = 0.0;     // 0.0

// Current set
uint8_t PID_pump_old_set = 0; // Old
uint8_t PID_pump_req_set = 1; // Request
uint8_t PID_pump_cur_set = 1; // Current
float PID_pump_Kp = PID_pump_set_1_Kp;
float PID_pump_Ki = PID_pump_set_1_Ki;
float PID_pump_Kd = PID_pump_set_1_Kd;

// Auto switch params
// Switch between sets when the deviation between the desired setpoint and the
// measured flow rate is more than this percentage.
// To prevent rapid switching between PID sets we apply:
//  - A deadband on the switch percentage
// To negate the effect of overshoot when using set 1 and preventing set 2 from
// already kicking in prematurely, we postpone the switching from set 1 to set 2
// by applying a wait timer.
float PID_pump_switch_pct      = 3.0;    // 3.0 [%]
float PID_pump_switch_deadband = 2.0;    // 2.0 [%]
uint8_t PID_pump_switch_wait_period = 20;     // 20  [s]
uint32_t PID_pump_millis_when_set1_was_requested_last = 0;  // Holds the millis() time

// Specify the links
PID PID_pump(&(state.read_flow_rate_m3h),
             &(state.set_pump_speed_pct),
             &(state.setpoint_flow_rate_m3h),
             PID_pump_Kp, PID_pump_Ki, PID_pump_Kd, P_ON_E, DIRECT);

// -----------------------------------------------------------------------------
//   Over temperature protection (OTP) of the heaters
// -----------------------------------------------------------------------------
/*
  Relays 1 to 3 control the hardware ENABLE switch of the Keysight
  power supplies, called ENA_PSU_# in the Python main program. When disabled
  the output of the power supply is 'Inhibited'.

  The power supplies should only be enabled, whenever the temperature of the
  heaters is being read out in order to prevent heater overheating and
  burn-out. The embedded thermocouples are read out by an Agilent multiplexer
  3497xA at a rate of ~ 1 second, running from within the Python main
  program. Python should periodically send out an "otp_okay" signal to this
  Arduino indicating that the temperatures are within valid range (e.g. between
  10 'C and 85 'C) every time the multiplexer is read out. The multiplexer reads
  at a rate of around 1 sec. If this Arduino doesn't receive an 'otp_okay'
  signal within the time-out specified below, the OTP will be tripped and all
  PSU output will be inhibited automatically. This time-out can be overriden
  when going into 'MANUAL' mode by setting state.ENA_OTP = false, which allows
  the user to control the relays 1 to 3 directly from the Python main program,
  without intervention by this Arduino.

  state.ENA_OTP = true:  protection enabled / automatic mode (default)
  state.ENA_OTP = false: protection disabled / manual mode
*/
#define  OTP_OKAY_TIMEOUT_MS 3000         // 2000 [ms], remark: 2000 ms seems to result in premature OTP trip sporadically. Mux needs more time occasionally? Investigate.
uint32_t OTP_okay_prevMillis = 0;
bool     OTP_tripped_status = false;      // Immediately inhibit PSU output when true
bool     OTP_tripped_status_old = false;

// -----------------------------------------------------------------------------
//    setup
// -----------------------------------------------------------------------------

void setup() {
  // Initiate serial ports
  Serial.begin(9600);
  SerialUSB.begin(9600);

  Ser_debug.println("Arduino_#1 online");

  // Set up mA current controllers
  T_click_1.begin();
  R_click_1.begin();
  R_click_2.begin();

  // Set up MCP23017 IO expander
  mcp.begin();

  // Set up digital lines for the relays
  relay_01.begin();
  relay_02.begin();
  relay_03.begin();
  relay_04.begin();
  relay_05.begin();
  relay_06.begin();
  relay_07.begin();
  relay_08.begin();
  relay_09.begin();

  // Determines how often the PID algorithm evaluates
  PID_pump.SetSampleTime(PID_pump_sample_time);

  // Limits on state.set_pump_speed_pct [%]
  PID_pump.SetOutputLimits(0.0, 81.0);

  // Enable watchdog timer
  Watchdog.enable(1000);   // [msec] 1000
}

// -----------------------------------------------------------------------------
//    loop
// -----------------------------------------------------------------------------

// Watchdog timer (WDT) reset rate. Do not reset the WDT every loop, because
// there is a 4 msec overhead each reset call. Instead, reset once per N msec.
uint32_t prevMillis_WDT_reset = 0;
uint16_t millisPeriod_WDT_reset = 800;  // [msec] 800

// DEBUG info
/*
uint32_t prevMillis = 0;
uint32_t curMicros  = 0;
uint32_t prevMicros_R_click = 0;
uint16_t microsRate_R_click = 0;
*/

void loop() {
  uint32_t curMillis = millis();
  char* strCmd;   // Incoming serial command string

  // Display DEBUG info
  /*
  if (curMillis - prevMillis > 1000) {
    Ser_debug.print("T ");
    Ser_debug.println(microsRate_TC_AMP);
    Ser_debug.print("R ");
    Ser_debug.println(microsRate_R_click);
    prevMillis = curMillis;
  }
  */

  // ---------------------------------------------------------------------------
  //   Update R_click readings
  // ---------------------------------------------------------------------------

  if (R_click_1_DAQ.pollUpdate()) {
    state.read_GVF_P_diff_bitV = R_click_1_DAQ.getValue();
    state.read_GVF_P_diff_mA   = R_click_1.bitVal2mA(state.read_GVF_P_diff_bitV);

    // Taken from Omega calibration sheet supplied with pressure transducer
    // Serial: 487141
    // Calibration job : WHS0021169
    // Calibration date: 12-03-2018
    state.read_GVF_P_diff_mbar = (state.read_GVF_P_diff_mA - 4.01) / 16.072 *
                                 170;
  }

  if (R_click_2_DAQ.pollUpdate()) {
    state.read_flow_rate_bitV = R_click_2_DAQ.getValue();
    state.read_flow_rate_mA   = R_click_2.bitVal2mA(state.read_flow_rate_bitV);
    state.read_flow_rate_m3h  = constrain((state.read_flow_rate_mA - 4) / 16.0,
                                          0, 1.0) * QMAX_FLOW_METER;

    // DEBUG info
    //curMicros = micros();
    //microsRate_R_click = curMicros - prevMicros_R_click;
    //prevMicros_R_click = curMicros;
  }

  // ---------------------------------------------------------------------------
  //   Process incoming serial command when available
  // ---------------------------------------------------------------------------

  // Debug info
  if (sc_debug.available()) {
    strCmd = sc_debug.getCmd();

    if (strcmpi(strCmd, "id?") == 0) {
      Ser_debug.println("Arduino_#1 debug channel: 04-09-2018");

    } else if (strcmp(strCmd, "reboot") == 0) {
      Ser_debug.println("Reboot triggered by watchdog timer in 1 sec");
      delay(1500);

    } else if (strcmp(strCmd, "?") == 0) {
      state.report(Ser_debug);

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

    } else if (strcmp(strCmd, "bub on") == 0) {
      relay_04.setStateToBeActuated(Relay::on);
      relay_05.setStateToBeActuated(Relay::on);
      relay_06.setStateToBeActuated(Relay::on);
      relay_07.setStateToBeActuated(Relay::on);
      relay_08.setStateToBeActuated(Relay::on);
    } else if (strcmp(strCmd, "bub off") == 0) {
      relay_04.setStateToBeActuated(Relay::off);
      relay_05.setStateToBeActuated(Relay::off);
      relay_06.setStateToBeActuated(Relay::off);
      relay_07.setStateToBeActuated(Relay::off);
      relay_08.setStateToBeActuated(Relay::off);

    } else if (strcmp(strCmd, "ena_otp on") == 0) {
      state.ENA_OTP = true;
      // The old state needs to be set to false, in order to have the OTP kick
      // in again asap when the MUX is /not/ scanning at the moment of
      // re-enabling ENA_OTP.
      OTP_tripped_status_old = false;
      Ser_debug.println("ENA_OTP is ON");
    } else if (strcmp(strCmd, "ena_otp off") == 0) {
      state.ENA_OTP = false;
      Ser_debug.println("ENA_OTP is OFF");
    }
  }

  // Python communication
  if (sc_python.available()) {
    strCmd = sc_python.getCmd();

    if (strcmpi(strCmd, "id?") == 0) {
      Ser_python.println("Arduino_#1");

    } else if (strcmp(strCmd, "soft_reset") == 0) {
      // Switch all relays off
      relay_01.setStateToBeActuated(Relay::off);
      relay_02.setStateToBeActuated(Relay::off);
      relay_03.setStateToBeActuated(Relay::off);
      relay_04.setStateToBeActuated(Relay::off);
      relay_05.setStateToBeActuated(Relay::off);
      relay_06.setStateToBeActuated(Relay::off);
      relay_07.setStateToBeActuated(Relay::off);
      relay_08.setStateToBeActuated(Relay::off);
      relay_09.setStateToBeActuated(Relay::off);

      // Set the pump speed to 0 rpm
      state.set_pump_speed_mA = 4.0;
      state.set_pump_speed_pct = 0.0;
      T_click_1.set_mA(state.set_pump_speed_mA);

      // Disable PID control on the tunnel flow rate
      state.ENA_PID_pump = false;
      state.setpoint_flow_rate_m3h = 0.0;

      // Reset the over-temperature protection (OTP)
      state.ENA_OTP = true;
      OTP_tripped_status = false;
      OTP_tripped_status_old = false;

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

    } else if (strcmp(strCmd, "r9") == 0) {
      relay_09.setStateToBeActuated(Relay::toggle);
    } else if (strcmp(strCmd, "r9 on") == 0) {
      relay_09.setStateToBeActuated(Relay::on);
    } else if (strcmp(strCmd, "r9 off") == 0) {
      relay_09.setStateToBeActuated(Relay::off);

    } else if (strncmp(strCmd, "sps", 3) == 0) {
      state.set_pump_speed_mA = constrain(parseFloatInString(strCmd, 3),
                                          4.0, 20.0);
      state.set_pump_speed_pct = (state.set_pump_speed_mA - 4.0) / 0.16;
      T_click_1.set_mA(state.set_pump_speed_mA);

    } else if (strcmp(strCmd, "ena_pfr on") == 0) {
      state.ENA_PID_pump = true;
    } else if (strcmp(strCmd, "ena_pfr off") == 0) {
      state.ENA_PID_pump = false;

    } else if (strcmp(strCmd, "ena_otp on") == 0) {
      state.ENA_OTP = true;
      // The old state needs to be set to false, in order to have the OTP kick
      // in again asap when the MUX is /not/ scanning at the moment of
      // re-enabling ENA_OTP.
      OTP_tripped_status_old = false;
    } else if (strcmp(strCmd, "ena_otp off") == 0) {
      state.ENA_OTP = false;

    } else if (strcmp(strCmd, "otp_okay") == 0) {
      // All heater temperatures are reported safe and okay.
      // Reset OTP time-out timer.
      OTP_tripped_status = false;
      OTP_okay_prevMillis = curMillis;
    } else if (strcmp(strCmd, "otp_trip") == 0) {
      // Heater temperatures are reported to be out of safe range
      // OR the multiplexer just stopped scanning.
      // Immediately trip the OTP and inhibit all PSU output.
      OTP_tripped_status = true;

    } else if (strncmp(strCmd, "sfr", 3) == 0) {
      state.setpoint_flow_rate_m3h = constrain(parseFloatInString(strCmd, 3),
                                               0.0, QMAX_FLOW_METER);

    } else if (strcmp(strCmd, "?") == 0) {
      // Send the full state and readings of the Arduino over the serial port
      // tab delimited

      // DEBUG INFO: print state-report frequency [Hz]
      //Ser_debug.println(round(1000./(curMillis - prevMillis)));
      //prevMillis = curMillis;

      state.report(Ser_python);
    }
  }

  // ---------------------------------------------------------------------------
  //   PID update
  // ---------------------------------------------------------------------------

  // Determine the PID mode: on (AUTOMATIC == 1) or off (MANUAL == 0).
  // Disable automatic PID mode when pump not enabled (relay_09).
  bool switch_to_PID_mode = (state.ENA_PID_pump && state.relay_09);

  if (switch_to_PID_mode != PID_pump.GetMode()){
    // The PID mode changed
    PID_pump.SetMode(switch_to_PID_mode);
  }

  // Determine which PID set we should request depending on deviation.
  float dev_setp_pct = abs(state.read_flow_rate_m3h -
                           state.setpoint_flow_rate_m3h) /
                       state.setpoint_flow_rate_m3h * 100;
  if (dev_setp_pct > (PID_pump_switch_pct + PID_pump_switch_deadband/2)) {
    PID_pump_req_set = 1;
    PID_pump_millis_when_set1_was_requested_last = curMillis;
  } else if (dev_setp_pct < (PID_pump_switch_pct - PID_pump_switch_deadband/2)) {
    PID_pump_req_set = 2;
  }

  // Test if we should grant the requested PID set.
  if (state.ENA_PID_pump && (PID_pump_cur_set != PID_pump_req_set)) {
    switch (PID_pump_req_set) {
      case 1: {
        // A request for set 1 gets granted immediatly
        PID_pump_cur_set = PID_pump_req_set;
        break;
      }
      case 2: {
        // Only switch to set 2 when the wait timer has expired.
        if ((curMillis - PID_pump_millis_when_set1_was_requested_last) >
            PID_pump_switch_wait_period * 1e3) {
          // Wait timer has expired. Grant.
          PID_pump_cur_set = PID_pump_req_set;
        } else {
          // Do not grant yet.
          //Ser_DB.println("Waiting to switch to PID set 2");
        }
        break;
      }
    }
  }

  // Make the switch definite
  if (PID_pump_cur_set != PID_pump_old_set) {
    switch (PID_pump_cur_set) {
      case 1: {
        Ser_debug.println("PID set 1");
        PID_pump_Kp = PID_pump_set_1_Kp;
        PID_pump_Ki = PID_pump_set_1_Ki;
        PID_pump_Kd = PID_pump_set_1_Kd;
        break;
      }
      case 2:{
        Ser_debug.println("PID set 2");
        PID_pump_Kp = PID_pump_set_2_Kp;
        PID_pump_Ki = PID_pump_set_2_Ki;
        PID_pump_Kd = PID_pump_set_2_Kd;
        break;
      }
    }
    PID_pump.SetTunings(PID_pump_Kp, PID_pump_Ki, PID_pump_Kd, P_ON_E);
    PID_pump_old_set = PID_pump_cur_set;
  }

  // Compute the new PID output
  if (PID_pump.Compute()) {
    // Send out the pump speed if the PID control is in automatic mode.
    state.set_pump_speed_mA = state.set_pump_speed_pct * 0.16 + 4.0;
    T_click_1.set_mA(state.set_pump_speed_mA);
  }

  // ---------------------------------------------------------------------------
  //   Over temperature protection (OTP) of the heaters
  // ---------------------------------------------------------------------------

  if (state.ENA_OTP) {
    if (curMillis - OTP_okay_prevMillis > OTP_OKAY_TIMEOUT_MS) {
      OTP_tripped_status = true;
    }

    if (OTP_tripped_status != OTP_tripped_status_old) {
      if (OTP_tripped_status) {
        relay_01.setStateToBeActuated(Relay::off);
        relay_02.setStateToBeActuated(Relay::off);
        relay_03.setStateToBeActuated(Relay::off);
        Ser_debug.println("OTP tripped");
      } else {
        relay_01.setStateToBeActuated(Relay::on);
        relay_02.setStateToBeActuated(Relay::on);
        relay_03.setStateToBeActuated(Relay::on);
        Ser_debug.println("OTP okay");
      }
      OTP_tripped_status_old = OTP_tripped_status;
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
  state.relay_09 = relay_09.update();

  // ---------------------------------------------------------------------------
  //   Reset the watchdog timer (WDT)
  // ---------------------------------------------------------------------------

  if (curMillis - prevMillis_WDT_reset > millisPeriod_WDT_reset) {
    Watchdog.reset(); // (Operation takes ~ 4250 usec when WDT enabled)
    prevMillis_WDT_reset = curMillis;
  }
}
