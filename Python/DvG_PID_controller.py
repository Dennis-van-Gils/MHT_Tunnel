#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ported and modified from C++ code:

 /******************************************************************************
 * Arduino PID Library - Version 1.2.1
 * by Brett Beauregard <br3ttb@gmail.com> brettbeauregard.com
 *
 * This Library is licensed under the MIT License
 ******************************************************************************/

 Edited by Dennis van Gils, 02-03-2018
   * Code refactoring.
   * P_ON_M mode has been removed.
   * Made the proportional, integrative and derivative terms accessible.

The 'compute' method should be called repeatedly at a fixed rate. Contrary to
the C library, the method here doesn't check the timing and just computes a
new PID output whenever it gets called. The I and D parameters are time rate
dependent by definition. I and D parameters passed to this class are on a per
second basis. 'Compute' will internally adjust I and D based on the actual
obtained time step between individual 'computes'.

Dennis van Gils
25-06-2018
"""

import numpy as np

import time
from DvG_debug_functions import dprint

# Show debug info in terminal?
DEBUG = False

class Constants:
    MANUAL    = 0
    AUTOMATIC = 1

    DIRECT    = 0
    REVERSE   = 1

class PID():
    def __init__(self, Kp, Ki, Kd, controller_direction=Constants.DIRECT):
        self.setpoint = np.nan
        self.output = np.nan

        # Must be set by set_tunings()
        self.kp = np.nan
        self.ki = np.nan
        self.kd = np.nan

        # Must be set by set_output_limits()
        self.output_limit_min = np.nan
        self.output_limit_max = np.nan

        self.in_auto = False

        self.pTerm = 0
        self.iTerm = 0
        self.dTerm = 0

        self.set_tunings(Kp, Ki, Kd, controller_direction);
        self.set_output_limits(0, 100)

        self.last_time = time.time()
        self.last_input = np.nan

    def compute(self, current_input):
        """ Compute new PID output. This function should be called repeatedly,
        preferably at a fixed time interval.
        Returns True when the output is computed, false when nothing has been
        done.
        """

        now = time.time()        # [s]
        time_step = (now - self.last_time)

        if ((not self.in_auto) or np.isnan(self.setpoint)):
            self.last_time = now;
            return False

        _input = current_input;
        error = self.setpoint - _input;

        # Proportional term
        self.pTerm = self.kp * error

        # Integral term
        #self.iTerm = self.iTerm + (self.ki * error)
        self.iTerm = self.iTerm + (self.ki * time_step * error)

        if DEBUG:
            if (self.iTerm < self.output_limit_min):
                dprint("iTerm < output_limit_min: integral windup")
            elif (self.iTerm > self.output_limit_max):
                dprint("iTerm > output_limit_max: integral windup")

        # Prevent integral windup
        self.iTerm = np.clip(self.iTerm,
                             self.output_limit_min,
                             self.output_limit_max)

        # Derivative term
        # Prevent derivative kick: really good to do!
        #self.dTerm = -self.kd * (_input - self.last_input)
        self.dTerm = -self.kd / time_step * (_input - self.last_input)

        # Compute PID Output
        self.output = self.pTerm + self.iTerm + self.dTerm

        if DEBUG:
            dprint("%i" % (time_step * 1000))
            dprint("%.1f %.1f %.1f" % (self.pTerm, self.iTerm, self.dTerm))
            dprint((" "*14 + "%.2f") % self.output)

            if (self.output < self.output_limit_min):
                dprint("output < output_limit_min: output clamped")
            elif (self.output > self.output_limit_max):
                dprint("output > output_limit_max: output clamped")

        # Clamp the output to its limits
        self.output = np.clip(self.output,
                              self.output_limit_min,
                              self.output_limit_max)

        # Remember some variables for next time
        self.last_input = _input
        self.last_time = now;

        return True

    def set_tunings(self, Kp, Ki, Kd, direction=Constants.DIRECT):
        """ This function allows the controller's dynamic performance to be
        adjusted. It's called automatically from the constructor, but tunings
        can also be adjusted on the fly during normal operation.

        The PID will either be connected to a DIRECT acting process
        (+Output leads to +Input) or a REVERSE acting process (+Output leads to
        -Input). We need to know which one, because otherwise we may increase
        the output when we should be decreasing. This is called from the
        constructor.
        """

        if ((Kp < 0) or (Ki < 0) or (Kd < 0)):
            return

        self.controller_direction = direction

        if (self.controller_direction == Constants.REVERSE):
            self.kp = -Kp
            self.ki = -Ki
            self.kd = -Kd
        else:
            self.kp = Kp
            self.ki = Ki
            self.kd = Kd

    def set_output_limits(self, limit_min, limit_max):
        if (limit_min >= limit_max):
            return

        self.output_limit_min = limit_min
        self.output_limit_max = limit_max

        if (self.in_auto):
            self.output = np.clip(self.output, limit_min, limit_max)
            self.iTerm  = np.clip(self.iTerm , limit_min, limit_max)

    def set_mode(self, mode, current_input, current_output):
        """ Allows the controller Mode to be set to manual (0) or Automatic
        (non-zero). When the transition from manual to auto occurs, the
        controller is automatically initialized.
        """

        new_auto = (mode == Constants.AUTOMATIC)
        if (new_auto and not self.in_auto):
            # We just went from manual to auto
            self.initialize(current_input, current_output)

        self.in_auto = new_auto

    def initialize(self, current_input, current_output):
        """ Does all the things that need to happen to ensure a bumpless
        transfer from manual to automatic mode.
        """
        self.iTerm = current_output
        self.last_input = current_input

        if DEBUG:
            dprint("PID init")
            if (self.iTerm < self.output_limit_min):
                dprint("@PID init: iTerm < output_limit_min: integral windup")
            elif (self.iTerm > self.output_limit_max):
                dprint("@PID init: iTerm > output_limit_max: integral windup")

        self.iTerm = np.clip(self.iTerm,
                             self.output_limit_min,
                             self.output_limit_max)