/*******************************************************************************
  DvG_SensorClasses

  Dennis van Gils
  19-03-2018
*******************************************************************************/

#ifndef DvG_SensorClasses_h
#define DvG_SensorClasses_h

#include <Arduino.h>

/*******************************************************************************
  InputSwitch
********************************************************************************
Usage:
  // Instantiate floater switch
  InputSwitch switch_01(1,      // Pin
                        true);  // Use internal pull-up resistor

  // This struct reflects the actual state and readings of the Arduino
  struct State state;

  void setup() {
    // Set up switch
    switch_01.begin();
  }

  void loop() {
    // Read switch state and store in state class
    state.switch_01 = switch_01.update();

    if (switch_01.stateHasChanged()) {
      // Do stuff. You can retreive the last stored state by using either:
      printf(state.switch_01);
      // or
      printf(switch_01.getState());
    }
  }
*/

class InputSwitch {
public:
  InputSwitch(uint8_t pin, bool fUseIntPullUp);

  // Set up the digital pin
  void begin();

  // Reads and returns the actual input state of the pin and stores it in
  // '_fState'. It also compares this value to the previous input state
  // '_fPrevState' since the previous call to 'update'.
  bool update();

  // Returns true if the input state has changed since the previous function
  // call 'update'
  bool stateHasChanged();

  bool getState();

private:
  uint8_t _pin;
  bool    _fUseIntPullUp;
  bool    _fState;
  bool    _fPrevState;
  bool    _fStateHasChanged;
};

/*******************************************************************************
  Relay
*******************************************************************************/

class Relay {
public:
  Relay(uint8_t pin);

  enum relay_action {
    toggle,
    on,
    off
  };

  // Set up the digital pin
  void begin();

  // Sets the relay state '_fState' but does not actuate it. A subsequent call to
  // 'actuateState' or 'update' is necessary for changing the output on the
  // digital pin.
  void setStateToBeActuated(relay_action newState);

  // Is there is a change necessary in the pin output state?
  bool needsUpdate();

  // Sets the digital pin output to reflect the relay state '_fState'.
  // Returns the actual actuated state.
  bool actuateState();

  // Checks whether there is a change necessary in the pin output state. If so,
  // it sets the digital pin output to reflect the relay state '_fState'.
  // Returns the actual actuated state.
  bool update();

private:
  uint8_t _pin;
  bool    _fState;
  bool    _fPrevState;
};

/*******************************************************************************
  TC_AMP: thermocouple amplifier class
  Reads out a thermocouple amplifier connected to an analog in pin. Provides
  bit value to degree Celcius conversion.
*******************************************************************************/

class TC_AMP {
public:
  // Constructor
  //  pin: analog in pin
  //  factorBitVal2DegC: linear conversion factor
  TC_AMP(uint8_t pin, float factorBitVal2DegC);

  /*
  TC_AMP(uint8_t pin, float factorBitVal2DegC,
    float fit_bitV_min, float fit_bitV_max,
    float fit_p1, float fit_p2, float fit_p3, float fit_p4, float fit_p5,
    float fit_p6, float fit_p7, float fit_mu1, float fit_mu2);
  */

  // Sets the analog pin to INPUT
  void begin();

  // NB: Keep input argument of type 'float' to accomodate for a running average
  // that could have been applied to the bit value.
  // Using idealized linear conversion.
  float bitVal2DegC(float bitVal);

  /*
  // NB: Keep input argument of type 'float' to accomodate for a running average
  // that could have been applied to the bit value.
  // Using sixth order polyfit results from calibration.
  float bitVal2DegC_O6(float bitVal);
  */

  // Reads and returns the analog in bit value
  uint32_t read_bitVal();

private:
  uint8_t _pin;             // Analog in pin
  float _factorBitVal2DegC; // Linear conversion factor from bit value to deg C.

  /*
  // Sixth order polyfit results obtained from calibration.
  float _fit_bitV_min, _fit_bitV_max;
  float _fit_p1, _fit_p2, _fit_p3, _fit_p4, _fit_p5, _fit_p6, _fit_p7;
  float _fit_mu1, _fit_mu2;
  */
};

/*******************************************************************************
  IIR_LP_DAQ
  Performs data acquisition (DAQ) at a fixed rate (non-blocking) and applies an
  one-pole infinite-input response (IIR) low-pass (LP) filter to the acquired
  data.
  IIR_LP_DAQ::pollUpdate() should be called continuously inside the main loop.
  This function will check the timer if another reading should be performed and
  added to the IIR filter.
*******************************************************************************/

class IIR_LP_DAQ {
public:
  // Constructor
  //  DAQ_interval_ms: data acquisition time interval [microsec]
  //  f_LP_Hz        : low-pass cut-off frequency [Hz]
  //  readFunction   : pointer to 'read' function, e.g. analogRead()
  IIR_LP_DAQ(uint32_t DAQ_interval_ms, double f_LP_Hz, uint32_t (*readFunction)());

  // Checks if enough time has passed to acquire a new reading. If yes, acquire
  // a new reading and append it to the IIR filter. Returns true when a reading
  // was actually performed.
  bool pollUpdate();

  // Returns the current low-pass filtered value
  double getValue();

  // Returns the last derived smoothing factor
  double getAlpha();

private:
  uint32_t _DAQ_interval_ms;
  double   _f_LP_Hz;
  uint32_t (*_readFunction)();    // Pointer to read function
  double   _IIR_LP_value;
  uint32_t _prevMicros;           // Time of last reading
  bool     _fStartup;
  double   _alpha;                // Derived smoothing factor
};

#endif
