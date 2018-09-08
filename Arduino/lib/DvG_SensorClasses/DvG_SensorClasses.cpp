/*******************************************************************************
  DvG_SensorClasses

  Dennis van Gils
  19-03-2018
*******************************************************************************/

#include "DvG_SensorClasses.h"

/*******************************************************************************
  InputSwitch
*******************************************************************************/

InputSwitch::InputSwitch(uint8_t pin, bool fUseIntPullUp) {
  _pin           = pin;
  _fUseIntPullUp = fUseIntPullUp;
  _fState        = false;
  _fPrevState    = false;
  _fStateHasChanged = false;
}

// Set up the digital pin
void InputSwitch::begin() {
  if (_fUseIntPullUp) {
    pinMode(_pin, INPUT_PULLUP);
  } else {
    pinMode(_pin, INPUT);
  }

  // Read the initial state
  _fState = digitalRead(_pin);

  // Force a stateHasChanged at the first upcoming call to 'update'
  _fPrevState = !(_fState);
  _fStateHasChanged = true;
}

// Reads and returns the actual input state of the pin and stores it in
// '_fState'. It also compares this value to the previous input state
// '_fPrevState' since the previous call to 'update'.
bool InputSwitch::update() {
  _fState = digitalRead(_pin);
  _fStateHasChanged = (_fState != _fPrevState);
  _fPrevState = _fState;
  return _fState;
}

// Returns true if the input state has changed since the previous function
// call 'update'
bool InputSwitch::stateHasChanged() {
  return _fStateHasChanged;
}

bool InputSwitch::getState() {
  return _fState;
}

/*******************************************************************************
  Relay
*******************************************************************************/

Relay::Relay(uint8_t pin) {
  _pin        = pin;
  _fState     = false;
  _fPrevState = false;
}

// Set up the digital pin
void Relay::begin() {
  actuateState();
  pinMode(_pin, OUTPUT);
}

// Sets the relay state '_fState' but does not actuate it. A subsequent call to
// 'actuateState' or 'update' is necessary for changing the output on the
// digital pin.
void Relay::setStateToBeActuated(relay_action newState) {
  if (newState == Relay::toggle) {
    _fState = !(_fState);
  } else if (newState == Relay::on) {
    _fState = true;
  } else {
    _fState = false;
  }
}

// Is there is a change necessary in the pin output state?
bool Relay::needsUpdate() {
  return (_fState != _fPrevState);
}

// Sets the digital pin output to reflect the relay state '_fState'.
// Returns the actual actuated state.
bool Relay::actuateState() {
  digitalWrite(_pin, _fState);
  _fPrevState = _fState;
  return _fState;
}

// Checks whether there is a change necessary in the pin output state. If so,
// it sets the digital pin output to reflect the relay state '_fState'.
// Returns the actual actuated state.
bool Relay::update() {
  if (needsUpdate()) return actuateState(); else return _fState;
}

/*******************************************************************************
  TC_AMP: thermocouple amplifier class
  Reads out a thermocouple amplifier connected to an analog in pin. Provides
  bit value to degree Celcius conversion.
*******************************************************************************/

TC_AMP::TC_AMP(uint8_t pin, float factorBitVal2DegC) {
  _pin = pin;

  // Idealized linear conversion.
  _factorBitVal2DegC = factorBitVal2DegC;
}

/*
TC_AMP::TC_AMP(uint8_t pin, float factorBitVal2DegC,
  float fit_bitV_min, float fit_bitV_max,
  float fit_p1, float fit_p2, float fit_p3, float fit_p4, float fit_p5,
  float fit_p6, float fit_p7, float fit_mu1, float fit_mu2) {
  _pin = pin;

  // Idealized linear conversion.
  _factorBitVal2DegC = factorBitVal2DegC;

  // Sixth order polyfit results from calibration.
  _fit_bitV_min = fit_bitV_min;
  _fit_bitV_max = fit_bitV_max;
  _fit_p1 = fit_p1;
  _fit_p2 = fit_p2;
  _fit_p3 = fit_p3;
  _fit_p4 = fit_p4;
  _fit_p5 = fit_p5;
  _fit_p6 = fit_p6;
  _fit_p7 = fit_p7;
  _fit_mu1 = fit_mu1;
  _fit_mu2 = fit_mu2;
}
*/

void TC_AMP::begin() {
  pinMode(_pin, INPUT);
}

float TC_AMP::bitVal2DegC(float bitVal) {
  // NB: Keep input argument of type 'float' to accomodate for a running average
  // that could have been applied to the bit value.
  // Using idealized linear conversion.
  return (bitVal * _factorBitVal2DegC);
}

/*
float TC_AMP::bitVal2DegC_O6(float bitVal) {
  // NB: Keep input argument of type 'float' to accomodate for a running average
  // that could have been applied to the bit value.
  // Using sixth order polyfit results from calibration.

  // Check if the bit value is inside the calibrated range.
  // If not, return obvious values to indicate we are out of range.
  if (bitVal < _fit_bitV_min) {
    return 0;
  } else if (bitVal > _fit_bitV_max) {
    return 99;
  }

  float x = (bitVal - _fit_mu1) / _fit_mu2;
  return (_fit_p1 * pow(x, 6) +
          _fit_p2 * pow(x, 5) +
          _fit_p3 * pow(x, 4) +
          _fit_p4 * pow(x, 3) +
          _fit_p5 * pow(x, 2) +
          _fit_p6 * x +
          _fit_p7);
}
*/

uint32_t TC_AMP::read_bitVal() {
  // Ignore the first readings which can be faulty at high-impedance when
  // switching between analog in channels.
  // https://forum.arduino.cc/index.php?topic=69675.0
  // (1 analogRead operation takes ~ 430 usec on M0 Pro)
  for (uint8_t i = 0; i < 5; i++) {  // i < 5
    analogRead(_pin);
  }
  return analogRead(_pin);
}

/*******************************************************************************
  IIR_LP_DAQ
  Performs data acquisition (DAQ) at a fixed rate (non-blocking) and applies an
  one-pole infinite-input response (IIR) low-pass (LP) filter to the acquired
  data.
  IIR_LP_DAQ::pollUpdate() should be called continuously inside the main loop.
  This function will check the timer if another reading should be performed and
  added to the IIR filter.
*******************************************************************************/

IIR_LP_DAQ::IIR_LP_DAQ(uint32_t DAQ_interval_ms,
                       double f_LP_Hz,
                       uint32_t (*readFunction)()) {
  _DAQ_interval_ms = DAQ_interval_ms;   // [millisec]
  _f_LP_Hz         = f_LP_Hz;
  _readFunction    = readFunction;
  _IIR_LP_value    = 0.0;
  _prevMicros      = 0;
  _fStartup        = true;
  _alpha           = 1.0;
}

// Checks if enough time has passed to acquire a new reading. If yes, acquire
// a new reading and append it to the IIR filter. Returns true when a reading
// was actually performed.
bool IIR_LP_DAQ::pollUpdate() {
  uint32_t curMicros = micros();

  if ((curMicros - _prevMicros) > _DAQ_interval_ms * 1e3) {
    // Enough time has passed: acquire new reading
    // Calculate the smoothing factor every time because an exact DAQ interval
    // time is not garantueed
    _alpha = 1.0 - exp(-double(curMicros - _prevMicros)*1e-6*_f_LP_Hz);          // (Operation takes ~ 180 usec on M0 Pro)

    if (_fStartup) {
      _IIR_LP_value = _readFunction();
      _fStartup = false;
    } else {
      _IIR_LP_value += _alpha * (_readFunction() - _IIR_LP_value);               // (Operation not including _readFunction takes ~ 20 usec on M0 Pro)
      //_IIR_LP_value = _readFunction();  // DEBUG SPEED TEST
      //_IIR_LP_value = 0;                // DEBUG SPEED TEST
    }
    _prevMicros = curMicros;
    return true;
  } else {
    return false;
  }
}

// Returns the current low-pass filtered value
double IIR_LP_DAQ::getValue() {
  return _IIR_LP_value;
}

// Returns the last derived smoothing factor
double IIR_LP_DAQ::getAlpha() {
  return _alpha;
}
