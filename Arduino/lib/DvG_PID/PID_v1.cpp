/*******************************************************************************
 * Arduino PID Library - Version 1.2.1
 * by Brett Beauregard <br3ttb@gmail.com> brettbeauregard.com
 *
 * This Library is licensed under the MIT License
 ******************************************************************************/

 /*
 Edited by Dennis van Gils, 02-03-2018
   * Code refactoring.
   * P_ON_M mode has been removed.
   * Made the proportional, integrative and derivative terms accessible.
 */

#include "Arduino.h"
#include <PID_v1.h>

/* Constructor(...) ************************************************************
The parameters specified here are those for for which we can't set up
reliable defaults, so we need to have the user set them.
*******************************************************************************/

PID::PID(float* Input, float* Output, float* Setpoint,
         float Kp, float Ki, float Kd, int POn, int ControllerDirection) {
  myOutput   = Output;
  myInput    = Input;
  mySetpoint = Setpoint;
  inAuto     = false;

  pTerm = 0;
  iTerm = 0;
  dTerm = 0;

  PID::SetOutputLimits(0, 100);		// Default output limit
  SampleTime = 1000;					    // Default Controller Sample Time

  PID::SetControllerDirection(ControllerDirection);
  PID::SetTunings(Kp, Ki, Kd, POn);

  lastTime = millis();
}

/* Compute() *******************************************************************
This, as they say, is where the magic happens.  this function should be called
every time "void loop()" executes.  the function will decide for itself whether
a new pid Output needs to be computed.  returns true when the output is
computed, false when nothing has been done.
*******************************************************************************/

bool PID::Compute() {
  unsigned long now;
  float input, output, error;

  if (!inAuto) return false;

  now = millis();
  if ((now - lastTime) >= SampleTime) {
    input = *myInput;
    error = *mySetpoint - input;

    // Proportional term
    pTerm = kp * error;

    // Integral term
    iTerm = iTerm + (ki * error);

    /*
    // DEBUG info
    if (iTerm < outMin) {
      Serial.println("iTerm < outMin: integral windup");
    } else if (iTerm > outMax) {
      Serial.println("iTerm > outMax: integral windup");
    }
    */

    // Prevent integral windup
    iTerm = constrain(iTerm, outMin, outMax);

    // Derivative term
    // Prevent derivative kick: really good to do!
    dTerm = -kd * (input - lastInput);

    // Compute PID Output
    output = pTerm + iTerm + dTerm;

    /*
    // DEBUG info
    if (output < outMin) {
      Serial.println("output < outMin: output clamped");
    } else if (output > outMax) {
      Serial.println("output > outMax: output clamped");
    }
    */

    // Clamp the output to its limits
    output = constrain(output, outMin, outMax);

    *myOutput = output;

    // Remember some variables for next time
    lastInput = input;
    lastTime = now;

    return true;
  } else {
    return false;
  }
}

/* SetTunings(...) *************************************************************
This function allows the controller's dynamic performance to be adjusted.
It's called automatically from the constructor, but tunings can also
be adjusted on the fly during normal operation
*******************************************************************************/

void PID::SetTunings(float Kp, float Ki, float Kd, int POn) {
  if (Kp < 0 || Ki < 0 || Kd < 0) return;

  pOn = POn;
  pOnE = POn == P_ON_E;

  dispKp = Kp;
  dispKi = Ki;
  dispKd = Kd;

  float SampleTimeInSec = ((float) SampleTime) / 1000;
  kp = Kp;
  ki = Ki * SampleTimeInSec;
  kd = Kd / SampleTimeInSec;

  if (controllerDirection == REVERSE) {
    kp = (0 - kp);
    ki = (0 - ki);
    kd = (0 - kd);
  }
}

/* SetTunings(...) *************************************************************
Set Tunings using the last-rembered POn setting
*******************************************************************************/

void PID::SetTunings(float Kp, float Ki, float Kd) {
  SetTunings(Kp, Ki, Kd, pOn);
}

/* SetSampleTime(...) **********************************************************
Sets the period, in Milliseconds, at which the calculation is performed
*******************************************************************************/

void PID::SetSampleTime(int NewSampleTime) {
  float ratio;

  if (NewSampleTime > 0) {
    ratio = (float) NewSampleTime / (float) SampleTime;
    ki *= ratio;
    kd /= ratio;
    SampleTime = (unsigned long) NewSampleTime;
  }
}

/* SetOutputLimits(...) ********************************************************
This function will be used far more often than SetInputLimits. While
the input to the controller will generally be in the 0-1023 range (which is
the default already,)  the output will be a little different.  maybe they'll
be doing a time window and will need 0-8000 or something.  or maybe they'll
want to clamp it from 0-125.  who knows.  at any rate, that can all be done
here.
*******************************************************************************/

void PID::SetOutputLimits(float Min, float Max) {
  if (Min >= Max) return;
  outMin = Min;
  outMax = Max;

  if (inAuto) {
    *myOutput = constrain(*myOutput, outMin, outMax);
    iTerm = constrain(iTerm, outMin, outMax);
  }
}

/* SetMode(...) ****************************************************************
Allows the controller Mode to be set to manual (0) or Automatic (non-zero)
when the transition from manual to auto occurs, the controller is
automatically initialized
*******************************************************************************/

void PID::SetMode(int Mode) {
  bool newAuto = (Mode == AUTOMATIC);
  if (newAuto && !inAuto) {
    // We just went from manual to auto
    PID::Initialize();
  }
  inAuto = newAuto;
}

/* Initialize() ****************************************************************
Does all the things that need to happen to ensure a bumpless transfer
from manual to automatic mode.
*******************************************************************************/

void PID::Initialize() {
  iTerm = *myOutput;
  lastInput = *myInput;

  /*
  // DEBUG info
  Serial.println("PID init");
  if (iTerm < outMin) {
    Serial.println("@PID init: iTerm < outMin: integral windup");
  } else if (iTerm > outMax) {
    Serial.println("@PID init: iTerm > outMax: integral windup");
  }
  */

  iTerm = constrain(iTerm, outMin, outMax);
}

/* SetControllerDirection(...) *************************************************
The PID will either be connected to a DIRECT acting process (+Output leads
to +Input) or a REVERSE acting process(+Output leads to -Input.)  we need to
know which one, because otherwise we may increase the output when we should
be decreasing.  This is called from the constructor.
*******************************************************************************/

void PID::SetControllerDirection(int Direction) {
  if (inAuto && Direction != controllerDirection) {
    kp = (0 - kp);
    ki = (0 - ki);
    kd = (0 - kd);
  }
  controllerDirection = Direction;
}

/* Status Funcions *************************************************************
Just because you set the Kp=-1 doesn't mean it actually happened.  these
functions query the internal state of the PID.  they're here for display
purposes.  this are the functions the PID Front-end uses for example
*******************************************************************************/

float PID::GetKp() {return dispKp;}
float PID::GetKi() {return dispKi;}
float PID::GetKd() {return dispKd;}
int PID::GetMode() {return inAuto ? AUTOMATIC : MANUAL;}
int PID::GetDirection() {return controllerDirection;}