#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dennis van Gils
16-03-2018
"""

"""
Abbrevations:
    fn_ : string containing filename
    TC  : thermocouple
    chkb: check box       [QtGui.QCheckBox]
    pbtn: push button     [QtGui.QPushButton]
    rbtn: radio button    [QtGui.QRadioButton]

    gw  : [pyqtgraph.GraphicsWindow]
    pi  : [pyqtgraph.PlotItem]
    vb  : [pyqtgraph.ViewBox]
    plot: [pyqtgraph.PlotDataItem]
"""

import sys
import visa
import numpy as np
from queue import Queue
from pathlib import Path

from PyQt5 import QtGui, QtCore
from PyQt5.QtCore import QDateTime
import pyqtgraph as pg

from DvG_debug_functions import ANSI, dprint
from DvG_PyVISA_library import find_visa_device_by_name, resolve_Arduino_1_2
from DvG_PyQt_controls import (create_LED_indicator,
                               create_Toggle_button,
                               SS_TEXTBOX_READ_ONLY,
                               SS_GROUP, SS_TITLE)
from DvG_PyQt_ChartHistory import ChartHistory

import DvG_dev_Picotech_PT104__fun_UDP as fun_PT104
import functions_PolyScience_PD_models_RS232 as fun_PolyScience

# The state of the Arduinos is polled with this time interval [msec]
UPDATE_INTERVAL_ARDUINOS = 500
UPDATE_INTERVAL_PT104    = UPDATE_INTERVAL_ARDUINOS
UPDATE_INTERVAL_BATH     = 1000

# Global variables for date-time keeping
cur_date_time = QDateTime.currentDateTime()
str_cur_date  = cur_date_time.toString("dd-MM-yyyy")
str_cur_time  = cur_date_time.toString("HH:mm:ss")
main_start_time = cur_date_time

# Recirculating temperature bath PolyScience PD15R‐30‐A12E
PATH_CONFIG_BATH = Path("config/port_PolyScience.txt")
ramp_start_degC = 15.0     # [deg C]
ramp_end_degC   = 87.0     # [deg C]
ramp_rate       = 1        # [mK/s]

# Global queue and mutex control containing messages to be send to the Arduinos
# Each queue item should be a list holding two variables:
#   [visa device instance, message string to be send to the device]
#   E.g. [Ard1, "R1 on"], to turn relay 1 on at Arduino #1
Ard_write_msg_queue = Queue()
Ard_write_msg_mutex = QtCore.QMutex()
Ard_write_msg_wait  = QtCore.QWaitCondition()

# Chart histories
N_HEATER_TC = 12
CH_SAMPLES_HEATER_TC = 1200 # [samples], multiply this with UPDATE_INTERVAL_MSEC
                            # to get the history time length

# Lay-out
FONT_DEFAULT   = QtGui.QFont("Arial", 9)
FONT_LARGE     = QtGui.QFont("Verdana", 12)
FONT_MONOSPACE = QtGui.QFont("Courier", 8)
FONT_MONOSPACE.setFamily("Monospace")
FONT_MONOSPACE.setStyleHint(QtGui.QFont.Monospace)

CHAR_DEG_C = chr(176) + 'C'

# Pen styles for plotting
PENS = [None] * 12
params = {'width': 2}
PENS[0]  = pg.mkPen(color=[199, 0  , 191], **params)
PENS[1]  = pg.mkPen(color=[0  , 128, 255], **params)
PENS[2]  = pg.mkPen(color=[0  , 255, 255], **params)
PENS[3]  = pg.mkPen(color=[20 , 200, 20 ], **params)
PENS[4]  = pg.mkPen(color=[255, 255, 0  ], **params)
PENS[5]  = pg.mkPen(color=[255, 0  , 0  ], **params)
params = {'width': 4}#, 'style': QtCore.Qt.DotLine}
PENS[6]  = pg.mkPen(color=[255, 0  , 0  ], **params)
PENS[7]  = pg.mkPen(color=[255, 255, 0  ], **params)
PENS[8]  = pg.mkPen(color=[20 , 200, 20 ], **params)
PENS[9]  = pg.mkPen(color=[0  , 255, 255], **params)
PENS[10] = pg.mkPen(color=[0  , 128, 255], **params)
PENS[11] = pg.mkPen(color=[191, 0  , 191], **params)
params = {'width': 4}
PEN_a = pg.mkPen(color=[0  , 0  , 255], **params)
PEN_b = pg.mkPen(color=[255, 20 , 147], **params)

# Show debug info in terminal? Warning: slow! Do not leave on unintentionally.
DEBUG = False

# ------------------------------------------------------------------------------
#   Arduino state management
# ------------------------------------------------------------------------------

class State(object):
    """
    Reflects the actual hardware state and readings of the Arduinos
    There should only be one instance of the State class
    """
    def __init__(self):
        # State variables that are reported by the Arduinos at run-time
        self.Arduino_1_free_RAM = np.nan
        self.Arduino_2_free_RAM = np.nan
        self.heater_TC_01_degC = np.nan
        self.heater_TC_02_degC = np.nan
        self.heater_TC_03_degC = np.nan
        self.heater_TC_04_degC = np.nan
        self.heater_TC_05_degC = np.nan
        self.heater_TC_06_degC = np.nan
        self.heater_TC_07_degC = np.nan
        self.heater_TC_08_degC = np.nan
        self.heater_TC_09_degC = np.nan
        self.heater_TC_10_degC = np.nan
        self.heater_TC_11_degC = np.nan
        self.heater_TC_12_degC = np.nan
        self.heater_TC_01_bitV = np.nan
        self.heater_TC_02_bitV = np.nan
        self.heater_TC_03_bitV = np.nan
        self.heater_TC_04_bitV = np.nan
        self.heater_TC_05_bitV = np.nan
        self.heater_TC_06_bitV = np.nan
        self.heater_TC_07_bitV = np.nan
        self.heater_TC_08_bitV = np.nan
        self.heater_TC_09_bitV = np.nan
        self.heater_TC_10_bitV = np.nan
        self.heater_TC_11_bitV = np.nan
        self.heater_TC_12_bitV = np.nan
        self.relay_1_1 = np.nan
        self.relay_1_2 = np.nan
        self.relay_1_3 = np.nan
        self.relay_1_4 = np.nan
        self.relay_1_5 = np.nan
        self.relay_1_6 = np.nan
        self.relay_1_7 = np.nan
        self.relay_1_8 = np.nan
        self.relay_2_1 = np.nan
        self.relay_2_2 = np.nan
        self.relay_2_3 = np.nan
        self.relay_2_4 = np.nan
        self.relay_2_5 = np.nan
        self.relay_2_6 = np.nan
        self.relay_2_7 = np.nan
        self.relay_2_8 = np.nan
        self.relay_3_1 = np.nan
        self.relay_3_2 = np.nan
        self.relay_3_3 = np.nan
        self.relay_3_4 = np.nan
        self.relay_3_5 = np.nan
        self.relay_3_6 = np.nan
        self.relay_3_7 = np.nan
        self.relay_3_8 = np.nan
        self.set_pump_speed_mA    = np.nan
        self.read_pump_speed_bitV = np.nan
        self.read_pump_speed_mA   = np.nan
        self.read_flow_rate_bitV  = np.nan
        self.read_flow_rate_mA    = np.nan
        self.ENA_PID_tunnel_flow_rate = np.nan
        self.setpoint_flow_rate_m3h   = np.nan
        self.prox_switch_1  = np.nan
        self.prox_switch_2  = np.nan
        self.prox_switch_3  = np.nan
        self.prox_switch_4  = np.nan
        self.floater_switch = np.nan
        self.FSM_FS_EXEC    = np.nan
        self.FS_unread_msgs_count = 0

        # State variables that are introduced by this Python program
        # -- Arduino communication bookkeeping
        self.Arduino_1_is_alive = True
        self.Arduino_2_is_alive = True
        self.Arduino_1_not_alive_counter = 0
        self.Arduino_2_not_alive_counter = 0
        self.update_counter = 0
        self.starting_up = True

        # -- Derived variables
        self.read_pump_speed_pct = np.nan
        self.read_flow_rate_m3h  = np.nan
        self.set_pump_speed_pct  = np.nan

        # Mutex for proper multithreading
        self.mutex = QtCore.QMutex()

# ------------------------------------------------------------------------------
#   Arduino communication functions
#   A 'Worker' is a class that will allow code to run in a separate thread
# ------------------------------------------------------------------------------

# Reflects the actual hardware state and readings of both the Arduinos
# There should only be one instance!
state = State()

class Worker_Ard_write(QtCore.QObject):
    """
    Messages that are to be send to the Arduinos should be put in the global and
    thread-safe queue 'Ard_write_msg_queue'. Each queue item should be a list
    holding two variables: [visa device instance, message string to be send to
    the device]. This Worker will send all messages currently in the queue and
    FIFO to the Arduinos in a separate thread, whenever it is woken up by
    calling 'Ard_write_msg_wait.wakeAll()'
    """
    def __init__(self, queue):
        super().__init__(None)
        if DEBUG: dprint("Worker_Ard_write: init", ANSI.YELLOW)
        self.msg_queue = queue
        self.running = True

    @QtCore.pyqtSlot()
    def run(self):
        if DEBUG: dprint("Worker_Ard_write: run", ANSI.YELLOW)
        while self.running:
            Ard_write_msg_mutex.lock()

            if DEBUG: dprint("**   Ard_write: waiting for trigger", ANSI.YELLOW)
            Ard_write_msg_wait.wait(Ard_write_msg_mutex)
            if DEBUG: dprint("**   Ard_write: trigger received", ANSI.YELLOW)

            process_queue = True
            while process_queue:
                if not self.msg_queue.empty():
                    # Each queue item should be a list holding two variables:
                    #   [visa device instance,
                    #    message string to be send to the device]
                    [dev, str_msg] = self.msg_queue.get(block = False)

                    if DEBUG: dprint(("Sending %s: %s" % (dev.name, str_msg)),
                                     ANSI.GREEN)
                    dev.mutex.lock()
                    dev.write(str_msg)
                    dev.mutex.unlock()
                else:
                    # No messages in the queue anymore
                    if DEBUG: dprint("Empty queue")
                    process_queue = False

            Ard_write_msg_mutex.unlock()
            if DEBUG: dprint("**   Ard_write: done", ANSI.YELLOW)

class Worker_Ard_read(QtCore.QObject):
    """
    This Worker will read the current state of both Arduinos in a dedicated
    thread and tries to do this at a fixed sampling rate. Basically, it updates
    the global State instance 'state' which reflects the hardware state and
    readings of both Arduinos. This thread runs continuously on its own internal
    timer.

    Every new state acquisition will also subsequently:
        - add these new data points to the history strip charts
        - add a new line to the data log-file, if the user has pressed 'pbtn_record'

    Two signals are fired:
        schedule_GUI_update: When succesfully acquired the state
        connection_lost: When connection lost to Arduino(s)
    """
    schedule_GUI_update = QtCore.pyqtSignal()
    connection_lost = QtCore.pyqtSignal()

    def __init__(self, arduino_device_1, arduino_device_2):
        super().__init__(None)
        if DEBUG: dprint("Worker_Ard_read: init", ANSI.CYAN)

        # Arduino device instances
        self.Ard_1 = arduino_device_1
        self.Ard_2 = arduino_device_2

        # Logging to disk
        self.fn_log = None                  # File name of the log
        self.f_log = None                   # File handle to log
        self.log_start_time = None          # [PyQt5.QtCore.QDateTime]

        self.startup_recording = False      # Used to write header to log
        self.closing_recording = False      # Used to close log file
        self.is_recording = False

    @QtCore.pyqtSlot()
    def run(self):
        if DEBUG: dprint("Worker_Ard_read: run", ANSI.CYAN)
        self.start_time = QDateTime.currentDateTime()

        # Set up and start the state update timer
        self.timer = QtCore.QTimer()
        self.timer.setInterval(UPDATE_INTERVAL_ARDUINOS)
        self.timer.timeout.connect(self.acquire_state)
        # CRITICAL, set timer to 1 ms resolution
        self.timer.setTimerType(QtCore.Qt.PreciseTimer)
        self.timer.start()

    def acquire_state(self):
        # Date-time keeping
        global cur_date_time, str_cur_date, str_cur_time
        cur_date_time = QDateTime.currentDateTime()
        elapsed_time = main_start_time.msecsTo(cur_date_time) # [msec]
        str_cur_date = cur_date_time.toString("dd-MM-yyyy")
        str_cur_time = cur_date_time.toString("HH:mm:ss")

        # Exclusive lock on the State instance
        locker = QtCore.QMutexLocker(state.mutex)
        if DEBUG: dprint("\n**   Ard_read: state locked", ANSI.CYAN)

        # ----------------------------------------------------------------------
        #   Acquire state from Arduinos
        # ----------------------------------------------------------------------
        state.update_counter += 1

        # Assume the Arduinos are not alive
        state.Arduino_1_not_alive_counter += 1
        state.Arduino_2_not_alive_counter += 1

        # Check the alive counters
        if state.Arduino_1_not_alive_counter > 3:
            dprint("Worker determined Arduino 1 is not alive")
            state.Arduino_1_is_alive = False

        if state.Arduino_2_not_alive_counter > 3:
            dprint("Worker determined Arduino 2 is not alive")
            state.Arduino_2_is_alive = False

        if (not state.Arduino_1_is_alive) | (not state.Arduino_2_is_alive):
            locker.unlock()
            self.schedule_GUI_update.emit()
            self.timer.stop()
            app.processEvents()

            self.close_log_at_exit()
            self.connection_lost.emit()
            return

        # ----------------------------------------------------------------------
        #   Arduino 1
        # ----------------------------------------------------------------------

        # Query the Arduino for its state
        try:
            locker_Ard_1 = QtCore.QMutexLocker(self.Ard_1.mutex)
            tmp_state = self.Ard_1.query_ascii_values("?", separator='\t')
            locker_Ard_1.unlock()
        except visa.VisaIOError:
            # Time-out expired: Arduino is likely offline
            state.Arduino_1_not_alive_counter += 1
            dprint("Arduino 1 VisaIOError")
            return
        except:
            raise

        # If the code made it to here the Arduino must have been alive
        if DEBUG: dprint("Ard1 is alive")
        state.Arduino_1_not_alive_counter -= 1

        [state.Arduino_1_free_RAM,
         state.ENA_OTP,
         #state.heater_TC_07_degC,
         #state.heater_TC_08_degC,
         #state.heater_TC_09_degC,
         #state.heater_TC_10_degC,
         #state.heater_TC_11_degC,
         #state.heater_TC_12_degC,
         #state.heater_TC_07_bitV,
         #state.heater_TC_08_bitV,
         #state.heater_TC_09_bitV,
         #state.heater_TC_10_bitV,
         #state.heater_TC_11_bitV,
         #state.heater_TC_12_bitV,
         state.relay_1_1,
         state.relay_1_2,
         state.relay_1_3,
         state.relay_1_4,
         state.relay_1_5,
         state.relay_1_6,
         state.relay_1_7,
         state.relay_1_8,
         state.relay_2_8,
         state.read_GVF_P_diff_bitV,
         state.read_GVF_P_diff_mA,
         state.read_GVF_P_diff_mbar,
         state.set_pump_speed_mA,
         state.read_flow_rate_bitV,
         state.read_flow_rate_mA,
         state.ENA_PID_tunnel_flow_rate,
         state.setpoint_flow_rate_m3h] = tmp_state

        # ----------------------------------------------------------------------
        #   Arduino 2
        # ----------------------------------------------------------------------

        # Query the Arduino for its state
        try:
            locker_Ard_2 = QtCore.QMutexLocker(self.Ard_2.mutex)
            tmp_state = self.Ard_2.query_ascii_values("?", separator='\t')
            locker_Ard_2.unlock()
        except visa.VisaIOError:
            # Time-out expired: Arduino is likely offline
            state.Arduino_2_not_alive_counter += 1
            dprint("Arduino 2 VisaIOError")
            return
        except:
            raise

        # If the code made it to here the Arduino must have been alive
        if DEBUG: dprint("Ard2 is alive")
        state.Arduino_2_not_alive_counter -= 1

        [state.Arduino_2_free_RAM,
         #state.heater_TC_01_degC,
         #state.heater_TC_02_degC,
         #state.heater_TC_03_degC,
         #state.heater_TC_04_degC,
         #state.heater_TC_05_degC,
         #state.heater_TC_06_degC,
         #state.heater_TC_01_bitV,
         #state.heater_TC_02_bitV,
         #state.heater_TC_03_bitV,
         #state.heater_TC_04_bitV,
         #state.heater_TC_05_bitV,
         #state.heater_TC_06_bitV,
         state.relay_3_1,
         state.relay_3_2,
         state.relay_3_3,
         state.relay_3_4,
         state.relay_3_5,
         state.relay_3_6,
         state.relay_3_7,
         state.relay_3_8,
         state.prox_switch_1,
         state.prox_switch_2,
         state.prox_switch_3,
         state.prox_switch_4,
         state.floater_switch,
         state.FSM_FS_EXEC,
         state.FS_unread_msgs_count] = tmp_state

        # DEBUG INFO
        if DEBUG: dprint("%04i - %i" % (state.update_counter, elapsed_time))

        # ----------------------------------------------------------------------
        #   Add readings to stripchart histories
        # ----------------------------------------------------------------------

        heater_TC_degC = ([state.heater_TC_01_degC, state.heater_TC_02_degC,
                           state.heater_TC_03_degC, state.heater_TC_04_degC,
                           state.heater_TC_05_degC, state.heater_TC_06_degC,
                           state.heater_TC_07_degC, state.heater_TC_08_degC,
                           state.heater_TC_09_degC, state.heater_TC_10_degC,
                           state.heater_TC_11_degC, state.heater_TC_12_degC])
        for i in range(N_HEATER_TC):
            window.CHs_heater_TC[i].add_new_reading(elapsed_time,
                                                    heater_TC_degC[i])

        window.CH_bath_setpoint.add_new_reading(elapsed_time,
                                                bath.state.setpoint)
        window.CH_bath_temp.add_new_reading(elapsed_time,
                                            bath.state.P1_temp)

        # ----------------------------------------------------------------------
        #   Logging to file
        # ----------------------------------------------------------------------

        if self.startup_recording:
            self.startup_recording = False
            self.is_recording = True

            # Create log file on disk
            self.fn_log = ("d:/data/TC_calib_" +
                           cur_date_time.toString("yyMMdd_HHmmss") +
                           ".txt")
            window.pbtn_record.setText("Recording to: " + self.fn_log)
            self.log_start_time = cur_date_time

            self.f_log = open(self.fn_log, 'w')
            try:
                self.f_log.write(
                  "elapsed_sec\t" +
                  "wall_time\t" +
                  "TC_01_degC\tTC_02_degC\tTC_03_degC\tTC_04_degC\t" +
                  "TC_05_degC\tTC_06_degC\tTC_07_degC\tTC_08_degC\t" +
                  "TC_09_degC\tTC_10_degC\tTC_11_degC\tTC_12_degC\t" +
                  "TC_01_bitV\tTC_02_bitV\tTC_03_bitV\tTC_04_bitV\t" +
                  "TC_05_bitV\tTC_06_bitV\tTC_07_bitV\tTC_08_bitV\t" +
                  "TC_09_bitV\tTC_10_bitV\tTC_11_bitV\tTC_12_bitV\t" +
                  "bath_setpoint_degC\tbath_temp_degC\t" +
                  "tunnel_inlet_degC\ttunnel_outlet_degC\n")
            except:
                raise

        if self.closing_recording:
            if self.is_recording:
                self.f_log.close()
            self.closing_recording = False
            self.is_recording = False

        if self.is_recording:
            # Add new data to the log
            log_elapsed_time = self.log_start_time.msecsTo(cur_date_time)/1e3  # [sec]

            try:
                self.f_log.write("%.3f\t" % log_elapsed_time)
                self.f_log.write("%s\t" % cur_date_time.toString("HH:mm:ss.zzz"))
                self.f_log.write(("%.2f\t" * 12) % (
                        state.heater_TC_01_degC, state.heater_TC_02_degC,
                        state.heater_TC_03_degC, state.heater_TC_04_degC,
                        state.heater_TC_05_degC, state.heater_TC_06_degC,
                        state.heater_TC_07_degC, state.heater_TC_08_degC,
                        state.heater_TC_09_degC, state.heater_TC_10_degC,
                        state.heater_TC_11_degC, state.heater_TC_12_degC))
                self.f_log.write(("%.1f\t" * 12) % (
                        state.heater_TC_01_bitV, state.heater_TC_02_bitV,
                        state.heater_TC_03_bitV, state.heater_TC_04_bitV,
                        state.heater_TC_05_bitV, state.heater_TC_06_bitV,
                        state.heater_TC_07_bitV, state.heater_TC_08_bitV,
                        state.heater_TC_09_bitV, state.heater_TC_10_bitV,
                        state.heater_TC_11_bitV, state.heater_TC_12_bitV))
                self.f_log.write("%.2f\t%.2f\t" % (
                        bath.state.setpoint,
                        bath.state.P1_temp))
                self.f_log.write("%.3f\t%.3f\n" % (
                        pt104.state.ch1_T, pt104.state.ch2_T))
                #f_log.flush() # Do not force flush, but leave it to the OS
            except:
                raise

        # Release the exclusive lock
        if DEBUG: dprint("**   Ard_read: state unlocked\n", ANSI.CYAN)
        locker.unlock()

        # Trigger sending the queued messages to the Arduinos
        Ard_write_msg_wait.wakeAll()

        # The state was acquired succesfully. Update GUI elements.
        #sleep(0.01)     # Improves readability when printing debug info
        self.schedule_GUI_update.emit()

    @QtCore.pyqtSlot()
    def start_recording(self):
        self.startup_recording = True
        self.closing_recording = False

    @QtCore.pyqtSlot()
    def stop_recording(self):
        self.startup_recording = False
        self.closing_recording = True

    @QtCore.pyqtSlot()
    def close_log_at_exit(self):
        """Can be called at app exit to correctly flush and the close log file,
        but make sure the Worker_Ard_read thread has stopped already to prevent
        IO operations on an already closed log file.
        """
        if self.is_recording:
            print("Closing log at app exit: ", end='')
            self.f_log.close()
            print("done.")

        self.startup_recording = False
        self.closing_recording = False
        self.is_recording = False

# ------------------------------------------------------------------------------
#   update_GUI
# ------------------------------------------------------------------------------

def update_GUI():
    """NOTE: 'state.mutex' is not being locked, because we are only reading
    'state' for displaying purposes. We can do this because most 'state' members
    are written and read atomicly. The few members (e.g. 'read_flow_rate_pct')
    that are written non-atomicly might be displayed wrongly, but this bears no
    consequences. This is because no actuator actions based on the read 'state'
    values are done here. Otherwise we must lock 'state.mutex'. Not locking
    'state.mutex' here potentially speeds up the Arduino read/write threads.
    """
    if DEBUG: dprint("Updating GUI")
    window.str_cur_date_time.setText(str_cur_date + "    " + str_cur_time)
    window.update_counter.setText("%i" % state.update_counter)

    window.alive_1.setChecked(state.Arduino_1_is_alive)
    window.alive_1.setText("%i" % state.Arduino_1_is_alive)
    window.alive_2.setChecked(state.Arduino_2_is_alive)
    window.alive_2.setText("%i" % state.Arduino_2_is_alive)

    # Show free memory
    window.Ard_1_label.setText("#1: %i%% free " %
                               round(state.Arduino_1_free_RAM / 32768 * 100))
    window.Ard_2_label.setText("#2: %i%% free " %
                               round(state.Arduino_2_free_RAM / 32768 * 100))

    window.heater_TC_01_degC.setText("%.2f" % state.heater_TC_01_degC)
    window.heater_TC_02_degC.setText("%.2f" % state.heater_TC_02_degC)
    window.heater_TC_03_degC.setText("%.2f" % state.heater_TC_03_degC)
    window.heater_TC_04_degC.setText("%.2f" % state.heater_TC_04_degC)
    window.heater_TC_05_degC.setText("%.2f" % state.heater_TC_05_degC)
    window.heater_TC_06_degC.setText("%.2f" % state.heater_TC_06_degC)
    window.heater_TC_07_degC.setText("%.2f" % state.heater_TC_07_degC)
    window.heater_TC_08_degC.setText("%.2f" % state.heater_TC_08_degC)
    window.heater_TC_09_degC.setText("%.2f" % state.heater_TC_09_degC)
    window.heater_TC_10_degC.setText("%.2f" % state.heater_TC_10_degC)
    window.heater_TC_11_degC.setText("%.2f" % state.heater_TC_11_degC)
    window.heater_TC_12_degC.setText("%.2f" % state.heater_TC_12_degC)

    window.heater_TC_01_bitV.setText("%.1f" % state.heater_TC_01_bitV)
    window.heater_TC_02_bitV.setText("%.1f" % state.heater_TC_02_bitV)
    window.heater_TC_03_bitV.setText("%.1f" % state.heater_TC_03_bitV)
    window.heater_TC_04_bitV.setText("%.1f" % state.heater_TC_04_bitV)
    window.heater_TC_05_bitV.setText("%.1f" % state.heater_TC_05_bitV)
    window.heater_TC_06_bitV.setText("%.1f" % state.heater_TC_06_bitV)
    window.heater_TC_07_bitV.setText("%.1f" % state.heater_TC_07_bitV)
    window.heater_TC_08_bitV.setText("%.1f" % state.heater_TC_08_bitV)
    window.heater_TC_09_bitV.setText("%.1f" % state.heater_TC_09_bitV)
    window.heater_TC_10_bitV.setText("%.1f" % state.heater_TC_10_bitV)
    window.heater_TC_11_bitV.setText("%.1f" % state.heater_TC_11_bitV)
    window.heater_TC_12_bitV.setText("%.1f" % state.heater_TC_12_bitV)

    window.bath_setpoint_degC.setText("%.2f" % bath.state.setpoint)
    window.bath_temp_degC.setText("%.2f" % bath.state.P1_temp)

    # HACK: Temperature ramp is running in thread?
    if not window._worker_bath.is_ramp_running:
        #window.pbtn_run_ramp.setChecked(True)
        #process_pbtn_record()
    #else:
        window.pbtn_run_ramp.setChecked(False)
        process_pbtn_run_ramp()

    # Update stripchart
    update_chart()

# ------------------------------------------------------------------------------
#   update_chart
# ------------------------------------------------------------------------------

def update_chart():
    # Update curves
    [CH.update_curve() for CH in window.CHs_heater_TC]
    window.CH_bath_setpoint.update_curve()
    window.CH_bath_temp.update_curve()
    window.CH_tunnel_inlet.update_curve()
    window.CH_tunnel_outlet.update_curve()

    # Show or hide curve depending on checkbox
    for i in range(N_HEATER_TC):
        window.CHs_heater_TC[i].curve.setVisible(
                window.chkbs_heater_TC[i].isChecked())
    window.CH_bath_setpoint.curve.setVisible(
            window.chkb_bath_setpoint.isChecked())
    window.CH_bath_temp.curve.setVisible(
            window.chkb_bath_temp.isChecked())
    window.CH_tunnel_inlet.curve.setVisible(
            window.chkb_tunnel_inlet.isChecked())
    window.CH_tunnel_outlet.curve.setVisible(
            window.chkb_tunnel_outlet.isChecked())

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

@QtCore.pyqtSlot()
def process_pbtn_history_1():
    change_history_axes(time_axis_factor=1e3,      # transform [msec] to [sec]
                        time_axis_range=-30,       # [sec]
                        time_axis_label=
                        '<span style="font-size:12pt">history (sec)</span>')

@QtCore.pyqtSlot()
def process_pbtn_history_2():
    change_history_axes(time_axis_factor=1e3,      # transform [msec] to [sec]
                        time_axis_range=-60,       # [sec]
                        time_axis_label=
                        '<span style="font-size:12pt">history (sec)</span>')

@QtCore.pyqtSlot()
def process_pbtn_history_3():
    change_history_axes(time_axis_factor=60e3,     # transform [msec] to [min]
                        time_axis_range=-3,        # [min]
                        time_axis_label=
                        '<span style="font-size:12pt">history (min)</span>')

@QtCore.pyqtSlot()
def process_pbtn_history_4():
    change_history_axes(time_axis_factor=60e3,     # transform [msec] to [min]
                        time_axis_range=-5,        # [min]
                        time_axis_label=
                        '<span style="font-size:12pt">history (min)</span>')

@QtCore.pyqtSlot()
def process_pbtn_history_5():
    change_history_axes(time_axis_factor=60e3,     # transform [msec] to [min]
                        time_axis_range=-10,       # [min]
                        time_axis_label=
                        '<span style="font-size:12pt">history (min)</span>')

@QtCore.pyqtSlot()
def process_pbtn_history_6():
    change_history_axes(time_axis_factor=60e3,     # transform [msec] to [min]
                        time_axis_range=-30,       # [min]
                        time_axis_label=
                        '<span style="font-size:12pt">history (min)</span>')

def change_history_axes(time_axis_factor, time_axis_range, time_axis_label):
    window.pi_heater_TC.setXRange(time_axis_range, 0)
    window.pi_heater_TC.setLabel('bottom', time_axis_label)

    for CH in window.CHs_heater_TC:
        CH.x_axis_divisor = time_axis_factor
    window.CH_bath_setpoint.x_axis_divisor = time_axis_factor
    window.CH_bath_temp.x_axis_divisor = time_axis_factor
    window.CH_tunnel_inlet.x_axis_divisor = time_axis_factor
    window.CH_tunnel_outlet.x_axis_divisor = time_axis_factor

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

def process_pbtn_record():
    if (window.pbtn_record.isChecked()):
        window._worker_Ard_read.start_recording()
    else:
        window._worker_Ard_read.stop_recording()
        window.pbtn_record.setText("Click to start recording to file")

# ------------------------------------------------------------------------------
#   soft_reset
# ------------------------------------------------------------------------------

def soft_reset():
    # First make sure to process all pending events
    app.processEvents()

    # Reset Arduinos to safe initial state
    Ard_write_msg_queue.put([Ard1, "soft_reset"])
    Ard_write_msg_queue.put([Ard2, "soft_reset"])

# ------------------------------------------------------------------------------
#   Close app routines
# ------------------------------------------------------------------------------

def notify_connection_lost():
    # Close crucial threads and timers
    window._Ard_read_thread.quit()
    window._Ard_write_thread.quit()

    window.lbl_title.setText("    " + "! " * 8 + "   CONNECTION LOST   " +
                             " !" * 8 + "    ")

    # Notify user
    str_msg = (str_cur_date + " " + str_cur_time + "\n" +
        "Connection to Arduino(s) has been lost." +
        "\n   Arduino_#1 was alive: " + str(state.Arduino_1_is_alive) +
        "\n   Arduino_#2 was alive: " + str(state.Arduino_2_is_alive) +
        "\n\nExiting...")
    print("\nCRITICAL ERROR: " + str_msg)
    reply = QtGui.QMessageBox.warning(window, "CRITICAL ERROR", str_msg,
                                      QtGui.QMessageBox.Ok)

    if reply == QtGui.QMessageBox.Ok:
        # Leave the GUI open for read-only inspection by the user
        pass

def about_to_quit():
    print("About to quit")

    # First make sure to process all pending events
    app.processEvents()

    # Close threads. Important, because Python will not automatically.
    window._Ard_read_thread.quit()
    print("Closing thread 'Ard_read'    : ", end='')
    if window._Ard_read_thread.wait(2000): print("done.")
    else: print("failed.")

    window._Ard_write_thread.quit()
    print("Closing thread 'Ard_write'   : done.")

    # Thereafter and first of all:
    # Close and flush log to disk!
    # My life for my data!
    window._worker_Ard_read.close_log_at_exit()

    # Close pt-104 thread
    if pt104 is not None:
        window._pt104_read_thread.quit()
        print("Closing thread 'pt104_read'  : ", end='')
        if window._pt104_read_thread.wait(2000): print("done.")
        else: print("failed.")

    # Close PolyScience bath thread
    window._bath_thread.quit()
    print("Closing thread 'bath'        : ", end='')
    if window._bath_thread.wait(2000): print("done.")
    else: print("failed.")

    # Close all device connections
    try: pt104.close()
    except: pass
    try: bath.close()
    except: pass
    try: Ard1.close()
    except: pass
    try: Ard2.close()
    except: pass
    try: rm.close()
    except: pass

# ------------------------------------------------------------------------------
#   PT-104 routines
# ------------------------------------------------------------------------------

class Worker_pt104_read(QtCore.QObject):
    """This Worker will read the status and readings of the PT-104 every
    second.

    NOTE: PT-104 takes roughly 720 ms per channel
    """
    schedule_GUI_update = QtCore.pyqtSignal()
    connection_lost = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__(None)
        if DEBUG: dprint("Worker_PT104_read: init")

    @QtCore.pyqtSlot()
    def run(self):
        if DEBUG: dprint("Worker_PT104_read: run")

        self.timer = QtCore.QTimer()
        self.timer.setInterval(UPDATE_INTERVAL_PT104)
        self.timer.timeout.connect(self.acquire_state)
        self.timer.start()

    def acquire_state(self):
        pt104.keep_alive()
        pt104.read_4_wire_temperature()

        # TO DO: check for connection lost
        #self.connection_lost.emit()

        # Add readings to stripchart histories
        elapsed_time = main_start_time.msecsTo(QDateTime.currentDateTime())
        window.CH_tunnel_inlet.add_new_reading(elapsed_time, pt104.state.ch1_T)
        window.CH_tunnel_outlet.add_new_reading(elapsed_time, pt104.state.ch2_T)

        self.schedule_GUI_update.emit()

def update_GUI_pt104():
    if pt104 is not None:
        window.tunnel_inlet_temp.setText("%.3f" % pt104.state.ch1_T)
        window.tunnel_outlet_temp.setText("%.3f" % pt104.state.ch2_T)

# ------------------------------------------------------------------------------
#   PolyScience PD15R‐30‐A12E routines
# ------------------------------------------------------------------------------

class Worker_bath(QtCore.QObject):
    """This Worker will communicate (both read and write) with the PolyScience
    temperature bath.
    """

    def __init__(self):
        super().__init__(None)

        # Temperature ramp
        self.ramp_start_time = None          # [PyQt5.QtCore.QDateTime]
        self.is_ramp_running = False;

    @QtCore.pyqtSlot()
    def run(self):
        self.ramp_start_time = QDateTime.currentDateTime()

        # Set up and start the timer
        self.timer = QtCore.QTimer()
        self.timer.setInterval(UPDATE_INTERVAL_BATH)
        self.timer.timeout.connect(self.communicate)
        self.timer.start()

    def communicate(self):
        locker = QtCore.QMutexLocker(bath.mutex)

        if self.is_ramp_running:
            # Send new setpoint
            cur_time = QDateTime.currentDateTime()
            elapsed_time = self.ramp_start_time.secsTo(cur_time)  # [sec]

            setpoint_degC = ramp_start_degC + elapsed_time * ramp_rate/1e3

            if (((ramp_rate > 0) and (setpoint_degC > ramp_end_degC)) or
                ((ramp_rate < 0) and (setpoint_degC < ramp_end_degC))):
                # Ramp has reached the end
                setpoint_degC = ramp_end_degC
                self.is_ramp_running = False
                print("Finished ramp at %s" % cur_time.toString("HH:mm:ss"))

            bath.send_setpoint(setpoint_degC)

        bath.query_setpoint()
        bath.query_P1_temp()

    @QtCore.pyqtSlot(float)
    def send_setpoint(self, temp_degC):
        locker = QtCore.QMutexLocker(bath.mutex)
        bath.send_setpoint(temp_degC)

    @QtCore.pyqtSlot()
    def start_ramp(self):
        self.ramp_start_time = QDateTime.currentDateTime()
        self.is_ramp_running = True

    @QtCore.pyqtSlot()
    def end_ramp(self):
        self.is_ramp_running = False

def process_pbtn_run_ramp():
    if window.pbtn_run_ramp.isChecked():
        window._worker_bath.start_ramp()
        window.pbtn_run_ramp.setText("Running")

        # Calculate ETA
        duration = (ramp_end_degC - ramp_start_degC) / (ramp_rate/1e3)  # [s]
        ETA = QDateTime.currentDateTime().addSecs(duration)
        window.ramp_ETA.setText(ETA.toString("HH:mm:ss"))
    else:
        window._worker_bath.end_ramp()
        window.pbtn_run_ramp.setText("Click to start ramp")
        window.ramp_ETA.setText("00:00:00")

def check_temp_text_input(qLineEditObject):
    try:
        temp_degC = float(qLineEditObject.text())
    except ValueError:
        temp_degC = 20.0
    temp_degC = np.clip(temp_degC,
                        fun_PolyScience.BATH_MIN_SETPOINT_DEG_C,
                        fun_PolyScience.BATH_MAX_SETPOINT_DEG_C)
    qLineEditObject.setText("%.2f" % temp_degC)
    return temp_degC

def editingFinished_bath_setpoint():
    temp_degC = check_temp_text_input(window.bath_setpoint_degC_send)

    # Manually changing setpoint is directly send to the bath
    window._worker_bath.send_setpoint(temp_degC)

def editingFinished_ramp_start_degC():
    global ramp_start_degC
    ramp_start_degC = check_temp_text_input(window.ramp_start_degC)

def editingFinished_ramp_end_degC():
    global ramp_end_degC
    ramp_end_degC = check_temp_text_input(window.ramp_end_degC)

def editingFinished_ramp_rate():
    global ramp_rate
    try:
        ramp_rate = float(window.ramp_rate.text())
    except ValueError:
        ramp_rate = 1
    window.ramp_rate.setText("%.2f" % ramp_rate)

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

class MainWindow(QtGui.QWidget):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        self.setGeometry(800, 120, 1200, 660)
        self.setWindowTitle("Thermocouple calibration")

        # -------------------------
        #   Top frame
        # -------------------------

        self.update_counter = QtGui.QLabel("0")

        lbl_title = QtGui.QLabel(text="Thermocouple calibration",
                                 font=FONT_LARGE)
        lbl_title.setStyleSheet(SS_TITLE)
        lbl_title.setAlignment(QtCore.Qt.AlignCenter)
        lbl_title.setMinimumWidth(400)

        self.str_cur_date_time = QtGui.QLabel("00-00-0000    00:00:00")
        self.str_cur_date_time.setAlignment(QtCore.Qt.AlignCenter)

        self.pbtn_exit = QtGui.QPushButton("Exit")
        self.pbtn_exit.clicked.connect(self.close)
        self.pbtn_exit.setMinimumHeight(30)

        self.pbtn_reset = QtGui.QPushButton("Soft reset")
        self.pbtn_reset.setMinimumHeight(30)

        self.alive_1 = create_LED_indicator()
        self.alive_2 = create_LED_indicator()

        self.pbtn_record = create_Toggle_button("Click to start recording to file")

        alive_form_1 = QtGui.QFormLayout()
        self.Ard_1_label = QtGui.QLabel("#1")
        alive_form_1.addRow(self.alive_1, self.Ard_1_label)
        alive_form_2 = QtGui.QFormLayout()
        self.Ard_2_label = QtGui.QLabel("#2")
        alive_form_2.addRow(self.alive_2, self.Ard_2_label)

        grid_top = QtGui.QGridLayout()
        grid_top.addLayout(alive_form_1          , 0, 0)
        grid_top.addLayout(alive_form_2          , 1, 0)
        grid_top.addWidget(self.update_counter   , 2, 0)

        grid_top.addItem(QtGui.QSpacerItem(1, 1) , 0, 1)
        grid_top.addWidget(lbl_title             , 0, 2, 2, 1)
        grid_top.addWidget(self.str_cur_date_time, 2, 2)
        grid_top.addItem(QtGui.QSpacerItem(1, 1) , 0, 3)

        grid_top.addWidget(self.pbtn_exit        , 0, 4)
        grid_top.addWidget(self.pbtn_reset       , 1, 4)
        grid_top.addWidget(self.pbtn_record      , 3, 2)

        #grid_top.addItem(QtGui.QSpacerItem(1, 20), 4, 0)

        grid_top.setColumnStretch(1, 1)
        grid_top.setColumnStretch(3, 1)

        # -------------------------
        #   Tab control frame
        # -------------------------

        tabs = QtGui.QTabWidget()
        tab1 = QtGui.QWidget()

        tabs.addTab(tab1, "Calibration")

        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        #
        #   TAB PAGE 1
        #
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------

        grp_HTC = QtGui.QGroupBox("Heater temp.")
        grp_HTC.setStyleSheet(SS_GROUP)

        p = {'layoutDirection': QtCore.Qt.LeftToRight,
             'checked': True}
        self.chkbs_heater_TC = [QtGui.QCheckBox("#01", **p),
                                QtGui.QCheckBox("#02", **p),
                                QtGui.QCheckBox("#03", **p),
                                QtGui.QCheckBox("#04", **p),
                                QtGui.QCheckBox("#05", **p),
                                QtGui.QCheckBox("#06", **p),
                                QtGui.QCheckBox("#07", **p),
                                QtGui.QCheckBox("#08", **p),
                                QtGui.QCheckBox("#09", **p),
                                QtGui.QCheckBox("#10", **p),
                                QtGui.QCheckBox("#11", **p),
                                QtGui.QCheckBox("#12", **p)]
        self.lbl_heater_TC_bitV = QtGui.QLabel("0-4095")

        p = {'alignment': QtCore.Qt.AlignRight,
             'readOnly': True,
             'minimumWidth': 60,
             'maximumWidth': 0}
        self.heater_TC_01_degC = QtGui.QLineEdit(**p)
        self.heater_TC_02_degC = QtGui.QLineEdit(**p)
        self.heater_TC_03_degC = QtGui.QLineEdit(**p)
        self.heater_TC_04_degC = QtGui.QLineEdit(**p)
        self.heater_TC_05_degC = QtGui.QLineEdit(**p)
        self.heater_TC_06_degC = QtGui.QLineEdit(**p)
        self.heater_TC_07_degC = QtGui.QLineEdit(**p)
        self.heater_TC_08_degC = QtGui.QLineEdit(**p)
        self.heater_TC_09_degC = QtGui.QLineEdit(**p)
        self.heater_TC_10_degC = QtGui.QLineEdit(**p)
        self.heater_TC_11_degC = QtGui.QLineEdit(**p)
        self.heater_TC_12_degC = QtGui.QLineEdit(**p)
        self.heater_TC_01_bitV = QtGui.QLineEdit(**p)
        self.heater_TC_02_bitV = QtGui.QLineEdit(**p)
        self.heater_TC_03_bitV = QtGui.QLineEdit(**p)
        self.heater_TC_04_bitV = QtGui.QLineEdit(**p)
        self.heater_TC_05_bitV = QtGui.QLineEdit(**p)
        self.heater_TC_06_bitV = QtGui.QLineEdit(**p)
        self.heater_TC_07_bitV = QtGui.QLineEdit(**p)
        self.heater_TC_08_bitV = QtGui.QLineEdit(**p)
        self.heater_TC_09_bitV = QtGui.QLineEdit(**p)
        self.heater_TC_10_bitV = QtGui.QLineEdit(**p)
        self.heater_TC_11_bitV = QtGui.QLineEdit(**p)
        self.heater_TC_12_bitV = QtGui.QLineEdit(**p)

        self.pbtn_heater_TC_all  = QtGui.QPushButton("Show all / none")
        self.pbtn_heater_TC_1_6  = QtGui.QPushButton("1 - 6")
        self.pbtn_heater_TC_7_12 = QtGui.QPushButton("7 - 12")

        self.pbtn_heater_TC_all.clicked.connect(self.process_pbtn_heater_TC_all)
        self.pbtn_heater_TC_1_6.clicked.connect(
          lambda: self.process_pbtn_heater_TC_selection(np.linspace(0, 5, 6)))
        self.pbtn_heater_TC_7_12.clicked.connect(
          lambda: self.process_pbtn_heater_TC_selection(np.linspace(6, 11, 6)))

        grid = QtGui.QGridLayout()
        grid.setVerticalSpacing(4)
        grid.addWidget(QtGui.QLabel(CHAR_DEG_C), 0, 1)
        grid.addWidget(self.lbl_heater_TC_bitV, 0, 2)
        for i in range(len(self.chkbs_heater_TC)):
            grid.addWidget(self.chkbs_heater_TC[i], i + 1, 0)
        grid.addWidget(self.heater_TC_01_degC, 1, 1)
        grid.addWidget(self.heater_TC_02_degC, 2, 1)
        grid.addWidget(self.heater_TC_03_degC, 3, 1)
        grid.addWidget(self.heater_TC_04_degC, 4, 1)
        grid.addWidget(self.heater_TC_05_degC, 5, 1)
        grid.addWidget(self.heater_TC_06_degC, 6, 1)
        grid.addWidget(self.heater_TC_07_degC, 7, 1)
        grid.addWidget(self.heater_TC_08_degC, 8, 1)
        grid.addWidget(self.heater_TC_09_degC, 9, 1)
        grid.addWidget(self.heater_TC_10_degC, 10, 1)
        grid.addWidget(self.heater_TC_11_degC, 11, 1)
        grid.addWidget(self.heater_TC_12_degC, 12, 1)
        grid.addWidget(self.heater_TC_01_bitV, 1, 2)
        grid.addWidget(self.heater_TC_02_bitV, 2, 2)
        grid.addWidget(self.heater_TC_03_bitV, 3, 2)
        grid.addWidget(self.heater_TC_04_bitV, 4, 2)
        grid.addWidget(self.heater_TC_05_bitV, 5, 2)
        grid.addWidget(self.heater_TC_06_bitV, 6, 2)
        grid.addWidget(self.heater_TC_07_bitV, 7, 2)
        grid.addWidget(self.heater_TC_08_bitV, 8, 2)
        grid.addWidget(self.heater_TC_09_bitV, 9, 2)
        grid.addWidget(self.heater_TC_10_bitV, 10, 2)
        grid.addWidget(self.heater_TC_11_bitV, 11, 2)
        grid.addWidget(self.heater_TC_12_bitV, 12, 2)
        grid.addWidget(self.pbtn_heater_TC_all , 13, 0, 1, 2)
        grid.addWidget(self.pbtn_heater_TC_1_6 , 14, 0, 1, 2)
        grid.addWidget(self.pbtn_heater_TC_7_12, 15, 0, 1, 2)
        grid.setAlignment(QtCore.Qt.AlignTop)

        grp_HTC.setLayout(grid)

        # Group 0b
        # ---------
        group0b = QtGui.QGroupBox("Temperature bath")
        group0b.setStyleSheet(SS_GROUP)

        p = {'layoutDirection': QtCore.Qt.LeftToRight,
             'checked': True}
        self.chkb_bath_setpoint = QtGui.QCheckBox("Read setpoint", **p)
        self.chkb_bath_temp     = QtGui.QCheckBox("Bath temp.", **p)

        p = {'alignment': QtCore.Qt.AlignRight,
             'minimumWidth': 50,
             'maximumWidth': 0}
        self.bath_setpoint_degC_send = QtGui.QLineEdit("20.0", **p)
        self.bath_setpoint_degC      = QtGui.QLineEdit(**p, readOnly=True)
        self.bath_temp_degC          = QtGui.QLineEdit(**p, readOnly=True)

        grid = QtGui.QGridLayout()
        grid.setVerticalSpacing(4)
        grid.addWidget(QtGui.QLabel("<b>PolyScience PD15R‐30‐A12E</b>"),
                                                      0, 0, 1, 3)
        grid.addWidget(QtGui.QLabel("Send setpoint"), 1, 0)
        grid.addWidget(self.bath_setpoint_degC_send , 1, 1)
        grid.addWidget(QtGui.QLabel(CHAR_DEG_C)     , 1, 2)
        grid.addWidget(self.chkb_bath_setpoint      , 2, 0)
        grid.addWidget(self.bath_setpoint_degC      , 2, 1)
        grid.addWidget(QtGui.QLabel(CHAR_DEG_C)     , 2, 2)
        grid.addWidget(self.chkb_bath_temp          , 3, 0)
        grid.addWidget(self.bath_temp_degC          , 3, 1)
        grid.addWidget(QtGui.QLabel(CHAR_DEG_C)     , 3, 2)
        grid.setAlignment(QtCore.Qt.AlignTop)

        group0b.setLayout(grid)

        # Group 0c
        # ---------
        group0c = QtGui.QGroupBox("Temperature ramp")
        group0c.setStyleSheet(SS_GROUP)

        params = {'alignment': QtCore.Qt.AlignRight,
                  'minimumWidth': 50,
                  'maximumWidth': 0}
        self.ramp_start_degC = QtGui.QLineEdit("%.2f" % ramp_start_degC, **params)
        self.ramp_end_degC   = QtGui.QLineEdit("%.2f" % ramp_end_degC, **params)
        self.ramp_rate       = QtGui.QLineEdit("%.2f" % ramp_rate, **params)
        self.pbtn_run_ramp   = create_Toggle_button("Click to start ramp")
        self.ramp_ETA        = QtGui.QLineEdit("00:00:00", readOnly=True)

        grid = QtGui.QGridLayout()
        grid.setVerticalSpacing(4)
        grid.addWidget(QtGui.QLabel("Start temp."), 0, 0)
        grid.addWidget(QtGui.QLabel("End temp.")  , 1, 0)
        grid.addWidget(QtGui.QLabel("Rate")       , 2, 0)
        grid.addWidget(QtGui.QLabel("ETA")        , 4, 0)
        grid.addWidget(self.ramp_start_degC       , 0, 1)
        grid.addWidget(self.ramp_end_degC         , 1, 1)
        grid.addWidget(self.ramp_rate             , 2, 1)
        grid.addWidget(self.ramp_ETA              , 4, 1, 1, 2)
        grid.addWidget(QtGui.QLabel(CHAR_DEG_C)   , 0, 2)
        grid.addWidget(QtGui.QLabel(CHAR_DEG_C)   , 1, 2)
        grid.addWidget(QtGui.QLabel("mK/s")       , 2, 2)
        grid.addWidget(self.pbtn_run_ramp         , 3, 0, 1, 3)
        grid.setAlignment(QtCore.Qt.AlignTop)

        group0c.setLayout(grid)

        # ---------------------------------------------------------------------
        # ---------------------------------------------------------------------
        #
        #   Live temperature plot
        #
        # ---------------------------------------------------------------------
        # ---------------------------------------------------------------------

        # GraphicsWindow
        self.gw_heater_TC = pg.GraphicsWindow()
        self.gw_heater_TC.setBackground([20, 20, 20])

        # PlotItem
        self.pi_heater_TC = self.gw_heater_TC.addPlot()
        self.pi_heater_TC.setTitle(
          '<span style="font-size:12pt">Temperatures</span>')
        self.pi_heater_TC.setLabel('bottom',
          '<span style="font-size:12pt">history (min)</span>')
        self.pi_heater_TC.setLabel('left',
          '<span style="font-size:12pt">temperature ('+CHAR_DEG_C+')</span>')
        self.pi_heater_TC.showGrid(x=1, y=1)
        self.pi_heater_TC.setMenuEnabled(True)
        self.pi_heater_TC.enableAutoRange(axis=pg.ViewBox.XAxis, enable=False)
        self.pi_heater_TC.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
        self.pi_heater_TC.setAutoVisible(y=True)

        # Viewbox properties for the legend
        vb = self.gw_heater_TC.addViewBox(enableMenu=False)
        vb.setMaximumWidth(140)

        # Legend
        legend = pg.LegendItem()
        legend.setParentItem(vb)
        legend.anchor((0,0), (0,0), offset=(1, 40))
        legend.setFixedWidth(115)
        legend.setScale(1)

        # Create Chart Histories and PlotDataItems and link them together
        # Also add legend entries
        self.CHs_heater_TC = [None] * N_HEATER_TC
        for i in range(N_HEATER_TC):
            self.CHs_heater_TC[i] = ChartHistory(
                    CH_SAMPLES_HEATER_TC, self.pi_heater_TC.plot(pen=PENS[i]))
            legend.addItem(self.CHs_heater_TC[i].curve, name=('#%02i' % (i+1)))

        self.CH_bath_setpoint = ChartHistory(
                CH_SAMPLES_HEATER_TC, self.pi_heater_TC.plot(pen=PEN_a))
        self.CH_bath_temp = ChartHistory(
                CH_SAMPLES_HEATER_TC, self.pi_heater_TC.plot(pen=PEN_b))
        legend.addItem(self.CH_bath_setpoint.curve, name="setpoint")
        legend.addItem(self.CH_bath_temp.curve, name="bath temp")

        self.CH_tunnel_outlet = ChartHistory(
                CH_SAMPLES_HEATER_TC, self.pi_heater_TC.plot(pen=PENS[5]))
        self.CH_tunnel_inlet = ChartHistory(
                CH_SAMPLES_HEATER_TC, self.pi_heater_TC.plot(pen=PENS[1]))
        legend.addItem(self.CH_tunnel_outlet.curve, name="tunnel outlet")
        legend.addItem(self.CH_tunnel_inlet.curve , name="tunnel inlet")

        # ----------------------------------------------------------------------
        #   PT104 temperatures
        # ----------------------------------------------------------------------

        grp_tunnel_temp = QtGui.QGroupBox("PT104 (" + u"\u00B1" + " 0.015 K)")
        grp_tunnel_temp.setStyleSheet(SS_GROUP)

        p = {'layoutDirection': QtCore.Qt.LeftToRight,
             'checked': True}

        self.chkb_tunnel_outlet = QtGui.QCheckBox("Tunnel outlet", **p)
        self.chkb_tunnel_inlet  = QtGui.QCheckBox("Tunnel inlet", **p)

        params = {'alignment': QtCore.Qt.AlignCenter,
                  'minimumWidth': 60,
                  'maximumWidth': 0}
        self.tunnel_outlet_temp = QtGui.QLineEdit(**params, readOnly=True)
        self.tunnel_inlet_temp  = QtGui.QLineEdit(**params, readOnly=True)

        grid = QtGui.QGridLayout()
        grid.setVerticalSpacing(4)
        grid.addWidget(QtGui.QLabel(CHAR_DEG_C), 0, 1)
        grid.addWidget(self.chkb_tunnel_outlet , 1, 0)
        grid.addWidget(self.chkb_tunnel_inlet  , 2, 0)
        grid.addWidget(self.tunnel_outlet_temp , 1, 1)
        grid.addWidget(self.tunnel_inlet_temp  , 2, 1)

        grp_tunnel_temp.setLayout(grid)

        # User controls
        # -------------
        group2 = QtGui.QGroupBox("History")
        group2.setStyleSheet(SS_GROUP)

        self.pbtn_history_1 = QtGui.QPushButton("00:30")
        self.pbtn_history_2 = QtGui.QPushButton("01:00")
        self.pbtn_history_3 = QtGui.QPushButton("03:00")
        self.pbtn_history_4 = QtGui.QPushButton("05:00")
        self.pbtn_history_5 = QtGui.QPushButton("10:00")
        #self.pbtn_history_6 = QtGui.QPushButton("60:00")

        self.pbtn_history_clear = QtGui.QPushButton("clear")
        self.pbtn_history_clear.clicked.connect(self.clear_all_charts)

        grid = QtGui.QGridLayout()
        grid.addWidget(self.pbtn_history_1, 0, 0)
        grid.addWidget(self.pbtn_history_2, 1, 0)
        grid.addWidget(self.pbtn_history_3, 2, 0)
        grid.addWidget(self.pbtn_history_4, 3, 0)
        grid.addWidget(self.pbtn_history_5, 4, 0)
        #grid.addWidget(self.pbtn_history_6, 5, 0)
        grid.addWidget(self.pbtn_history_clear, 6, 0)

        group2.setLayout(grid)


        # Round up tab page 1
        # -------------------

        vbox1 = QtGui.QVBoxLayout()
        vbox1.addWidget(grp_HTC)
        vbox1.addWidget(group0b)
        vbox1.addWidget(group0c)
        vbox1.addStretch()

        vbox2 = QtGui.QVBoxLayout()
        vbox2.addWidget(grp_tunnel_temp)
        vbox2.addWidget(group2)
        vbox2.addStretch()

        hbox = QtGui.QHBoxLayout()
        hbox.addLayout(vbox1)
        hbox.addWidget(self.gw_heater_TC, 2)
        hbox.addLayout(vbox2)

        tab1.setLayout(hbox)

        # -------------------------
        #   Round up full window
        # -------------------------

        vbox = QtGui.QVBoxLayout(self)
        vbox.addLayout(grid_top)
        vbox.addWidget(tabs)

    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------

    def process_pbtn_heater_TC_all(self):
        # First: if any heater is hidden --> show all
        # Second: if all heaters are shown --> hide all
        any_hidden = False
        for i in range(len(self.chkbs_heater_TC)):
            if (not self.chkbs_heater_TC[i].isChecked()):
                self.chkbs_heater_TC[i].setChecked(True)
                any_hidden = True

        if (not any_hidden):
            for i in range(len(self.chkbs_heater_TC)):
                self.chkbs_heater_TC[i].setChecked(False)

    def process_pbtn_heater_TC_selection(self, heaters_idx_array):
        for i in range(len(self.chkbs_heater_TC)):
            if (np.any(heaters_idx_array == i)):
                self.chkbs_heater_TC[i].setChecked(True)
            else:
                self.chkbs_heater_TC[i].setChecked(False)

    def clear_all_charts(self):
        str_msg = "Are you sure you want to clear all charts?"
        reply = QtGui.QMessageBox.warning(self, "Clear charts", str_msg,
                                          QtGui.QMessageBox.Yes |
                                          QtGui.QMessageBox.No,
                                          QtGui.QMessageBox.No)

        if reply == QtGui.QMessageBox.Yes:
            [CH.clear() for CH in self.CHs_heater_TC]
            self.CH_bath_setpoint.clear()
            self.CH_bath_temp.clear()
            self.CH_tunnel_inlet.clear()
            self.CH_tunnel_outlet.clear()

# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
#
#   MAIN
#
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------

if __name__ == '__main__':
    # Open VISA resource manager and search for Arduinos
    rm = visa.ResourceManager()

    #(Arduino_device_adresses, Arduino_device_names) = \
    #    find_visa_device_by_name(rm, "Atmel Corp. EDBG USB Port")
    (Arduino_device_adresses, Arduino_device_names) = \
        find_visa_device_by_name(rm, "Arduino M0 PRO Native Port")

    # Determine which one is Arduino #1 and which one is Arduino #2 and return
    # the VISA device instances to the respective Arduinos
    (Ard1, Ard2) = \
        resolve_Arduino_1_2(rm,
                            Arduino_device_adresses,
                            Arduino_device_names,
                            baud_rate=9600)

    if Ard1 == [] or Ard2 == []:
        print("Check connections and try resetting the Arduinos and wait 8 sec")
        print("Exiting...\n")
        rm.close()
        sys.exit(1)
    else:
        print() # Terminal esthetics
        Ard1.timeout = 50
        Ard2.timeout = 50

        # Add mutex to Arduino device instances to control read and write
        # operations across multiple threads
        Ard1.mutex = QtCore.QMutex()
        Ard2.mutex = QtCore.QMutex()

    # --------------------------------------------------------------------------
    #   Connect to and set up PicoTech PT-104 temperature logger
    # --------------------------------------------------------------------------

    IP_ADDRESS = "10.10.100.2"
    PORT       = 1234
    ENA_channels  = [1, 1, 0, 0]
    gain_channels = [1, 1, 0, 0]

    pt104 = fun_PT104.PT104()

    if pt104.connect(IP_ADDRESS, PORT):
        pt104.begin()
        pt104.start_conversion(ENA_channels, gain_channels)
    else:
        print("ERROR: Could not connect to PT-104 and acquire a lock.")
        pt104 = None

    # --------------------------------------------------------------------------
    #   Create application
    # --------------------------------------------------------------------------

    app = 0    # Work-around for kernel crash when using Spyder IDE
    app = QtGui.QApplication(sys.argv)
    app.setFont(FONT_DEFAULT)
    app.setStyleSheet(SS_TEXTBOX_READ_ONLY)
    app.aboutToQuit.connect(about_to_quit)

    # Create window
    window = MainWindow()

    # --------------------------------------------------------------------------
    #   Open connection to PolyScience PD15R‐30‐A12E recirculating bath
    # --------------------------------------------------------------------------

    # Create a PolyScience_bath class instance
    bath = fun_PolyScience.PolyScience_bath()

    # Were we able to connect to a PolyScience bath?
    if bath.auto_connect(PATH_CONFIG_BATH):
        # TO DO: display internal settings of the PolyScience bath, like
        # its temperature limits, etc.
        pass
    else:
        sys.exit(0)

    # Create mutex for multithreading
    bath.mutex = QtCore.QMutex()

    # Retrieve the bath internal parameters
    bath.query_setpoint()
    bath.query_P1_temp()

    window.bath_setpoint_degC_send.setText("%.2f" % bath.state.setpoint)
    window.bath_setpoint_degC.setText("%.2f" % bath.state.setpoint)

    # --------------------------------------------------------------------------
    #   Set up multithreading
    # --------------------------------------------------------------------------

    # --------------------------
    #   Thread: Arduino read
    # --------------------------

    window._Ard_read_thread = QtCore.QThread()
    window._worker_Ard_read = Worker_Ard_read(Ard1, Ard2)
    window._worker_Ard_read.moveToThread(window._Ard_read_thread)
    window._Ard_read_thread.started.connect(window._worker_Ard_read.run)
    window._Ard_read_thread.start()
    # CRITICAL
    window._Ard_read_thread.setPriority(QtCore.QThread.TimeCriticalPriority)

    # Connect signals from worker
    window._worker_Ard_read.schedule_GUI_update.connect(update_GUI)
    window._worker_Ard_read.connection_lost.connect(notify_connection_lost)

    # --------------------------
    #   Thread: Arduino write
    # --------------------------

    window._Ard_write_thread = QtCore.QThread()
    window._worker_Ard_write = Worker_Ard_write(Ard_write_msg_queue)
    window._worker_Ard_write.moveToThread(window._Ard_write_thread)
    window._Ard_write_thread.started.connect(window._worker_Ard_write.run)
    window._Ard_write_thread.start()

    # --------------------------
    #   Thread: PT104 read
    # --------------------------

    if pt104 is not None:
        window._pt104_read_thread = QtCore.QThread()
        window._worker_pt104_read = Worker_pt104_read()
        window._worker_pt104_read.moveToThread(window._pt104_read_thread)
        window._pt104_read_thread.started.connect(window._worker_pt104_read.run)
        window._pt104_read_thread.start()

        # Connect signals from worker
        window._worker_pt104_read.schedule_GUI_update.connect(update_GUI_pt104)

    # --------------------------
    #   Thread: PolyScience bath
    # --------------------------

    window._bath_thread = QtCore.QThread()
    window._worker_bath = Worker_bath()
    window._worker_bath.moveToThread(window._bath_thread)
    window._bath_thread.started.connect(window._worker_bath.run)
    window._bath_thread.start()

    # --------------------------------------------------------------------------
    #   Connect remaining signals from GUI
    # --------------------------------------------------------------------------

    window.pbtn_reset.clicked.connect(soft_reset)
    window.pbtn_record.clicked.connect(process_pbtn_record)

    window.pbtn_history_1.clicked.connect(process_pbtn_history_1)
    window.pbtn_history_2.clicked.connect(process_pbtn_history_2)
    window.pbtn_history_3.clicked.connect(process_pbtn_history_3)
    window.pbtn_history_4.clicked.connect(process_pbtn_history_4)
    window.pbtn_history_5.clicked.connect(process_pbtn_history_5)

    window.bath_setpoint_degC_send.editingFinished.connect(
            editingFinished_bath_setpoint)
    window.ramp_start_degC.editingFinished.connect(
            editingFinished_ramp_start_degC)
    window.ramp_end_degC.editingFinished.connect(
            editingFinished_ramp_end_degC)
    window.ramp_rate.editingFinished.connect(editingFinished_ramp_rate)
    window.pbtn_run_ramp.clicked.connect(process_pbtn_run_ramp)

    # --------------------------------------------------------------------------
    #   Last inits
    # --------------------------------------------------------------------------

    # Init the time axis of the strip charts
    process_pbtn_history_3()

    # --------------------------------------------------------------------------
    #   Start the main GUI loop
    # --------------------------------------------------------------------------

    window.show()
    sys.exit(app.exec_())