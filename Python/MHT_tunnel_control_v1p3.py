#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dennis van Gils
11-10-2018
"""

import os
import sys
import psutil
import visa
import pylab
import numpy as np

from PyQt5 import QtCore, QtGui
from PyQt5 import QtWidgets as QtWid
from PyQt5.QtCore import QDateTime
import pyqtgraph as pg

import MHT_tunnel_constants as C
import MHT_tunnel_GUI_v1p3  as MHT_tunnel_GUI

from DvG_debug_functions import ANSI, dprint, print_fancy_traceback as pft
from DvG_pyqt_FileLogger import FileLogger
from DvG_pyqt_ChartHistory import ChartHistory
from DvG_dev_Base__pyqt_lib import DAQ_trigger

import DvG_dev_Arduino__fun_serial            as Arduino_functions
import DvG_dev_Arduino__pyqt_lib__MHT_version as Arduino_pyqt_lib

# Peripheral devices
import DvG_dev_Bronkhorst_MFC__fun_RS232        as mfc_functions
import DvG_dev_Bronkhorst_MFC__pyqt_lib         as mfc_pyqt_lib
import DvG_dev_Keysight_N8700_PSU__fun_SCPI     as N8700_functions
import DvG_dev_Keysight_N8700_PSU__pyqt_lib     as N8700_pyqt_lib
import DvG_dev_Picotech_PT104__fun_UDP          as pt104_functions
import DvG_dev_Picotech_PT104__pyqt_lib         as pt104_pyqt_lib
import DvG_dev_ThermoFlex_chiller__fun_RS232    as chiller_functions
import DvG_dev_ThermoFlex_chiller__pyqt_lib     as chiller_pyqt_lib
import DvG_dev_Keysight_3497xA__fun_SCPI        as K3497xA_functions
import DvG_dev_Keysight_3497xA__pyqt_lib        as K3497xA_pyqt_lib
import DvG_dev_Compax3_traverse__fun_RS232      as compax3_functions
import DvG_dev_Compax3_traverse__pyqt_lib       as compax3_pyqt_lib
import DvG_dev_Compax3_step_navigator__pyqt_lib as step_nav_pyqt_lib

# Global variables for date-time keeping
cur_date_time = QDateTime.currentDateTime()
str_cur_date  = cur_date_time.toString("dd-MM-yyyy")
str_cur_time  = cur_date_time.toString("HH:mm:ss")

fn_log = ""
fn_log_mux2 = ""

# Show debug info in terminal? Warning: slow! Do not leave on unintentionally.
DEBUG = False

# ------------------------------------------------------------------------------
#   Arduino state management
# ------------------------------------------------------------------------------

class State(object):
    """Reflects the actual hardware state and readings of both Arduinos.
    There should only be one instance of the State class.
    """
    def __init__(self):
        # State variables that are reported by the Arduinos at run-time
        self.time = np.nan
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
        self.ENA_OTP   = np.nan
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
        self.read_GVF_P_diff_bitV = np.nan
        self.read_GVF_P_diff_mA   = np.nan
        self.read_GVF_P_diff_mbar = np.nan
        self.set_pump_speed_mA    = np.nan
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
        self.FS_new_msgs = []

        # -- Derived variables
        self.read_flow_rate_m3h = np.nan
        self.set_pump_speed_pct = np.nan

        # -- Cross-sectional area of the current measurement section [m2]
        self.area_meas_section = np.nan

        # -- Gas volume fraction (GVF)
        self.GVF_density_liquid = np.nan
        self.GVF_pct = np.nan

        # Mutex for proper multithreading
        self.mutex = QtCore.QMutex()
        self.starting_up = True

# Reflects the actual hardware state and readings of both the Arduinos
# There should only be one instance!
state = State()

# ------------------------------------------------------------------------------
#   my_Arduino_DAQ_update
# ------------------------------------------------------------------------------

def my_Arduino_DAQ_update():
    """Read the current state of both Arduinos in a dedicated thread and do this
    at a fixed sampling rate. Basically, it updates the global State instance
    'state' which reflects the hardware state and readings of both Arduinos.
    This thread runs continuously on its own internal timer.

    Every new state acquisition will also subsequently:
        - add these new data points to the history strip charts
        - add a new line to the data log-file, if the user has pressed 'record'

    Two signals are fired:
        GUI_update: When succesfully acquired the state
        connection_lost: When connection lost to Arduino(s)

    Returns [successfull update Arduino 1?, successfull update Arduino 2?]
    """
    # Date-time keeping
    global cur_date_time, str_cur_date, str_cur_time
    cur_date_time = QDateTime.currentDateTime()
    str_cur_date = cur_date_time.toString("dd-MM-yyyy")
    str_cur_time = cur_date_time.toString("HH:mm:ss")

    success1 = False
    success2 = False

    # ---------------------------------------
    #   Query Arduino 1 for its state
    # ---------------------------------------

    [success, tmp_state] = ard1.query_ascii_values("?", separator='\t')
    if not(success):
        dprint("'%s' reports IOError @ %s %s" %
               (ard1.name, str_cur_date, str_cur_time))
    else:
        # Parse readings into separate state variables
        try:
            [state.Arduino_1_free_RAM,
             state.ENA_OTP,
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
        except Exception as err:
            pft(err, 3)
            dprint("'%s' reports IOError @ %s %s" %
                   (ard1.name, str_cur_date, str_cur_time))
        else:
            success1 = True

    # ---------------------------------------
    #   Query Arduino 2 for its state
    # ---------------------------------------

    [success, tmp_state] = ard2.query_ascii_values("?", separator='\t')
    if not(success):
        dprint("'%s' reports IOError @ %s %s" %
               (ard2.name, str_cur_date, str_cur_time))
    else:
        # Parse readings into separate state variables
        try:
            [state.Arduino_2_free_RAM,
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
        except Exception as err:
            pft(err, 3)
            dprint("'%s' reports IOError @ %s %s" %
                   (ard2.name, str_cur_date, str_cur_time))
        else:
            success2 = True

    while (state.FS_unread_msgs_count > 0):
        [success, ans_str] = ard2.query("FS_msg?")
        if success:
            state.FS_new_msgs.append(ans_str)
            state.FS_unread_msgs_count -= 1
        else:
            dprint("'%s' reports IOError @ %s %s" %
                   (ard2.name, str_cur_date, str_cur_time))
            success2 = False
            break

    # ---------------------------------------
    #   Success check
    # ---------------------------------------

    if not(success1 and success2):
        return [success1, success2]

    # ---------------------------------------
    #   Happy
    # ---------------------------------------

    state.time = cur_date_time.toMSecsSinceEpoch()

    # Transform read_flow_rate_mA to m3/h
    state.read_flow_rate_m3h = (
        np.clip((state.read_flow_rate_mA - 4)/16, 0, 1) * C.QMAX_FLOW_METER)

    # Transform set_pump_speed_mA to % of full scale
    state.set_pump_speed_pct = (
        np.clip((state.set_pump_speed_mA - 4)/16, 0, 1) * 100)

    # Calculate gas volume fraction (GVF) percentage
    state.GVF_pct = (state.read_GVF_P_diff_mbar * 1e2 / C.GRAVITY /
                     C.GVF_PORTHOLE_DISTANCE / state.GVF_density_liquid *
                     100)

    # ---------------------------------------
    #   Add readings to strip chart histories
    # ---------------------------------------

    window.CH_flow_speed.add_new_reading(state.time,
                                         state.read_flow_rate_m3h)

    window.CH_set_pump_speed.add_new_reading(state.time,
                                             state.set_pump_speed_pct)

    # ---------------------------------------
    #   Logging to file
    # ---------------------------------------

    if file_logger.starting:
        #fn_log = ("d:/data/" + cur_date_time.toString("yyMMdd_HHmmss") + ".txt")
        if file_logger.create_log(state.time, fn_log, mode='w'):
            file_logger.signal_set_recording_text.emit(
                "Recording to file: " + fn_log)

            # Header
            file_logger.write("[HEADER]\n")
            file_logger.write("Gravity [m2/s]:\t%.2f\n" % C.GRAVITY)
            file_logger.write("Area meas. section [m2]:\t%.4f\n" %
                             state.area_meas_section)
            file_logger.write("GVF porthole distance [m]:\t%.3f\n" %
                             C.GVF_PORTHOLE_DISTANCE)
            file_logger.write("Density liquid [kg/m3]:\t%.0f\n" %
                             state.GVF_density_liquid)
            file_logger.write("[DATA]\n")
            file_logger.write("[s]\t[HH:mm:ss]\t"
                             "[m3/h]\t[m3/h]\t[pct]\t"
                             "[ln/min]\t[mbar]\t" +
                             ("[" + u'\N{DEGREE SIGN}' "C]\t") * 17 +
                             "[W]\t[W]\t[W]\n")
            file_logger.write("time\twall_time\t"
                             "Q_tunnel_setp\tQ_tunnel\tS_pump_setp\t"
                             "Q_bubbles\tPdiff_GVF\t"
                             "T_TC_01\tT_TC_02\tT_TC_03\tT_TC_04\t"
                             "T_TC_05\tT_TC_06\tT_TC_07\tT_TC_08\t"
                             "T_TC_09\tT_TC_10\tT_TC_11\tT_TC_12\t"
                             "T_ambient\tT_inlet\tT_outlet\t"
                             "T_chill_setp\tT_chill\t"
                             "P_PSU_1\tP_PSU_2\tP_PSU_3\n")

    if file_logger.stopping:
        file_logger.signal_set_recording_text.emit(
            "Click to start recording to file")
        file_logger.close_log()

    if file_logger.is_recording:
        log_elapsed_time = (state.time - file_logger.start_time)/1e3  # [sec]

        # Add new data to the log
        file_logger.write("%.3f\t" % log_elapsed_time)
        file_logger.write("%s\t" % cur_date_time.toString("HH:mm:ss.zzz"))
        file_logger.write("%.3f\t" % state.setpoint_flow_rate_m3h)
        file_logger.write("%.3f\t" % state.read_flow_rate_m3h)
        file_logger.write("%.3f\t" % state.set_pump_speed_pct)
        file_logger.write("%.2f\t" % mfc.state.flow_rate)
        file_logger.write("%.2f\t" % state.read_GVF_P_diff_mbar)
        file_logger.write(("%.2f\t" * 12) % (
                state.heater_TC_01_degC, state.heater_TC_02_degC,
                state.heater_TC_03_degC, state.heater_TC_04_degC,
                state.heater_TC_05_degC, state.heater_TC_06_degC,
                state.heater_TC_07_degC, state.heater_TC_08_degC,
                state.heater_TC_09_degC, state.heater_TC_10_degC,
                state.heater_TC_11_degC, state.heater_TC_12_degC))
        file_logger.write("%.3f\t%.3f\t%.3f\t" % (
                pt104.state.ch3_T, pt104.state.ch1_T, pt104.state.ch2_T))
        file_logger.write("%.1f\t%.1f\t" % (
                chiller.state.setpoint, chiller.state.temp))
        file_logger.write("%.2f\t" % psus[0].state.P_meas)
        file_logger.write("%.2f\t" % psus[1].state.P_meas)
        file_logger.write("%.2f\n" % psus[2].state.P_meas)

    return [True, True]

# ------------------------------------------------------------------------------
#   update_GUI
# ------------------------------------------------------------------------------

@QtCore.pyqtSlot()
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
    window.update_counter.setText("%i" %
                                  ards_pyqt.DAQ_update_counter)
    window.lbl_DAQ_rate.setText("DAQ: %.1f Hz" %
                                ards_pyqt.obtained_DAQ_rate_Hz)

    # Show free memory
    if ard1.is_alive:
        window.Ard_1_label.setText("Arduino #1: %i%% free " %
                                   round(state.Arduino_1_free_RAM/32768*100))
    else:
        window.Ard_1_label.setText("Arduino #1: OFFLINE")
    if ard2.is_alive:
        window.Ard_2_label.setText("Arduino #2: %i%% free " %
                                   round(state.Arduino_2_free_RAM/32768*100))
    else:
        window.Ard_2_label.setText("Arduino #2: OFFLINE")

    window.heater_TC_01_degC.setText("%.1f" % state.heater_TC_01_degC)
    window.heater_TC_02_degC.setText("%.1f" % state.heater_TC_02_degC)
    window.heater_TC_03_degC.setText("%.1f" % state.heater_TC_03_degC)
    window.heater_TC_04_degC.setText("%.1f" % state.heater_TC_04_degC)
    window.heater_TC_05_degC.setText("%.1f" % state.heater_TC_05_degC)
    window.heater_TC_06_degC.setText("%.1f" % state.heater_TC_06_degC)
    window.heater_TC_07_degC.setText("%.1f" % state.heater_TC_07_degC)
    window.heater_TC_08_degC.setText("%.1f" % state.heater_TC_08_degC)
    window.heater_TC_09_degC.setText("%.1f" % state.heater_TC_09_degC)
    window.heater_TC_10_degC.setText("%.1f" % state.heater_TC_10_degC)
    window.heater_TC_11_degC.setText("%.1f" % state.heater_TC_11_degC)
    window.heater_TC_12_degC.setText("%.1f" % state.heater_TC_12_degC)

    window.relay_1_1.setChecked(state.relay_1_1)
    window.relay_1_2.setChecked(state.relay_1_2)
    window.relay_1_3.setChecked(state.relay_1_3)
    window.relay_1_4.setChecked(state.relay_1_4)
    window.relay_1_5.setChecked(state.relay_1_5)
    window.relay_1_6.setChecked(state.relay_1_6)
    window.relay_1_7.setChecked(state.relay_1_7)
    window.relay_1_8.setChecked(state.relay_1_8)

    window.relay_1_1.setText("%i" % state.relay_1_1)
    window.relay_1_2.setText("%i" % state.relay_1_2)
    window.relay_1_3.setText("%i" % state.relay_1_3)
    window.relay_1_4.setText("%i" % state.relay_1_4)
    window.relay_1_5.setText("%i" % state.relay_1_5)
    window.relay_1_6.setText("%i" % state.relay_1_6)
    window.relay_1_7.setText("%i" % state.relay_1_7)
    window.relay_1_8.setText("%i" % state.relay_1_8)

    window.enable_pump.setChecked(state.relay_2_8)
    if window.enable_pump.isChecked():
        window.enable_pump.setText("Pump ON")
    else:
        window.enable_pump.setText("Pump OFF")

    window.enable_pump_PID.setChecked(state.ENA_PID_tunnel_flow_rate)
    if state.ENA_PID_tunnel_flow_rate:
        window.enable_pump_PID.setText("PID feedback ON")

        window.set_pump_speed_pct.setText("%.1f" %
            ((state.set_pump_speed_mA - 4)/16*100))
        window.set_pump_speed_mA.setText("%.2f" % state.set_pump_speed_mA)

        window.set_pump_speed_pct.setReadOnly(True)
        window.set_pump_speed_mA.setReadOnly(True)
    else:
        window.enable_pump_PID.setText("PID feedback OFF")
        window.set_pump_speed_pct.setReadOnly(False)
        window.set_pump_speed_mA.setReadOnly(False)

    if state.starting_up:
        # Insert the last setpoints known to the Arduinos into textboxes only at
        # the start of the application
        window.set_pump_speed_mA.setText("%.2f" % state.set_pump_speed_mA)
        window.set_pump_speed_pct.setText("%.1f" %
            ((state.set_pump_speed_mA - 4)/16*100))

        window.set_flow_speed_cms.setText("%.2f" %
            (state.setpoint_flow_rate_m3h / state.area_meas_section / 36.0))
        window.set_flow_rate_m3h.setText("%.2f" % state.setpoint_flow_rate_m3h)

        state.starting_up = False

    window.read_flow_rate_m3h.setText("%.2f" % state.read_flow_rate_m3h)
    window.read_flow_rate_mA.setText("%.2f" % state.read_flow_rate_mA)
    window.read_flow_rate_bitV.setText("%i" % state.read_flow_rate_bitV)

    # Transform flow rate [m3/h] to flow speed [cm/s]
    window.read_flow_speed_cms.setText("%.2f" %
        (state.read_flow_rate_m3h / state.area_meas_section / 36.0))

    # Gas volume fraction
    window.read_GVF_P_diff_mbar.setText("%.1f" % state.read_GVF_P_diff_mbar)
    window.read_GVF_P_diff_mA.setText("%.2f" % state.read_GVF_P_diff_mA)
    window.read_GVF_P_diff_bitV.setText("%i" % state.read_GVF_P_diff_bitV)
    window.GVF_pct.setText("%.1f" % state.GVF_pct)

    window.prox_switch_1.setChecked(state.prox_switch_1)
    window.prox_switch_2.setChecked(state.prox_switch_2)
    window.prox_switch_3.setChecked(not(state.prox_switch_3))
    window.prox_switch_4.setChecked(not(state.prox_switch_4))
    window.floater_switch.setChecked(state.floater_switch)

    window.prox_switch_1.setText("%i" % state.prox_switch_1)
    window.prox_switch_2.setText("%i" % state.prox_switch_2)
    window.prox_switch_3.setText("%i" % (not(state.prox_switch_3)))
    window.prox_switch_4.setText("%i" % (not(state.prox_switch_4)))
    window.floater_switch.setText("%i" % (state.floater_switch))

    window.relay_3_1.setChecked(state.relay_3_1)
    window.relay_3_2.setChecked(state.relay_3_2)
    window.relay_3_3.setChecked(state.relay_3_3)
    window.relay_3_4.setChecked(state.relay_3_4)
    window.relay_3_5.setChecked(state.relay_3_5)
    window.relay_3_6.setChecked(state.relay_3_6)
    window.relay_3_7.setChecked(state.relay_3_7)
    window.relay_3_8.setChecked(state.relay_3_8)

    window.relay_3_1.setText("%i" % state.relay_3_1)
    window.relay_3_2.setText("%i" % state.relay_3_2)
    window.relay_3_3.setText("%i" % state.relay_3_3)
    window.relay_3_4.setText("%i" % state.relay_3_4)
    window.relay_3_5.setText("%i" % state.relay_3_5)
    window.relay_3_6.setText("%i" % state.relay_3_6)
    window.relay_3_7.setText("%i" % state.relay_3_7)
    window.relay_3_8.setText("%i" % state.relay_3_8)

    # Heater temperature control
    window.pbtn_ENA_OTP.setChecked(state.ENA_OTP)
    if window.pbtn_ENA_OTP.isChecked():
        window.pbtn_ENA_OTP.setText("Protection enabled")
        window.relay_1_1.setEnabled(False)
        window.relay_1_2.setEnabled(False)
        window.relay_1_3.setEnabled(False)
    else:
        window.pbtn_ENA_OTP.setText("WARNING:\nPROTECTION DISABLED")
        window.relay_1_1.setEnabled(True)
        window.relay_1_2.setEnabled(True)
        window.relay_1_3.setEnabled(True)

    # Redraw the state of the filling system (FS) program buttons
    for iFSM_FS_EXEC in range(8):
        if (iFSM_FS_EXEC == state.FSM_FS_EXEC):
            window.FS_exec_button_list[iFSM_FS_EXEC].setChecked(True)
        else:
            window.FS_exec_button_list[iFSM_FS_EXEC].setChecked(False)

    # Check for filling system messages and display when available
    while len(state.FS_new_msgs) > 0:
        # Insert msg
        cursor = window.FS_text_msgs.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End,
                            QtGui.QTextCursor.MoveAnchor)
        window.FS_text_msgs.setTextCursor(cursor)
        window.FS_text_msgs.insertPlainText(str_cur_time + ' ')
        msg_str = state.FS_new_msgs.pop(0)
        msg_str = msg_str.replace("\r ", "\r " + " " * 9)
        window.FS_text_msgs.insertPlainText(msg_str + '\n')

        # Move focus to the last line
        """
        cursor = window.FS_text_msgs.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End,
                            QtGui.QTextCursor.MoveAnchor)
        window.FS_text_msgs.setTextCursor(cursor)
        """

        while (window.FS_text_msgs.document().lineCount() > 19):
            # Limit the number of lines in the textbox
            cursor = window.FS_text_msgs.textCursor()
            cursor.movePosition(QtGui.QTextCursor.Start,
                                QtGui.QTextCursor.MoveAnchor)
            cursor.movePosition(QtGui.QTextCursor.Down,
                                QtGui.QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
            cursor.movePosition(QtGui.QTextCursor.Start,
                                QtGui.QTextCursor.MoveAnchor)
            window.FS_text_msgs.setTextCursor(cursor)

    # Update stripcharts
    update_charts_Arduinos()

# ------------------------------------------------------------------------------
#   Update chart routines
# ------------------------------------------------------------------------------

@QtCore.pyqtSlot()
def update_charts_Arduinos():
    """Update strip charts that are sourced by the Arduinos
    """
    if DEBUG: tick = QDateTime.currentDateTime()

    # Update curve tunnel flow speed
    # Note that the graph is being fed with [m3/h] and needs to be transformed
    # to [cm/s] depending on the selected measurement section.
    window.CH_flow_speed.y_axis_divisor = state.area_meas_section * 36.0
    window.CH_flow_speed.update_curve()

    # Update set_pump_speed curve
    window.CH_set_pump_speed.update_curve()

    if DEBUG:
        tack = QDateTime.currentDateTime()
        dprint("  update_curve done in %d ms" % tick.msecsTo(tack))

@QtCore.pyqtSlot()
def update_charts():
    """Update strip charts that are not sourced by the Arduinos
    """
    # DAQ rate
    window.CH_DAQ_rate.add_new_reading(state.time,
                                       ards_pyqt.obtained_DAQ_rate_Hz)
    window.CH_DAQ_rate.update_curve()

    # Update curves TC heaters
    [CH.update_curve() for CH in window.CHs_heater_TC]

    # Show or hide curve depending on checkbox
    for i in range(C.N_HEATER_TC):
        window.CHs_heater_TC[i].curve.setVisible(
                window.chkbs_heater_TC[i].isChecked())

    # Updates 'tunnel temperatures' strip chart sourced by the chiller and the
    # PT-104
    window.CH_tunnel_outlet.update_curve()
    window.CH_tunnel_inlet.update_curve()
    window.CH_ambient.update_curve()
    window.CH_chiller_temp.update_curve()
    window.CH_chiller_setpoint.update_curve()

    # Show or hide curve depending on checkbox
    window.CH_tunnel_outlet.curve.setVisible(
            window.chkbs_tunnel_temp[0].isChecked())
    window.CH_tunnel_inlet.curve.setVisible(
            window.chkbs_tunnel_temp[1].isChecked())
    window.CH_ambient.curve.setVisible(
            window.chkbs_tunnel_temp[2].isChecked())
    window.CH_chiller_temp.curve.setVisible(
            window.chkbs_tunnel_temp[3].isChecked())
    window.CH_chiller_setpoint.curve.setVisible(
            window.chkbs_tunnel_temp[4].isChecked())

    # Update 'thermistors' mux2 strip chart
    [CH.update_curve() for CH in window.CHs_mux2]

    # Show or hide curve depending on checkbox
    for i in range(mux2_N_channels):
        window.CHs_mux2[i].curve.setVisible(
                window.chkbs_show_curves_mux2[i].isChecked())

    # Update curves heater power
    if not psus[0].is_alive:
        window.chkb_PSU_1.setChecked(False)
        window.chkb_PSU_1.setEnabled(False)
    if not psus[1].is_alive:
        window.chkb_PSU_2.setChecked(False)
        window.chkb_PSU_2.setEnabled(False)
    if not psus[2].is_alive:
        window.chkb_PSU_3.setChecked(False)
        window.chkb_PSU_3.setEnabled(False)

    # Show or hide curve depending on checkbox
    window.CH_power_PSU_1.curve.setVisible(window.chkb_PSU_1.isChecked() and
                                           psus[0].is_alive)
    window.CH_power_PSU_2.curve.setVisible(window.chkb_PSU_2.isChecked() and
                                           psus[1].is_alive)
    window.CH_power_PSU_3.curve.setVisible(window.chkb_PSU_3.isChecked() and
                                           psus[2].is_alive)

    window.CH_power_PSU_1.update_curve()
    window.CH_power_PSU_2.update_curve()
    window.CH_power_PSU_3.update_curve()

def _(): pass # Spyder IDE outline divider
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

    window.pi_tunnel_temp.setXRange(time_axis_range, 0)
    window.pi_tunnel_temp.setLabel('bottom', time_axis_label)

    window.vb_set_pump_speed.setXRange(time_axis_range, 0)
    window.pi_flow_speed.setXRange(time_axis_range, 0)
    window.pi_flow_speed.setLabel('bottom', time_axis_label)

    window.pi_mux2.setXRange(time_axis_range, 0)
    window.pi_mux2.setLabel('bottom', time_axis_label)

    window.pi_heater_power.setXRange(time_axis_range, 0)
    window.pi_heater_power.setLabel('bottom', time_axis_label)

    window.pi_DAQ_rate.setXRange(time_axis_range, 0)
    window.pi_DAQ_rate.setLabel('bottom', time_axis_label)

    for CH in window.CHs_heater_TC:
        CH.x_axis_divisor = time_axis_factor
    window.CH_flow_speed.x_axis_divisor       = time_axis_factor
    window.CH_set_pump_speed.x_axis_divisor   = time_axis_factor
    window.CH_tunnel_outlet.x_axis_divisor    = time_axis_factor
    window.CH_tunnel_inlet.x_axis_divisor     = time_axis_factor
    window.CH_ambient.x_axis_divisor          = time_axis_factor
    window.CH_chiller_temp.x_axis_divisor     = time_axis_factor
    window.CH_chiller_setpoint.x_axis_divisor = time_axis_factor

    for i in range(mux2_N_channels):
        window.CHs_mux2[i].x_axis_divisor = time_axis_factor

    window.CH_power_PSU_1.x_axis_divisor      = time_axis_factor
    window.CH_power_PSU_2.x_axis_divisor      = time_axis_factor
    window.CH_power_PSU_3.x_axis_divisor      = time_axis_factor
    window.CH_DAQ_rate.x_axis_divisor         = time_axis_factor

def _(): pass # Spyder IDE outline divider
# ------------------------------------------------------------------------------
#   Arduino control: relays
# ------------------------------------------------------------------------------

def bool2on(bool_val):
    return "on" if bool_val else "off"

@QtCore.pyqtSlot()
def actuate_relay_1_1_from_button():
    ards_pyqt.send(ard1, "r1 " + bool2on(window.relay_1_1.isChecked()))

@QtCore.pyqtSlot()
def actuate_relay_1_2_from_button():
    ards_pyqt.send(ard1, "r2 " + bool2on(window.relay_1_2.isChecked()))

@QtCore.pyqtSlot()
def actuate_relay_1_3_from_button():
    ards_pyqt.send(ard1, "r3 " + bool2on(window.relay_1_3.isChecked()))

@QtCore.pyqtSlot()
def actuate_relay_1_4_from_button():
    if mfc.state.flow_rate > 0:
        ards_pyqt.send(ard1, "r4 " + bool2on(window.relay_1_4.isChecked()))

@QtCore.pyqtSlot()
def actuate_relay_1_5_from_button():
    if mfc.state.flow_rate > 0:
        ards_pyqt.send(ard1, "r5 " + bool2on(window.relay_1_5.isChecked()))

@QtCore.pyqtSlot()
def actuate_relay_1_6_from_button():
    if mfc.state.flow_rate > 0:
        ards_pyqt.send(ard1, "r6 " + bool2on(window.relay_1_6.isChecked()))

@QtCore.pyqtSlot()
def actuate_relay_1_7_from_button():
    if mfc.state.flow_rate > 0:
        ards_pyqt.send(ard1, "r7 " + bool2on(window.relay_1_7.isChecked()))

@QtCore.pyqtSlot()
def actuate_relay_1_8_from_button():
    if mfc.state.flow_rate > 0:
        ards_pyqt.send(ard1, "r8 " + bool2on(window.relay_1_8.isChecked()))

@QtCore.pyqtSlot()
def actuate_relay_2_8_from_button():
    ards_pyqt.send(ard1, "r9 " + bool2on(window.enable_pump.isChecked()))

@QtCore.pyqtSlot()
def actuate_relay_3_1_from_button():
    ards_pyqt.send(ard2, "r1 " + bool2on(window.relay_3_1.isChecked()))

@QtCore.pyqtSlot()
def actuate_relay_3_2_from_button():
    ards_pyqt.send(ard2, "r2 " + bool2on(window.relay_3_2.isChecked()))

@QtCore.pyqtSlot()
def actuate_relay_3_3_from_button():
    ards_pyqt.send(ard2, "r3 " + bool2on(window.relay_3_3.isChecked()))

@QtCore.pyqtSlot()
def actuate_relay_3_4_from_button():
    ards_pyqt.send(ard2, "r4 " + bool2on(window.relay_3_4.isChecked()))

@QtCore.pyqtSlot()
def actuate_relay_3_5_from_button():
    ards_pyqt.send(ard2, "r5 " + bool2on(window.relay_3_5.isChecked()))

@QtCore.pyqtSlot()
def actuate_relay_3_6_from_button():
    ards_pyqt.send(ard2, "r6 " + bool2on(window.relay_3_6.isChecked()))

@QtCore.pyqtSlot()
def actuate_relay_3_7_from_button():
    ards_pyqt.send(ard2, "r7 " + bool2on(window.relay_3_7.isChecked()))

@QtCore.pyqtSlot()
def actuate_relay_3_8_from_button():
    ards_pyqt.send(ard2, "r8 " + bool2on(window.relay_3_8.isChecked()))

@QtCore.pyqtSlot()
def open_all_bubblers():
    #dprint("@ open_all_bubblers")      # DEBUG info
    ards_pyqt.send(ard1, "r4 on")
    ards_pyqt.send(ard1, "r5 on")
    ards_pyqt.send(ard1, "r6 on")
    ards_pyqt.send(ard1, "r7 on")
    ards_pyqt.send(ard1, "r8 on")

@QtCore.pyqtSlot()
def close_all_bubblers():
    #dprint("@ close_all_bubblers")     # DEBUG info
    ards_pyqt.send(ard1, "r4 off")
    ards_pyqt.send(ard1, "r5 off")
    ards_pyqt.send(ard1, "r6 off")
    ards_pyqt.send(ard1, "r7 off")
    ards_pyqt.send(ard1, "r8 off")

# ------------------------------------------------------------------------------
#   Arduino control: filling system
# ------------------------------------------------------------------------------

@QtCore.pyqtSlot()
def exec_FS_idle():
    ards_pyqt.send(ard2, "exec_FS_idle")

@QtCore.pyqtSlot()
def exec_FS_barrel_1_to_tunnel():
    ards_pyqt.send(ard2, "exec_FS_barrel_1_to_tunnel")

@QtCore.pyqtSlot()
def exec_FS_barrel_2_to_tunnel():
    ards_pyqt.send(ard2, "exec_FS_barrel_2_to_tunnel")

@QtCore.pyqtSlot()
def exec_FS_tunnel_to_barrel_1():
    ards_pyqt.send(ard2, "exec_FS_tunnel_to_barrel_1")

@QtCore.pyqtSlot()
def exec_FS_tunnel_to_barrel_2():
    ards_pyqt.send(ard2, "exec_FS_tunnel_to_barrel_2")

@QtCore.pyqtSlot()
def exec_FS_barrel_1_to_sewer():
    ards_pyqt.send(ard2, "exec_FS_barrel_1_to_sewer")

@QtCore.pyqtSlot()
def exec_FS_barrel_2_to_sewer():
    ards_pyqt.send(ard2, "exec_FS_barrel_2_to_sewer")

@QtCore.pyqtSlot()
def exec_FS_tunnel_to_sewer():
    ards_pyqt.send(ard2, "exec_FS_tunnel_to_sewer")

# ------------------------------------------------------------------------------
#   Arduino control: 4-20 mA current loops
# ------------------------------------------------------------------------------

@QtCore.pyqtSlot()
def set_pump_speed_from_pct_textbox():
    try:
        pct_value = float(window.set_pump_speed_pct.text())
    except ValueError:
        pct_value = 0.0

    pct_value = np.clip(pct_value, 0, 100)
    mA_value  = pct_value/100*16 + 4
    window.set_pump_speed_pct.setText("%.1f" % pct_value)
    window.set_pump_speed_mA.setText("%.2f" % mA_value)
    ards_pyqt.send(ard1, "sps%.2f" % mA_value)

    # Automatically set ENA_TUNNEL_PUMP to False when 0 has been entered
    # EDIT: don't. This will immediately switch off the pump without slow wind
    # down. Think of a better approach to auto switch off the pump.
    #if pct_value == 0:
    #    ards_pyqt.send(ard1, "r9 off")

@QtCore.pyqtSlot()
def set_pump_speed_from_mA_textbox():
    try:
        mA_value = float(window.set_pump_speed_mA.text())
    except ValueError:
        mA_value = 4.0

    mA_value  = np.clip(mA_value, 4, 20)
    pct_value = (mA_value - 4)/16*100
    window.set_pump_speed_pct.setText("%.1f" % pct_value)
    window.set_pump_speed_mA.setText("%.2f" % mA_value)
    ards_pyqt.send(ard1, "sps%.2f" % mA_value)

    # Automatically set ENA_TUNNEL_PUMP to False when 0 has been entered
    #if pct_value == 0:
    #    ards_pyqt.send(ard1, "r9 off")

# ------------------------------------------------------------------------------
#   Tunnel flow rate PID control
# ------------------------------------------------------------------------------

@QtCore.pyqtSlot()
def process_pbtn_enable_pump_PID():
    ards_pyqt.send(ard1, "ena_pfr " +
                   bool2on(window.enable_pump_PID.isChecked()))

@QtCore.pyqtSlot()
def process_rbtn_MS():
    if window.rbtn_MS1.isChecked():
        meas_section_number = 1
        state.area_meas_section = C.AMS_1
    elif window.rbtn_MS2.isChecked():
        meas_section_number = 2
        state.area_meas_section = C.AMS_2
    elif window.rbtn_MS3.isChecked():
        meas_section_number = 3
        state.area_meas_section = C.AMS_3

    # Write selected measurement section number to config file on disk
    if not C.PATH_CONFIG_MEAS_SECTION.parent.is_dir():
        # Subfolder does not exists yet. Create.
        try:
            C.PATH_CONFIG_MEAS_SECTION.parent.mkdir()
        except:
            pass    # Do not panic and remain silent

    try:
        # Write the config file
        C.PATH_CONFIG_MEAS_SECTION.write_text("%i" % meas_section_number)
    except:
        pass        # Do not panic and remain silent

@QtCore.pyqtSlot()
def set_tunnel_flow_speed_cms_from_textbox():
    try:
        value_cms = float(window.set_flow_speed_cms.text())
    except ValueError:
        value_cms = 0.0

    # Transform flow speed [cm/s] to flow rate [m3/h]
    value_cms = max(value_cms, 0)
    value_m3h = value_cms * state.area_meas_section * 36.0

    window.set_flow_speed_cms.setText("%.2f" % value_cms)
    window.set_flow_rate_m3h.setText("%.2f" % value_m3h)
    ards_pyqt.send(ard1, "sfr%.3f" % value_m3h)

# ------------------------------------------------------------------------------
#   Heater temperature control
# ------------------------------------------------------------------------------

@QtCore.pyqtSlot()
def process_pbtn_ENA_OTP():
    ards_pyqt.send(ard1, "ena_otp " + bool2on(window.pbtn_ENA_OTP.isChecked()))

# ------------------------------------------------------------------------------
#   Gas volume fraction (GVF)
# ------------------------------------------------------------------------------

@QtCore.pyqtSlot()
def process_GVF_density_liquid():
    try:
        GVF_density_liquid = float(window.GVF_density_liquid.text())
    except:
        GVF_density_liquid = np.nan
    if (GVF_density_liquid == 0):
        GVF_density_liquid = np.nan

    state.GVF_density_liquid = GVF_density_liquid

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

@QtCore.pyqtSlot()
def process_pbtn_record_to_file():
    global fn_log, fn_log_mux2
    fn_log = ("d:/data/" + cur_date_time.toString("yyMMdd_HHmmss") + ".txt")
    fn_log_mux2 = ("d:/data/" + cur_date_time.toString("yyMMdd_HHmmss") + ".mux2")

    if window.pbtn_record.isChecked():
        file_logger.starting = True
        file_logger_mux2.starting = True
    else:
        file_logger.stopping = True
        file_logger_mux2.stopping = True

def _(): pass # Spyder IDE outline divider
# ------------------------------------------------------------------------------
#   soft_reset
# ------------------------------------------------------------------------------

@QtCore.pyqtSlot()
def soft_reset():
    # Reset Arduinos to safe initial state
    app.processEvents()
    ards_pyqt.send(ard1, "soft_reset")
    ards_pyqt.send(ard2, "soft_reset")
    app.processEvents()

    # Reset GUI elements
    window.set_pump_speed_pct.setText("0.0")
    window.set_pump_speed_mA.setText("4.00")
    window.set_flow_speed_cms.setText("0.00")
    window.set_flow_rate_m3h.setText("0.00")
    window.relay_3_MC.setChecked(False)
    window.relay_3_manual_control()

    # --------------------------------------------------------------------------
    #   Turn off peripheral devices immediately. This means that we communicate
    #   with these devices from within this main thread, instead of putting it
    #   on the message queues of their 'send' workers.
    # --------------------------------------------------------------------------

    # Bronkhorst mass flow controller
    mfc_pyqt.qled_send_setpoint.setText("0.00")
    # Work-around to prevent resending previous setpoint when focus was on
    # textbox prior to clicking on 'soft reset'
    mfc_pyqt.send_setpoint_from_textbox()
    if mfc.is_alive:
        locker = QtCore.QMutexLocker(mfc.mutex)
        mfc.send_setpoint(0)
        locker.unlock()

    # Keysight power supplies
    for psu in psus:
        if psu.is_alive:
            locker = QtCore.QMutexLocker(mfc.mutex)
            psu.turn_off()
            locker.unlock()

    # ThermoFlex chiller
    if chiller.is_alive:
        locker = QtCore.QMutexLocker(chiller.mutex)
        chiller.turn_off()
        locker.unlock()

    # Compax3 traverses
    for trav in travs:
        locker = QtCore.QMutexLocker(trav.mutex)
        trav.stop_motion_and_remove_power()
        locker.unlock()

# ------------------------------------------------------------------------------
#   Program termination routines
# ------------------------------------------------------------------------------

def stop_running():
    """Stop Arduino communication and logging
    """
    app.processEvents()
    ards_pyqt.close_all_threads()
    file_logger.close_log()
    file_logger_mux2.close_log()

@QtCore.pyqtSlot()
def notify_connection_lost():
    stop_running()
    timer_charts.stop()

    window.lbl_title.setText("    " + "! " * 8 + "   CONNECTION LOST   " +
                             " !" * 8 + "    ")

    # Notify user
    str_msg = (str_cur_date + " " + str_cur_time + "\n" +
        "Connection to Arduino(s) has been lost." +
        "\n   Arduino_#1 was alive: " + str(ard1.is_alive) +
        "\n   Arduino_#2 was alive: " + str(ard2.is_alive) +
        "\n\nExiting...")
    print("\nCRITICAL ERROR: " + str_msg)
    reply = QtGui.QMessageBox.warning(window, "CRITICAL ERROR", str_msg,
                                      QtGui.QMessageBox.Ok)

    if reply == QtGui.QMessageBox.Ok:
        # Leave the GUI open for read-only inspection by the user
        pass

@QtCore.pyqtSlot()
def about_to_quit():
    print("About to quit")
    stop_running()

    print("Stopping timers.................", end='')
    timer_charts.stop()
    timer_psus.stop()
    print("done.")

    # -----------------------------------
    #   Close peripheral device threads
    # -----------------------------------

    chiller_pyqt.close_all_threads()    # ThermoFlex chiller
    mfc_pyqt.close_all_threads()        # Bronkhorst mass flow controller
    mux1_pyqt.close_all_threads()       # Keysight 3497xA
    mux2_pyqt.close_all_threads()       # Keysight 3497xA
    pt104_pyqt.close_all_threads()      # Picotech PT-104

    # Keysight power supplies
    for psu_pyqt in psus_pyqt:
        psu_pyqt.close_all_threads()

    # Compax3 traverses
    travs_are_powerless = True
    for trav in travs:
        if trav.is_alive:
            travs_are_powerless &= trav.status_word_1.powerless

    if not travs_are_powerless:
        str_msg = ("The traverse is still powered.\n\n"
                   "Remove power to save energy?")
        reply = QtWid.QMessageBox.question(None,
                "Save energy", str_msg,
                QtWid.QMessageBox.Yes | QtWid.QMessageBox.No,
                QtWid.QMessageBox.No)

        if reply == QtWid.QMessageBox.Yes:
            for trav in travs:
                if trav.is_alive:
                    locker = QtCore.QMutexLocker(trav.mutex)
                    trav.stop_motion_and_remove_power()
                    locker.unlock()

    for trav_pyqt in travs_pyqt:
        trav_pyqt.close_all_threads()

    # ---------------------------------------
    #   Close connections
    # ---------------------------------------

    try: ard1.close()
    except: pass
    try: ard2.close()
    except: pass
    try: chiller.close()
    except: pass
    try: mfc.close()
    except: pass
    try: mux1.close()
    except: pass
    try: mux2.close()
    except: pass
    try: pt104.close()
    except: pass
    for psu in psus:
        try: psu.close()
        except: pass
    for trav in travs:
        try: trav.close()
        except: pass
    try: rm.close()
    except: pass
    print("")

def _(): pass # Spyder IDE outline divider

# ------------------------------------------------------------------------------
#   Bronkhorst mass flow conroller routines
# ------------------------------------------------------------------------------

@QtCore.pyqtSlot()
def process_mfc_auto_open_valve():
    if DEBUG: dprint("process_mfc_auto_open_valve")

    # Automatically open all bubblers when none are open
    locker_state = QtCore.QMutexLocker(state.mutex)
    all_bubblers_closed = ((not state.relay_1_4) and
                           (not state.relay_1_5) and
                           (not state.relay_1_6) and
                           (not state.relay_1_7) and
                           (not state.relay_1_8))
    locker_state.unlock()
    if all_bubblers_closed:
        open_all_bubblers()

# ------------------------------------------------------------------------------
#   Keysight power supply routines
# ------------------------------------------------------------------------------

@QtCore.pyqtSlot()
def trigger_update_psus():
    # Trigger new PSU readings by waking up the 'DAQ' threads
    if DEBUG: dprint("timer_psus: wake all PSU DAQ")
    for psu_pyqt in psus_pyqt:
        psu_pyqt.worker_DAQ.wake_up()

# ------------------------------------------------------------------------------
#   Keysight N8700 routines
# ------------------------------------------------------------------------------

@QtCore.pyqtSlot()
def update_GUI_heater_control_extras():
    # Add readings to charts
    elapsed_time = QDateTime.currentDateTime().toMSecsSinceEpoch()
    if psus[0].is_alive:
        window.CH_power_PSU_1.add_new_reading(elapsed_time,
                                              psus[0].state.P_meas)
    if psus[1].is_alive:
        window.CH_power_PSU_2.add_new_reading(elapsed_time,
                                              psus[1].state.P_meas)
    if psus[2].is_alive:
        window.CH_power_PSU_3.add_new_reading(elapsed_time,
                                              psus[2].state.P_meas)

# ------------------------------------------------------------------------------
#   Keysight 3497xA routines
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
#   Mux 1 over-temperature (OTP) check routine
#   NOTE: no GUI changes are allowed in this function.
# ------------------------------------------------------------------------------

def DAQ_postprocess_MUX1_scan_function():
    # DEBUG info
    #dprint("thread: %s" % QtCore.QThread.currentThread().objectName())

    if len(mux1.state.readings) == 0:
        return

    all_temps_okay = True
    if mux1_pyqt.is_MUX_scanning:
        readings = mux1.state.readings

        for i in range(C.N_HEATER_TC):
            if i >= len(readings):
                # Regardless of the scan list in the mux, always make
                # sure readings contains 12 fields.
                readings.append(np.nan)

            if readings[i] > 9.8e37:
                readings[i] = np.nan

            # Temperature okay (in range) check
            if (i == 10 or i == 11):
                # Thermocouples are broken and heaters are not connected.
                # Hence, ignore these thermocouples from the OTP check
                continue

            if ((readings[i] > C.OTP_MAX_TEMP_DEGC) or
                (readings[i] == np.nan)):
                all_temps_okay = False

        if all_temps_okay:
            ards_pyqt.send(ard1, "otp_okay")
        else:
            ards_pyqt.send(ard1, "otp_trip")
    else:
        # Multiplexer is not scanning. No readings available
        readings = [np.nan] * 12

    [state.heater_TC_01_degC,
     state.heater_TC_02_degC,
     state.heater_TC_03_degC,
     state.heater_TC_04_degC,
     state.heater_TC_05_degC,
     state.heater_TC_06_degC,
     state.heater_TC_07_degC,
     state.heater_TC_08_degC,
     state.heater_TC_09_degC,
     state.heater_TC_10_degC,
     state.heater_TC_11_degC,
     state.heater_TC_12_degC] = readings

    # Add readings to charts
    elapsed_time = QDateTime.currentDateTime().toMSecsSinceEpoch()
    for i in range(C.N_HEATER_TC):
        window.CHs_heater_TC[i].add_new_reading(elapsed_time, readings[i])

def DAQ_postprocess_MUX2_scan_function():

    if mux2_pyqt.is_MUX_scanning:
        readings = mux2.state.readings
        for i in range(mux2_N_channels):
            if readings[i] > K3497xA_pyqt_lib.INFINITY_CAP:
                readings[i] = np.nan
    else:
        readings = [np.nan] * mux2_N_channels
        mux2.state.readings = readings

    # Add readings to charts
    elapsed_time = QDateTime.currentDateTime().toMSecsSinceEpoch()
    for i in range(mux2_N_channels):
        window.CHs_mux2[i].add_new_reading(elapsed_time, readings[i])

    # ----------------------------------------------------------------------
    #   Logging to file
    # ----------------------------------------------------------------------

    if file_logger_mux2.starting:
        if file_logger_mux2.create_log(elapsed_time, fn_log_mux2, mode='w'):
            # Header
            file_logger_mux2.write("[s]\t")
            for i in range(mux2_N_channels - 1):
                file_logger_mux2.write("[ohm]\t")
            file_logger_mux2.write("[ohm]\n")
            file_logger_mux2.write("time\t")
            for i in range(mux2_N_channels - 1):
                file_logger_mux2.write("CH%s\t" %
                                       mux2.state.all_scan_list_channels[i])
            file_logger_mux2.write("CH%s\n" %
                                   mux2.state.all_scan_list_channels[-1])

    if file_logger_mux2.stopping:
        file_logger_mux2.close_log()

    if file_logger_mux2.is_recording:
        log_elapsed_time = (elapsed_time - file_logger_mux2.start_time)/1e3  # [sec]

        # Add new data to the log
        file_logger_mux2.write("%.3f" % log_elapsed_time)
        for i in range(mux2_N_channels):
            if len(mux2.state.readings) <= i:
                file_logger_mux2.write("\t%.5e" % np.nan)
            else:
                file_logger_mux2.write("\t%.5e" % mux2.state.readings[i])
        file_logger_mux2.write("\n")

# ------------------------------------------------------------------------------
#   Picotech PT104 routines
# ------------------------------------------------------------------------------

@QtCore.pyqtSlot()
def update_GUI_PT104():
    # Add readings to charts
    elapsed_time = QDateTime.currentDateTime().toMSecsSinceEpoch()
    window.CH_tunnel_inlet.add_new_reading(elapsed_time, pt104.state.ch1_T)
    window.CH_tunnel_outlet.add_new_reading(elapsed_time, pt104.state.ch2_T)
    window.CH_ambient.add_new_reading(elapsed_time, pt104.state.ch3_T)

    # GUI
    window.tunnel_inlet_temp.setText("%.3f" % pt104.state.ch1_T)
    window.tunnel_outlet_temp.setText("%.3f" % pt104.state.ch2_T)
    window.ambient_temp.setText("%.3f" % pt104.state.ch3_T)
    if not pt104.is_alive:
        window.pt104_offline.setVisible(True)

# ------------------------------------------------------------------------------
#   ThermoFlex chiller routines
# ------------------------------------------------------------------------------

@QtCore.pyqtSlot()
def update_GUI_chiller_extras():
    # Add readings to charts
    elapsed_time = QDateTime.currentDateTime().toMSecsSinceEpoch()
    window.CH_chiller_setpoint.add_new_reading(elapsed_time,
                                               chiller.state.setpoint)
    window.CH_chiller_temp.add_new_reading(elapsed_time,
                                           chiller.state.temp)

    # GUI
    window.chiller_read_setpoint.setText("%.1f" % chiller.state.setpoint)
    window.chiller_read_temp.setText("%.1f" % chiller.state.temp)

# ------------------------------------------------------------------------------
#   Compax3 traverse routines
# ------------------------------------------------------------------------------

@QtCore.pyqtSlot()
def act_upon_signal_step_up(new_pos: float):
    trav_vert_pyqt.qled_new_pos.setText("%.2f" % new_pos)
    trav_vert_pyqt.process_pbtn_move_to_new_pos()

@QtCore.pyqtSlot()
def act_upon_signal_step_down(new_pos: float):
    trav_vert_pyqt.qled_new_pos.setText("%.2f" % new_pos)
    trav_vert_pyqt.process_pbtn_move_to_new_pos()

@QtCore.pyqtSlot()
def act_upon_signal_step_left(new_pos: float):
    trav_horz_pyqt.qled_new_pos.setText("%.2f" % new_pos)
    trav_horz_pyqt.process_pbtn_move_to_new_pos()

@QtCore.pyqtSlot()
def act_upon_signal_step_right(new_pos: float):
    trav_horz_pyqt.qled_new_pos.setText("%.2f" % new_pos)
    trav_horz_pyqt.process_pbtn_move_to_new_pos()

# ------------------------------------------------------------------------------
#   Debug / tests
# ------------------------------------------------------------------------------

def fill_TC_chart_with_random_data():
    #last_time_stamp = self.CHs_heater_TC[0]._time[-1]
    last_time_stamp = QDateTime.currentDateTime().toMSecsSinceEpoch()

    for i in range(C.N_HEATER_TC):
        window.CHs_heater_TC[i].clear()
        time_ms = (last_time_stamp -
                   np.arange(C.CH_SAMPLES_HEATER_TC, -1, -1) *
                   C.MUX_1_SCANNING_INTERVAL)
        window.CHs_heater_TC[i].add_new_readings(
                time_ms,
                20.0 + np.sin(2*np.pi/230000*(time_ms - i*1e4)))

def _(): pass # Spyder IDE outline divider
# ------------------------------------------------------------------------------
#   Main
# ------------------------------------------------------------------------------

if __name__ == '__main__':
    # Set priority of this process to maximum in the operating system
    print("PID: %s\n" % os.getpid())
    try:
        proc = psutil.Process(os.getpid())
        if os.name == "nt": proc.nice(psutil.REALTIME_PRIORITY_CLASS) # Windows
        else: proc.nice(-20)                                          # Other
    except:
        print("Warning: Could not set process to maximum priority.\n")

    # --------------------------------------------------------------------------
    #   Create application
    # --------------------------------------------------------------------------
    QtCore.QThread.currentThread().setObjectName('MAIN')    # For DEBUG info

    app = 0    # Work-around for kernel crash when using Spyder IDE
    app = QtGui.QApplication(sys.argv)
    app.setFont(MHT_tunnel_GUI.FONT_DEFAULT)
    app.aboutToQuit.connect(about_to_quit)

    # --------------------------------------------------------------------------
    #   Connect to Arduinos
    # --------------------------------------------------------------------------

    ard1 = Arduino_functions.Arduino(name="Ard 1", baudrate=115200)
    ard1.auto_connect(path_config=C.PATH_CONFIG_ARD1,
                      match_identity="Arduino_#1")

    if not ard1.is_alive:
        print("Check connection and try resetting the Arduino.")
        print("Exiting...\n")
        sys.exit(0)

    ard2 = Arduino_functions.Arduino(name="Ard 2", baudrate=115200)
    ard2.auto_connect(path_config=C.PATH_CONFIG_ARD2,
                      match_identity="Arduino_#2")

    if not ard2.is_alive:
        print("Check connection and try resetting the Arduino.")
        print("Exiting...\n")
        sys.exit(0)

    ards_pyqt = Arduino_pyqt_lib.Arduino_pyqt(ard1,
                                              ard2,
                                              C.UPDATE_INTERVAL_ARDUINOS,
                                              my_Arduino_DAQ_update)
    ards_pyqt.signal_DAQ_updated.connect(update_GUI)
    ards_pyqt.signal_connection_lost.connect(notify_connection_lost)

    # --------------------------------------------------------------------------
    #   Connect to peripheral devices
    # --------------------------------------------------------------------------

    rm = visa.ResourceManager()    # Open VISA resource manager

    # -----------------------------------
    #   ThermoFlex chiller
    # -----------------------------------

    chiller = chiller_functions.ThermoFlex_chiller(
                                    min_setpoint_degC=C.CHILLER_MIN_TEMP_DEG_C,
                                    max_setpoint_degC=C.CHILLER_MAX_TEMP_DEG_C,
                                    name="chiller")
    if chiller.auto_connect(path_config=C.PATH_CONFIG_CHILLER):
        chiller.begin()

    chiller_pyqt = (
            chiller_pyqt_lib.ThermoFlex_chiller_pyqt(chiller,
                                                     C.UPDATE_INTERVAL_CHILLER))
    chiller_pyqt.signal_DAQ_updated.connect(update_GUI_chiller_extras)

    # -----------------------------------
    #   Bronkhorst mass flow controller
    # -----------------------------------

    mfc = mfc_functions.Bronkhorst_MFC(name="MFC")
    if mfc.auto_connect(path_config=C.PATH_CONFIG_MFC_1,
                        match_serial_str=C.SERIAL_MFC_1):
        mfc.begin()

    mfc_pyqt = mfc_pyqt_lib.Bronkhorst_MFC_pyqt(mfc, C.UPDATE_INTERVAL_MFC)
    mfc_pyqt.signal_valve_auto_open.connect(process_mfc_auto_open_valve)
    mfc_pyqt.signal_valve_auto_close.connect(close_all_bubblers)

    # -----------------------------------
    #   Keysight power supplies
    # -----------------------------------

    psu1 = N8700_functions.PSU(visa_address=C.VISA_ADDRESS_PSU_1,
                               path_config=C.PATH_CONFIG_PSU_1,
                               name="PSU 1")
    psu2 = N8700_functions.PSU(visa_address=C.VISA_ADDRESS_PSU_2,
                               path_config=C.PATH_CONFIG_PSU_2,
                               name="PSU 2")
    psu3 = N8700_functions.PSU(visa_address=C.VISA_ADDRESS_PSU_3,
                               path_config=C.PATH_CONFIG_PSU_3,
                               name="PSU 3")
    psus = [psu1, psu2, psu3]

    for psu in psus:
        if psu.connect(rm):
            psu.read_config_file()
            psu.begin()

    psus_pyqt = list()
    for i in range(len(psus)):
        psus_pyqt.append(N8700_pyqt_lib.PSU_pyqt(
                dev=psus[i],
                DAQ_critical_not_alive_count=np.nan,
                DAQ_trigger_by=DAQ_trigger.EXTERNAL_WAKE_UP_CALL))

    # DEBUG information
    DEBUG_PSU = False
    psus_pyqt[0].worker_DAQ.DEBUG  = DEBUG_PSU
    psus_pyqt[0].worker_send.DEBUG = DEBUG_PSU
    psus_pyqt[0].worker_DAQ.DEBUG_color  = ANSI.YELLOW
    psus_pyqt[0].worker_send.DEBUG_color = ANSI.CYAN

    psus_pyqt[1].worker_DAQ.DEBUG  = DEBUG_PSU
    psus_pyqt[1].worker_send.DEBUG = DEBUG_PSU
    psus_pyqt[1].worker_DAQ.DEBUG_color  = ANSI.GREEN
    psus_pyqt[1].worker_send.DEBUG_color = ANSI.RED

    # -----------------------------------
    #   Compax3 traverse controllers
    # -----------------------------------

    trav_horz = compax3_functions.Compax3_traverse(name="TRAV HORZ")
    trav_vert = compax3_functions.Compax3_traverse(name="TRAV VERT")
    travs = [trav_horz, trav_vert]

    if trav_horz.auto_connect(path_config=C.PATH_CONFIG_TRAV_HORZ,
                              match_serial_str=C.SERIAL_TRAV_HORZ):
        trav_horz.begin()
        # Set default motion profile (= #2) parameters
        trav_horz.store_motion_profile(target_position=0,
                                       velocity=10,
                                       mode=1,
                                       accel=100,
                                       decel=100,
                                       jerk=1e6,
                                       profile_number=2)

    if trav_vert.auto_connect(path_config=C.PATH_CONFIG_TRAV_VERT,
                              match_serial_str=C.SERIAL_TRAV_VERT):
        trav_vert.begin()
        # Set default motion profile (= #2) parameters
        trav_vert.store_motion_profile(target_position=0,
                                       velocity=10,
                                       mode=1,
                                       accel=100,
                                       decel=100,
                                       jerk=1e6,
                                       profile_number=2)

    trav_horz_pyqt = (
            compax3_pyqt_lib.Compax3_traverse_pyqt(trav_horz,
                                                   C.UPDATE_INTERVAL_TRAVs))
    trav_vert_pyqt = (
            compax3_pyqt_lib.Compax3_traverse_pyqt(trav_vert,
                                                   C.UPDATE_INTERVAL_TRAVs))
    travs_pyqt = [trav_horz_pyqt, trav_vert_pyqt]

    # Create Compax3 single step navigator
    trav_step_nav = step_nav_pyqt_lib.Compax3_step_navigator(
                        trav_horz=trav_horz, trav_vert=trav_vert)
    trav_step_nav.step_up.connect(act_upon_signal_step_up)
    trav_step_nav.step_down.connect(act_upon_signal_step_down)
    trav_step_nav.step_left.connect(act_upon_signal_step_left)
    trav_step_nav.step_right.connect(act_upon_signal_step_right)

    # -----------------------------------
    #   Picotech PT-104
    # -----------------------------------
    # NOTE: There is only a 15 s time window where the PT-104 expects a new
    # 'keep alive' signal. The next 'keep alive' will be send when the
    # worker_DAQ thread is started.

    pt104 = pt104_functions.PT104(name="PT104")
    if pt104.connect(C.PT104_IP_ADDRESS, C.PT104_PORT):
        pt104.begin()
        pt104.start_conversion(C.PT104_ENA_CHANNELS, C.PT104_GAIN_CHANNELS)

    pt104_pyqt = pt104_pyqt_lib.PT104_pyqt(pt104, C.UPDATE_INTERVAL_PT104)
    pt104_pyqt.signal_DAQ_updated.connect(update_GUI_PT104)

    # -----------------------------------
    #   Keysight 3497xA multiplexers
    # -----------------------------------

    mux1 = K3497xA_functions.K3497xA(C.MUX_1_VISA_ADDRESS, name="MUX 1")
    if mux1.connect(rm):
        mux1.begin(C.MUX_1_SCPI_COMMANDS)

    mux1_pyqt = K3497xA_pyqt_lib.K3497xA_pyqt(
                    dev=mux1,
                    DAQ_update_interval_ms=C.MUX_1_SCANNING_INTERVAL,
                    DAQ_postprocess_MUX_scan_function=
                    DAQ_postprocess_MUX1_scan_function)

    mux2 = K3497xA_functions.K3497xA(C.MUX_2_VISA_ADDRESS, name="MUX 2")
    if mux2.connect(rm):
        mux2.begin(C.MUX_2_SCPI_COMMANDS)

    mux2_pyqt = K3497xA_pyqt_lib.K3497xA_pyqt(
                    dev=mux2,
                    DAQ_update_interval_ms=C.MUX_2_SCANNING_INTERVAL,
                    DAQ_postprocess_MUX_scan_function=
                    DAQ_postprocess_MUX2_scan_function)

    # --------------------------------------------------------------------------
    #   Create main window
    # --------------------------------------------------------------------------

    window = MHT_tunnel_GUI.MainWindow()

    # -----------------------
    #   Tab: Main
    # -----------------------

    mfc_pyqt.qgrp.setTitle('')
    mfc_pyqt.qgrp.setFlat(True)
    mfc_pyqt.grid.setContentsMargins(0, 0, 0, 0)
    mfc_pyqt.qlbl_update_counter.setVisible(False)
    window.grid_bubbles.addWidget(mfc_pyqt.qgrp, 0, 0, 1, 3)

    # -----------------------
    #   Tab: Chiller
    # -----------------------

    window.tab_chiller.setLayout(chiller_pyqt.hbly_GUI)

    # -----------------------
    #   Tab: Heater control
    # -----------------------

    hbox1 = QtWid.QHBoxLayout()
    hbox2 = QtWid.QHBoxLayout()

    # Keysight power supplies
    for psu_pyqt in psus_pyqt:
        hbox1.addWidget(psu_pyqt.grpb, stretch=0, alignment=QtCore.Qt.AlignTop)
        if psu_pyqt.dev.is_alive:
            # Enable power PID controller by default
            psu_pyqt.pbtn_ENA_PID.setChecked(True)
            psu_pyqt.process_pbtn_ENA_PID()

    # Keysight 3497xA
    mux1_pyqt.qgrp.setTitle(mux1_pyqt.dev.name + ": Heater temperatures")
    mux1_pyqt.qtbl_readings.setFixedWidth(150)
    mux1_pyqt.qtbl_readings.setColumnWidth(0, 90)
    mux1_pyqt.set_table_readings_format("%.2f")
    hbox1.addWidget(mux1_pyqt.qgrp, stretch=1, alignment=QtCore.Qt.AlignTop)

    # Over-temperature protection
    hbox1.addWidget(window.grpb_OTP, stretch=0, alignment=QtCore.Qt.AlignTop)
    hbox1.addStretch(1)
    hbox1.setAlignment(QtCore.Qt.AlignTop)

    # Show PSU curves
    hbox2.addWidget(window.grpb_show_PSU, stretch=0,
                    alignment=QtCore.Qt.AlignTop)

    # Chart heater power
    hbox2.addWidget(window.gw_heater_power, stretch=1)

    # Round up
    vbox = QtWid.QVBoxLayout()
    vbox.addLayout(hbox1)
    vbox.addLayout(hbox2)

    window.tab_heater_control.setLayout(vbox)

    # -----------------------
    #   Tab: Thermistors
    # -----------------------

    mux2_pyqt.set_table_readings_format("%.4e")
    mux2_pyqt.qgrp.setFixedWidth(420)

    hbox1 = QtWid.QHBoxLayout()
    hbox1.addWidget(mux2_pyqt.qgrp, stretch=0, alignment=QtCore.Qt.AlignTop)
    hbox1.addWidget(window.gw_mux2, stretch=1)
    hbox1.addLayout(window.vbox_mux2)

    window.tab_thermistors.setLayout(hbox1)

    # Create pens and chart histories depending on the number of scan channels

    mux2_N_channels = len(mux2.state.all_scan_list_channels)

    # Pen styles for plotting
    PENS = [None] * mux2_N_channels
    cm = pylab.get_cmap('gist_rainbow')
    params = {'width': 2}
    for i in range(mux2_N_channels):
        color = cm(1.*i/mux2_N_channels)  # color will now be an RGBA tuple
        color = np.array(color) * 255
        PENS[i] = pg.mkPen(color=color, **params)

    # Create Chart Histories (CH) and PlotDataItems and link them together
    # Also add legend entries
    window.CHs_mux2 = [None] * mux2_N_channels
    window.chkbs_show_curves_mux2 = [None] * mux2_N_channels
    for i in range(mux2_N_channels):
        window.CHs_mux2[i] = ChartHistory(C.CH_SAMPLES_MUX2,
                                          window.pi_mux2.plot(pen=PENS[i]))
        window.legend_mux2.addItem(window.CHs_mux2[i].curve,
                                   name=mux2.state.all_scan_list_channels[i])

        # Add checkboxes for showing the curves
        window.chkbs_show_curves_mux2[i] = QtWid.QCheckBox(
                parent=window,
                text=mux2.state.all_scan_list_channels[i],
                checked=True)
        window.grid_show_curves_mux2.addWidget(
                window.chkbs_show_curves_mux2[i], i, 0)

    # -----------------------
    #   Tab: Traverse
    # -----------------------

    vbox = QtWid.QVBoxLayout()
    vbox.addWidget(window.grpb_trav_img)
    vbox.addWidget(trav_step_nav.grpb)
    vbox.setAlignment(trav_step_nav.grpb, QtCore.Qt.AlignLeft)
    vbox.addStretch(1)

    hbox = QtWid.QHBoxLayout()
    hbox.addWidget(trav_vert_pyqt.qgrp, stretch=0)
    hbox.addWidget(trav_horz_pyqt.qgrp)
    hbox.addLayout(vbox)
    hbox.setAlignment(trav_horz_pyqt.qgrp, QtCore.Qt.AlignTop)
    hbox.setAlignment(trav_vert_pyqt.qgrp, QtCore.Qt.AlignTop)
    hbox.addStretch(1)

    window.tab_traverse.setLayout(hbox)

    # --------------------------------------------------------------------------
    #   File logger
    # --------------------------------------------------------------------------

    file_logger = FileLogger()
    file_logger.signal_set_recording_text.connect(window.set_text_qpbt_record)

    file_logger_mux2 = FileLogger()

    # --------------------------------------------------------------------------
    #   Start threads
    # --------------------------------------------------------------------------

    # Arduinos
    ards_pyqt.start_thread_worker_DAQ(QtCore.QThread.TimeCriticalPriority)
    ards_pyqt.start_thread_worker_send()

    # Picotech PT-104
    if not pt104_pyqt.start_thread_worker_DAQ():
        update_GUI_PT104()  # Update GUI once to reflect offline device

    # Bronkhorst mass flow controller
    mfc_pyqt.start_thread_worker_DAQ()
    mfc_pyqt.start_thread_worker_send()

    # Keysight power supplies
    for psu_pyqt in psus_pyqt:
        psu_pyqt.signal_DAQ_updated.connect(update_GUI_heater_control_extras)
        psu_pyqt.start_thread_worker_DAQ()
        psu_pyqt.start_thread_worker_send()

    # Keysight 3497xA
    mux1_pyqt.start_thread_worker_DAQ()
    mux1_pyqt.start_thread_worker_send()
    mux2_pyqt.start_thread_worker_DAQ()
    mux2_pyqt.start_thread_worker_send()

    # ThermoFlex chiller
    chiller_pyqt.start_thread_worker_DAQ()
    chiller_pyqt.start_thread_worker_send()

    # Compax3 traverse controllers
    trav_horz_pyqt.start_thread_worker_DAQ()
    trav_horz_pyqt.start_thread_worker_send()
    trav_vert_pyqt.start_thread_worker_DAQ()
    trav_vert_pyqt.start_thread_worker_send()

    # --------------------------------------------------------------------------
    #   Connect remaining signals from GUI
    # --------------------------------------------------------------------------

    window.relay_1_1.clicked.connect(actuate_relay_1_1_from_button)
    window.relay_1_2.clicked.connect(actuate_relay_1_2_from_button)
    window.relay_1_3.clicked.connect(actuate_relay_1_3_from_button)
    window.relay_1_4.clicked.connect(actuate_relay_1_4_from_button)
    window.relay_1_5.clicked.connect(actuate_relay_1_5_from_button)
    window.relay_1_6.clicked.connect(actuate_relay_1_6_from_button)
    window.relay_1_7.clicked.connect(actuate_relay_1_7_from_button)
    window.relay_1_8.clicked.connect(actuate_relay_1_8_from_button)

    window.enable_pump.clicked.connect(actuate_relay_2_8_from_button)

    window.relay_3_1.clicked.connect(actuate_relay_3_1_from_button)
    window.relay_3_2.clicked.connect(actuate_relay_3_2_from_button)
    window.relay_3_3.clicked.connect(actuate_relay_3_3_from_button)
    window.relay_3_4.clicked.connect(actuate_relay_3_4_from_button)
    window.relay_3_5.clicked.connect(actuate_relay_3_5_from_button)
    window.relay_3_6.clicked.connect(actuate_relay_3_6_from_button)
    window.relay_3_7.clicked.connect(actuate_relay_3_7_from_button)
    window.relay_3_8.clicked.connect(actuate_relay_3_8_from_button)

    window.FS_exec_1.clicked.connect(exec_FS_idle)
    window.FS_exec_2.clicked.connect(exec_FS_barrel_1_to_tunnel)
    window.FS_exec_3.clicked.connect(exec_FS_barrel_2_to_tunnel)
    window.FS_exec_4.clicked.connect(exec_FS_tunnel_to_barrel_1)
    window.FS_exec_5.clicked.connect(exec_FS_tunnel_to_barrel_2)
    window.FS_exec_6.clicked.connect(exec_FS_barrel_1_to_sewer)
    window.FS_exec_7.clicked.connect(exec_FS_barrel_2_to_sewer)
    window.FS_exec_8.clicked.connect(exec_FS_tunnel_to_sewer)

    window.set_pump_speed_pct.editingFinished.connect(
            set_pump_speed_from_pct_textbox)
    window.set_pump_speed_mA.editingFinished.connect(
            set_pump_speed_from_mA_textbox)

    window.rbtn_MS1.clicked.connect(process_rbtn_MS)
    window.rbtn_MS2.clicked.connect(process_rbtn_MS)
    window.rbtn_MS3.clicked.connect(process_rbtn_MS)

    window.GVF_density_liquid.editingFinished.connect(
            process_GVF_density_liquid)

    window.enable_pump_PID.clicked.connect(process_pbtn_enable_pump_PID)
    window.set_flow_speed_cms.editingFinished.connect(
            set_tunnel_flow_speed_cms_from_textbox)

    window.pbtn_reset.clicked.connect(soft_reset)
    window.pbtn_record.clicked.connect(process_pbtn_record_to_file)

    window.pbtn_history_1.clicked.connect(process_pbtn_history_1)
    window.pbtn_history_2.clicked.connect(process_pbtn_history_2)
    window.pbtn_history_3.clicked.connect(process_pbtn_history_3)
    window.pbtn_history_4.clicked.connect(process_pbtn_history_4)
    window.pbtn_history_5.clicked.connect(process_pbtn_history_5)
    window.pbtn_history_6.clicked.connect(process_pbtn_history_6)

    window.pbtn_ENA_OTP.clicked.connect(process_pbtn_ENA_OTP)

    window.fill_TC_chart_random.clicked.connect(
            fill_TC_chart_with_random_data)

    # --------------------------------------------------------------------------
    #   Set up timers
    # --------------------------------------------------------------------------

    timer_charts = QtCore.QTimer()
    timer_charts.timeout.connect(update_charts)
    timer_charts.start(C.UPDATE_INTERVAL_CHARTS)

    timer_psus = QtCore.QTimer()
    timer_psus.timeout.connect(trigger_update_psus)
    timer_psus.start(C.UPDATE_INTERVAL_PSUs)

    # --------------------------------------------------------------------------
    #   Last inits
    # --------------------------------------------------------------------------

    # Init manual control of relays
    window.relay_3_manual_control()

    # Deselect TC temperatures 11 & 12
    window.chkbs_heater_TC[10].setChecked(False)
    window.chkbs_heater_TC[11].setChecked(False)

    # Stripchart downsampling
    #window.pi_heater_TC.setDownsampling(ds=10, auto=False, mode='mean')
    #window.pi_flow_speed.setDownsampling(ds=10, auto=False, mode='mean')
    #window.plot_set_pump_speed.setDownsampling(ds=10, auto=False, method='mean')

    # Init the time axis of the strip charts
    process_pbtn_history_3()

    # Retrieve the last used measurement section from config file on disk
    meas_section_number = 2  # Default when file can not be read or found
    if C.PATH_CONFIG_MEAS_SECTION.is_file():
        try:
            with C.PATH_CONFIG_MEAS_SECTION.open() as f:
                meas_section_number = int(f.readline().strip())
        except:
            pass    # Do not panic and remain silent

    if meas_section_number == 1:
        window.rbtn_MS1.setChecked(True)
        state.area_meas_section = C.AMS_1
    elif meas_section_number == 2:
        window.rbtn_MS2.setChecked(True)
        state.area_meas_section = C.AMS_2
    elif meas_section_number == 3:
        window.rbtn_MS3.setChecked(True)
        state.area_meas_section = C.AMS_3

    # Init the liquid density
    process_GVF_density_liquid()

    # Debugging test
    window.pbtn_debug_1.clicked.connect(lambda:
      window.pi_heater_TC.setDownsampling(ds=10, auto=False, mode='mean'))
    window.pbtn_debug_2.clicked.connect(lambda:
      window.pi_heater_TC.setDownsampling(ds=1, auto=False, mode='mean'))

    # DEBUG
    #window.tabs.setCurrentIndex(1)

    # --------------------------------------------------------------------------
    #   Start the main GUI event loop
    # --------------------------------------------------------------------------

    window.setGeometry(220, 34, 1310, 1010)
    window.show()
    sys.exit(app.exec_())