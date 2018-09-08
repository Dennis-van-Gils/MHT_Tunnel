#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dennis_van_Gils
17-04-2018
"""

import numpy as np
import queue

from PyQt5 import QtCore, QtGui
from PyQt5 import QtWidgets as QtWid

from DvG_debug_functions import ANSI, dprint
from DvG_PyQt_controls import (create_Toggle_button,
                               create_error_LED,
                               create_tiny_error_LED,
                               SS_GROUP)
import DvG_dev_ThermoFlex_chiller__fun_RS232 as chiller_functions

# Show debug info in terminal? Warning: slow! Do not leave on unintentionally.
DEBUG = False

# Short-hand aliases for DEBUG information
curThread = QtCore.QThread.currentThread

# Special characters
CHAR_DEG_C = chr(176) + 'C'

# ------------------------------------------------------------------------------
#   ThermoFlex_chiller_pyqt
# ------------------------------------------------------------------------------

class ThermoFlex_chiller_pyqt(QtWid.QWidget):
    """Collection of PyQt related functions and objects to provide a GUI and
    automated data transmission/acquisition for a Thermo Scientific ThermoFlex
    recirculating chiller, from now on referred to as the 'device'.

    Create the block of PyQt GUI elements for the device and handle the control
    functionality. The main QWidget object is of type [QtWidgets.QHBoxLayout]
    and resides at 'self.hbly_GUI' This can be added to e.g. the main window of
    the app.
    !! No device I/O operations are allowed at this class level. It solely
    focusses on handling the GUI !!

    All device I/O operations will be offloaded to separate 'Workers', which
    reside as nested classes inside of this class. Instances of these workers
    should be transferred to separate threads and not be run on the same thread
    as the GUI. This will keep the GUI and main routine responsive, without
    blocking when communicating with the device.
    !! No changes to the GUI are allowed inside these nested classes !!

    Two workers are created as class members at init of this class:
        - worker_send
            Maintains a queue where desired device I/O operations can be put on
            the stack. The worker will periodically send out the operations to
            the device as scheduled in the queue.

        - worker_state
            Periodically query the device for its state.
    """

    def __init__(self, dev: chiller_functions.ThermoFlex_chiller,
                 update_interval_ms=1000,
                 DEBUG_color=ANSI.PURPLE, parent=None):
        super(ThermoFlex_chiller_pyqt, self).__init__(parent=parent)

        # Store reference to 'chiller_functions.ThermoFlex_chiller()' instance
        self.dev = dev

        # Create mutex for proper multithreading
        self.dev.mutex = QtCore.QMutex()

        # Terminal text color for DEBUG information
        self.DEBUG_color = DEBUG_color

        # Periodically query the device for its state.
        # !! To be put in a seperate thread !!
        self.worker_state = self.Worker_state(dev, update_interval_ms,
                                              DEBUG_color)

        # Maintains a queue where desired device I/O operations can be put on
        # the stack. The worker will periodically send out the operations to the
        # device as scheduled in the queue.
        # !! To be put in a seperate thread !!
        self.worker_send = self.Worker_send(dev, DEBUG_color)

        # Create the block of GUI elements for the device. The main QWidget
        # object is of type [QtWidgets.QHBoxLayout] and resides at
        # 'self.hbly_GUI'
        self.create_GUI()
        self.connect_signals_to_slots()

        # Make sure GUI is updated al least once to correctly reflect an offline
        # chiller
        if not self.dev.is_alive:
            self.update_GUI()

        # Create and set up threads
        if self.dev.is_alive:
            self.thread_state = QtCore.QThread()
            self.thread_state.setObjectName("%s_state" % self.dev.name)
            self.worker_state.moveToThread(self.thread_state)
            self.thread_state.started.connect(self.worker_state.run)

            self.thread_send = QtCore.QThread()
            self.thread_send.setObjectName("%s_send" % self.dev.name)
            self.worker_send.moveToThread(self.thread_send)
            self.thread_send.started.connect(self.worker_send.run)
        else:
            self.thread_state = None
            self.thread_send = None

    # --------------------------------------------------------------------------
    #   Create QGroupBoxes with controls
    # --------------------------------------------------------------------------

    def create_GUI(self):
        # ------------------------------
        #   Groupbox "Alarm values"
        # ------------------------------

        self.grpb_alarms = QtWid.QGroupBox("Alarm values")
        self.grpb_alarms.setStyleSheet(SS_GROUP)

        p = {'alignment': QtCore.Qt.AlignRight,
             'minimumWidth': 50,
             'maximumWidth': 30,
             'readOnly': True}
        self.LO_flow = QtWid.QLineEdit(**p)
        self.HI_flow = QtWid.QLineEdit(**p)
        self.LO_pres = QtWid.QLineEdit(**p)
        self.HI_pres = QtWid.QLineEdit(**p)
        self.LO_temp = QtWid.QLineEdit(**p)
        self.HI_temp = QtWid.QLineEdit(**p)
        self.pbtn_read_alarm_values = QtWid.QPushButton("Read")
        self.pbtn_read_alarm_values.setMinimumSize(50, 30)

        p = {'alignment': QtCore.Qt.AlignCenter}
        grid = QtWid.QGridLayout()
        grid.addWidget(QtWid.QLabel("Values can be set in the chiller's menu",
                                    **p)          , 0, 0, 1, 4)
        grid.addWidget(QtWid.QLabel("LO")         , 1, 1)
        grid.addWidget(QtWid.QLabel("HI")         , 1, 2)
        grid.addWidget(QtWid.QLabel("Flow rate")  , 2, 0)
        grid.addWidget(self.LO_flow               , 2, 1)
        grid.addWidget(self.HI_flow               , 2, 2)
        grid.addWidget(QtWid.QLabel("LPM")        , 2, 3)
        grid.addWidget(QtWid.QLabel("Pressure")   , 3, 0)
        grid.addWidget(self.LO_pres               , 3, 1)
        grid.addWidget(self.HI_pres               , 3, 2)
        grid.addWidget(QtWid.QLabel("bar")        , 3, 3)
        grid.addWidget(QtWid.QLabel("Temperature"), 4, 0)
        grid.addWidget(self.LO_temp               , 4, 1)
        grid.addWidget(self.HI_temp               , 4, 2)
        grid.addWidget(QtWid.QLabel(CHAR_DEG_C)   , 4, 3)
        grid.addWidget(self.pbtn_read_alarm_values, 5, 0)

        self.grpb_alarms.setLayout(grid)

        # ------------------------------
        #   Groupbox "PID feedback"
        # ------------------------------

        self.grpb_PID = QtWid.QGroupBox("PID feedback")
        self.grpb_PID.setStyleSheet(SS_GROUP)

        p = {'alignment': QtCore.Qt.AlignRight,
             'minimumWidth': 50,
             'maximumWidth': 30,
             'readOnly': True}
        self.PID_P = QtWid.QLineEdit(**p)
        self.PID_I = QtWid.QLineEdit(**p)
        self.PID_D = QtWid.QLineEdit(**p)
        self.pbtn_read_PID_values = QtWid.QPushButton("Read")
        self.pbtn_read_PID_values.setMinimumSize(50, 30)

        p = {'alignment': QtCore.Qt.AlignCenter}
        grid = QtWid.QGridLayout()
        grid.addWidget(QtWid.QLabel("Values can be set in the chiller's menu",
                                    **p)                          , 0, 0, 1, 3)
        grid.addWidget(QtWid.QLabel("P", **p)                     , 1, 0)
        grid.addWidget(self.PID_P                                 , 1, 1)
        grid.addWidget(QtWid.QLabel("% span of 100" + CHAR_DEG_C) , 1, 2)
        grid.addWidget(QtWid.QLabel("I", **p)                     , 2, 0)
        grid.addWidget(self.PID_I                                 , 2, 1)
        grid.addWidget(QtWid.QLabel("repeats/minute")             , 2, 2)
        grid.addWidget(QtWid.QLabel("D", **p)                     , 3, 0)
        grid.addWidget(self.PID_D                                 , 3, 1)
        grid.addWidget(QtWid.QLabel("minutes")                    , 3, 2)
        grid.addWidget(self.pbtn_read_PID_values                  , 4, 0)

        self.grpb_PID.setLayout(grid)

        # ------------------------------
        #   Groupbox "Status bits"
        # ------------------------------

        self.grpb_SBs = QtWid.QGroupBox("Status bits")
        self.grpb_SBs.setStyleSheet(SS_GROUP)

        self.SB_tripped                = create_error_LED()
        self.SB_tripped.setText("No faults")
        self.SB_high_temp_fixed        = create_tiny_error_LED()
        self.SB_low_temp_fixed         = create_tiny_error_LED()
        self.SB_high_temp              = create_tiny_error_LED()
        self.SB_low_temp               = create_tiny_error_LED()
        self.SB_high_pressure          = create_tiny_error_LED()
        self.SB_low_pressure           = create_tiny_error_LED()
        self.SB_drip_pan               = create_tiny_error_LED()
        self.SB_high_level             = create_tiny_error_LED()
        self.SB_phase_monitor          = create_tiny_error_LED()
        self.SB_motor_overload         = create_tiny_error_LED()
        self.SB_LPC                    = create_tiny_error_LED()
        self.SB_HPC                    = create_tiny_error_LED()
        self.SB_external_EMO           = create_tiny_error_LED()
        self.SB_local_EMO              = create_tiny_error_LED()
        self.SB_low_flow               = create_tiny_error_LED()
        self.SB_low_level              = create_tiny_error_LED()
        self.SB_sense_5V               = create_tiny_error_LED()
        self.SB_invalid_level          = create_tiny_error_LED()
        self.SB_low_fixed_flow_warning = create_tiny_error_LED()
        self.SB_high_pressure_factory  = create_tiny_error_LED()
        self.SB_low_pressure_factory   = create_tiny_error_LED()

        p = {'alignment': QtCore.Qt.AlignRight}
        grid = QtWid.QGridLayout()
        grid.addWidget(self.SB_tripped                            , 0, 0, 1, 2)
        grid.addItem(QtWid.QSpacerItem(1, 12)                          , 1, 0)
        grid.addWidget(QtWid.QLabel("high temp fixed fault", **p)      , 2, 0)
        grid.addWidget(self.SB_high_temp_fixed                         , 2, 1)
        grid.addWidget(QtWid.QLabel("low temp fixed fault", **p)       , 3, 0)
        grid.addWidget(self.SB_low_temp_fixed                          , 3, 1)
        grid.addWidget(QtWid.QLabel("high temp fault/warning", **p)    , 4, 0)
        grid.addWidget(self.SB_high_temp                               , 4, 1)
        grid.addWidget(QtWid.QLabel("low temp fault/warning", **p)     , 5, 0)
        grid.addWidget(self.SB_low_temp                                , 5, 1)
        grid.addWidget(QtWid.QLabel("high pressure fault/warning", **p), 6, 0)
        grid.addWidget(self.SB_high_pressure                           , 6, 1)
        grid.addWidget(QtWid.QLabel("low pressure fault/warning", **p) , 7, 0)
        grid.addWidget(self.SB_low_pressure                            , 7, 1)
        grid.addWidget(QtWid.QLabel("drip pan fault", **p)             , 8, 0)
        grid.addWidget(self.SB_drip_pan                                , 8, 1)
        grid.addWidget(QtWid.QLabel("high level fault", **p)           , 9, 0)
        grid.addWidget(self.SB_high_level                              , 9, 1)
        grid.addWidget(QtWid.QLabel("phase monitor fault", **p)        , 10, 0)
        grid.addWidget(self.SB_phase_monitor                           , 10, 1)
        grid.addWidget(QtWid.QLabel("motor overload fault", **p)       , 11, 0)
        grid.addWidget(self.SB_motor_overload                          , 11, 1)
        grid.addWidget(QtWid.QLabel("LPC fault", **p)                  , 12, 0)
        grid.addWidget(self.SB_LPC                                     , 12, 1)
        grid.addWidget(QtWid.QLabel("HPC fault", **p)                  , 13, 0)
        grid.addWidget(self.SB_HPC                                     , 13, 1)
        grid.addWidget(QtWid.QLabel("external EMO fault", **p)         , 14, 0)
        grid.addWidget(self.SB_external_EMO                            , 14, 1)
        grid.addWidget(QtWid.QLabel("local EMO fault", **p)            , 15, 0)
        grid.addWidget(self.SB_local_EMO                               , 15, 1)
        grid.addWidget(QtWid.QLabel("low flow fault", **p)             , 16, 0)
        grid.addWidget(self.SB_low_flow                                , 16, 1)
        grid.addWidget(QtWid.QLabel("low level fault", **p)            , 17, 0)
        grid.addWidget(self.SB_low_level                               , 17, 1)
        grid.addWidget(QtWid.QLabel("sense 5V fault", **p)             , 18, 0)
        grid.addWidget(self.SB_sense_5V                                , 18, 1)
        grid.addWidget(QtWid.QLabel("invalid level fault", **p)        , 19, 0)
        grid.addWidget(self.SB_invalid_level                           , 19, 1)
        grid.addWidget(QtWid.QLabel("low fixed flow warning", **p)     , 20, 0)
        grid.addWidget(self.SB_low_fixed_flow_warning                  , 20, 1)
        grid.addWidget(QtWid.QLabel("high pressure factory fault", **p), 21, 0)
        grid.addWidget(self.SB_high_pressure_factory                   , 21, 1)
        grid.addWidget(QtWid.QLabel("low pressure factory fault", **p) , 22, 0)
        grid.addWidget(self.SB_low_pressure_factory                    , 22, 1)

        self.grpb_SBs.setLayout(grid)

        # ------------------------------
        #   Groupbox "Control"
        # ------------------------------

        self.grpb_control = QtWid.QGroupBox("Control")
        self.grpb_control.setStyleSheet(SS_GROUP)

        p = {'alignment': QtCore.Qt.AlignRight,
             'minimumWidth': 50,
             'maximumWidth': 30}

        self.lbl_offline = QtWid.QLabel("OFFLINE", visible=False,
            font=QtGui.QFont("Palatino", 14, weight=QtGui.QFont.Bold),
            alignment=QtCore.Qt.AlignCenter)
        self.pbtn_on       = create_Toggle_button("Off")
        self.powering_down = create_tiny_error_LED()
        self.send_setpoint = QtWid.QLineEdit(**p)
        self.read_setpoint = QtWid.QLineEdit(**p, readOnly=True)
        self.read_temp     = QtWid.QLineEdit(**p, readOnly=True)
        self.read_flow     = QtWid.QLineEdit(**p, readOnly=True)
        self.read_supply   = QtWid.QLineEdit(**p, readOnly=True)
        self.read_suction  = QtWid.QLineEdit(**p, readOnly=True)
        self.lbl_update_counter = QtWid.QLabel("0")

        grid = QtWid.QGridLayout()
        grid.addWidget(self.lbl_offline                   , 0, 0, 1, 3)
        grid.addWidget(self.pbtn_on                       , 1, 0, 1, 3)
        grid.addWidget(QtWid.QLabel("Is powering up/down?",
                       alignment=QtCore.Qt.AlignRight)    , 2, 0, 1, 2)
        grid.addWidget(self.powering_down                 , 2, 2)
        grid.addItem(QtWid.QSpacerItem(1, 12)             , 3, 0)
        grid.addWidget(QtWid.QLabel("Send setpoint")      , 4, 0)
        grid.addWidget(QtWid.QLabel("Read setpoint")      , 5, 0)
        grid.addWidget(self.send_setpoint                 , 4, 1)
        grid.addWidget(self.read_setpoint                 , 5, 1)
        grid.addWidget(QtWid.QLabel(CHAR_DEG_C)           , 4, 2)
        grid.addWidget(QtWid.QLabel(CHAR_DEG_C)           , 5, 2)
        grid.addItem(QtWid.QSpacerItem(1, 12)             , 6, 0)
        grid.addWidget(QtWid.QLabel("Read temp")          , 7, 0)
        grid.addWidget(self.read_temp                     , 7, 1)
        grid.addWidget(QtWid.QLabel(CHAR_DEG_C)           , 7, 2)
        grid.addWidget(QtWid.QLabel("Read flow")          , 8, 0)
        grid.addWidget(self.read_flow                     , 8, 1)
        grid.addWidget(QtWid.QLabel("LPM")                , 8, 2)
        grid.addWidget(QtWid.QLabel("Read supply")        , 9, 0)
        grid.addWidget(self.read_supply                   , 9, 1)
        grid.addWidget(QtWid.QLabel("bar")                , 9, 2)
        grid.addWidget(QtWid.QLabel("Read suction")       , 10, 0)
        grid.addWidget(self.read_suction                  , 10, 1)
        grid.addWidget(QtWid.QLabel("bar")                , 10, 2)

        grid.addItem(QtWid.QSpacerItem(1, 12)                      , 11, 0)
        grid.addWidget(QtWid.QLabel("Nominal values @ 15-02-2018:"), 12, 0, 1, 3)
        grid.addWidget(QtWid.QLabel("Read flow")                   , 13, 0)
        grid.addWidget(QtWid.QLabel("80  ",
                                    alignment=QtCore.Qt.AlignRight), 13, 1)
        grid.addWidget(QtWid.QLabel("LPM")                         , 13, 2)
        grid.addWidget(QtWid.QLabel("Read supply")                 , 14, 0)
        grid.addWidget(QtWid.QLabel("2.9  ",
                                    alignment=QtCore.Qt.AlignRight), 14, 1)
        grid.addWidget(QtWid.QLabel("bar")                         , 14, 2)
        grid.addWidget(QtWid.QLabel("Read suction")                , 15, 0)
        grid.addWidget(QtWid.QLabel("40  ",
                                    alignment=QtCore.Qt.AlignRight), 15, 1)
        grid.addWidget(QtWid.QLabel("bar")                         , 15, 2)
        grid.addWidget(self.lbl_update_counter                     , 16, 0, 1, 2)

        self.grpb_control.setLayout(grid)

        # --------------------------------------
        #   Round up final QtWid.QHBoxLayout()
        # --------------------------------------

        vbox = QtWid.QVBoxLayout()
        vbox.addWidget(self.grpb_alarms)
        vbox.addWidget(self.grpb_PID)
        vbox.setAlignment(self.grpb_alarms, QtCore.Qt.AlignTop)
        vbox.setAlignment(self.grpb_PID, QtCore.Qt.AlignTop)
        vbox.setAlignment(QtCore.Qt.AlignTop)

        self.hbly_GUI = QtWid.QHBoxLayout()
        self.hbly_GUI.addLayout(vbox)
        self.hbly_GUI.addWidget(self.grpb_SBs)
        self.hbly_GUI.addWidget(self.grpb_control)
        self.hbly_GUI.addStretch(1)
        self.hbly_GUI.setAlignment(self.grpb_SBs, QtCore.Qt.AlignTop)
        self.hbly_GUI.setAlignment(self.grpb_control, QtCore.Qt.AlignTop)
        self.hbly_GUI.setAlignment(QtCore.Qt.AlignTop)

        #tab_chiller.setLayout(self.hbly_GUI)

    # --------------------------------------------------------------------------
    #   update_GUI
    # --------------------------------------------------------------------------

    @QtCore.pyqtSlot()
    def update_GUI(self):
        """NOTE: 'self.dev.mutex' is not being locked, because we are only
        reading 'state' for displaying purposes. We can do this because 'state'
        members are written and read atomicly.
        Not locking the mutex might speed up the program.
        """
        if self.dev.is_alive:
            # At startup
            if self.dev.update_counter == 1:
                self.update_GUI_alarm_values()
                self.update_GUI_PID_values()
                self.send_setpoint.setText("%.1f" % self.dev.state.setpoint)

            # State
            self.read_setpoint.setText("%.1f" % self.dev.state.setpoint)
            self.read_temp.setText    ("%.1f" % self.dev.state.temp)
            self.read_flow.setText    ("%.1f" % self.dev.state.flow)
            self.read_supply.setText  ("%.2f" % self.dev.state.supply_pres)
            self.read_suction.setText ("%.2f" % self.dev.state.suction_pres)

            # Power
            SBs = self.dev.status_bits  # Short-hand
            self.pbtn_on.setChecked(SBs.running)
            if SBs.running:
                self.pbtn_on.setText("ON")
            else:
                self.pbtn_on.setText("OFF")
            self.powering_down.setChecked(SBs.powering_down)

            # Status bits
            self.SB_tripped.setChecked(SBs.fault_tripped)
            if self.dev.status_bits.fault_tripped:
                self.SB_tripped.setText("FAULT TRIPPED")
            else:
                self.SB_tripped.setText("No faults")
            self.SB_drip_pan.setChecked(SBs.drip_pan_fault)
            self.SB_external_EMO.setChecked(SBs.external_EMO_fault)
            self.SB_high_level.setChecked(SBs.high_level_fault)
            self.SB_high_pressure.setChecked(SBs.high_pressure_fault)
            self.SB_high_pressure_factory.setChecked(
                    SBs.high_pressure_fault_factory)
            self.SB_high_temp.setChecked(SBs.high_temp_fault)
            self.SB_high_temp_fixed.setChecked(SBs.high_temp_fixed_fault)
            self.SB_HPC.setChecked(SBs.HPC_fault)
            self.SB_invalid_level.setChecked(SBs.invalid_level_fault)
            self.SB_local_EMO.setChecked(SBs.local_EMO_fault)
            self.SB_low_fixed_flow_warning.setChecked(
                    SBs.low_fixed_flow_warning)
            self.SB_low_flow.setChecked(SBs.low_flow_fault)
            self.SB_low_level.setChecked(SBs.low_level_fault)
            self.SB_low_pressure.setChecked(SBs.low_pressure_fault)
            self.SB_low_pressure_factory.setChecked(
                    SBs.low_pressure_fault_factory)
            self.SB_low_temp.setChecked(SBs.low_temp_fault)
            self.SB_low_temp_fixed.setChecked(SBs.low_temp_fixed_fault)
            self.SB_LPC.setChecked(SBs.LPC_fault)
            self.SB_motor_overload.setChecked(SBs.motor_overload_fault)
            self.SB_phase_monitor.setChecked(SBs.phase_monitor_fault)
            self.SB_sense_5V.setChecked(SBs.sense_5V_fault)

            self.lbl_update_counter.setText("%s" % self.dev.update_counter)
        else:
            self.grpb_alarms.setEnabled(False)
            self.grpb_PID.setEnabled(False)
            self.grpb_SBs.setEnabled(False)
            self.grpb_control.setEnabled(False)

            self.pbtn_on.setVisible(False)
            self.lbl_offline.setVisible(True)

    @QtCore.pyqtSlot()
    def update_GUI_alarm_values(self):
        self.LO_flow.setText("%.1f" % self.dev.values_alarm.LO_flow)
        if self.dev.values_alarm.HI_flow == 0:
            self.HI_flow.setText("No limit")
        else:
            self.HI_flow.setText("%.1f" % self.dev.values_alarm.HI_flow)
        self.LO_pres.setText("%.2f" % self.dev.values_alarm.LO_pres)
        self.HI_pres.setText("%.2f" % self.dev.values_alarm.HI_pres)
        self.LO_temp.setText("%.1f" % self.dev.values_alarm.LO_temp)
        self.HI_temp.setText("%.1f" % self.dev.values_alarm.HI_temp)

    @QtCore.pyqtSlot()
    def update_GUI_PID_values(self):
        self.PID_P.setText("%.1f" % self.dev.values_PID.P)
        self.PID_I.setText("%.2f" % self.dev.values_PID.I)
        self.PID_D.setText("%.1f" % self.dev.values_PID.D)

    # --------------------------------------------------------------------------
    #   GUI functions
    # --------------------------------------------------------------------------

    @QtCore.pyqtSlot()
    def process_pbtn_on(self):
        if self.dev.status_bits.running:
            self.worker_send.queue.put((self.dev.turn_off,))
        else:
            self.worker_send.queue.put((self.dev.turn_on,))

    @QtCore.pyqtSlot()
    def process_pbtn_read_alarm_values(self):
        self.worker_send.queue.put((self.dev.query_alarm_values_and_units,))
        self.worker_send.queue.put(("signal_GUI_alarm_values_update",))

    @QtCore.pyqtSlot()
    def process_pbtn_read_PID_values(self):
        self.worker_send.queue.put((self.dev.query_PID_values,))
        self.worker_send.queue.put(("signal_GUI_PID_values_update",))

    @QtCore.pyqtSlot()
    def send_setpoint_from_textbox(self):
        try:
            setpoint = float(self.send_setpoint.text())
        except (TypeError, ValueError):
            setpoint = 22.0
        except:
            raise()

        setpoint = np.clip(setpoint,
                           self.dev.min_setpoint_degC,
                           self.dev.max_setpoint_degC)
        self.send_setpoint.setText("%.1f" % setpoint)

        self.worker_send.queue.put((self.dev.send_setpoint, setpoint))

    # --------------------------------------------------------------------------
    #   connect_signals_to_slots
    # --------------------------------------------------------------------------

    def connect_signals_to_slots(self):
        self.pbtn_on.clicked.connect(self.process_pbtn_on)
        self.pbtn_read_alarm_values.clicked.connect(
                self.process_pbtn_read_alarm_values)
        self.pbtn_read_PID_values.clicked.connect(
                self.process_pbtn_read_PID_values)
        self.send_setpoint.editingFinished.connect(
                self.send_setpoint_from_textbox)

        self.worker_state.signal_GUI_update.connect(self.update_GUI)
        self.worker_send.signal_GUI_alarm_values_update.connect(
                self.update_GUI_alarm_values)
        self.worker_send.signal_GUI_PID_values_update.connect(
                self.update_GUI_PID_values)

    # --------------------------------------------------------------------------
    #   Worker_send
    # --------------------------------------------------------------------------

    class Worker_send(QtCore.QObject):
        """No changes to the GUI are allowed inside this class!
        """
        signal_GUI_alarm_values_update = QtCore.pyqtSignal()
        signal_GUI_PID_values_update = QtCore.pyqtSignal()

        def __init__(self, dev: chiller_functions.ThermoFlex_chiller,
                     DEBUG_color=ANSI.YELLOW):
            super().__init__(None)

            self.dev = dev
            self.running = True

            # Put a 'sentinel' value in the queue to signal the end. This way we
            # can prevent a Queue.Empty exception being thrown later on when we
            # will read the queue till the end.
            self.sentinel = None
            self.queue = queue.Queue()
            self.queue.put(self.sentinel)

            # Terminal text color for DEBUG information
            self.DEBUG_color = DEBUG_color

            if DEBUG:
                dprint("Worker_send  %s init: thread %s" %
                       (self.dev.name, curThread().objectName()),
                       self.DEBUG_color)

        @QtCore.pyqtSlot()
        def run(self):
            if DEBUG:
                dprint("Worker_send  %s run : thread %s" %
                       (self.dev.name, curThread().objectName()),
                       self.DEBUG_color)

            while self.running:
                #if DEBUG:
                #    dprint("Worker_send  %s queued: %s" %
                #           (self.dev.name, self.queue.qsize() - 1),
                #           self.DEBUG_color)

                # Process all jobs until the queue is empty
                for job in iter(self.queue.get_nowait, self.sentinel):
                    func = job[0]
                    args = job[1:]

                    if (func == "signal_GUI_alarm_values_update"):
                        # Special instruction
                        if DEBUG:
                            dprint("Worker_send  %s: %s %s" %
                                   (self.dev.name, func, args),
                                   self.DEBUG_color)
                        self.signal_GUI_alarm_values_update.emit()
                    elif (func == "signal_GUI_PID_values_update"):
                        # Special instruction
                        if DEBUG:
                            dprint("Worker_send  %s: %s %s" %
                                   (self.dev.name, func, args),
                                   self.DEBUG_color)
                        self.signal_GUI_PID_values_update.emit()
                    else:
                        # Send I/O operation to the chiller device
                        if DEBUG:
                            dprint("Worker_send  %s: %s %s" %
                                   (self.dev.name, func.__name__, args),
                                   self.DEBUG_color)
                        locker = QtCore.QMutexLocker(self.dev.mutex)
                        func(*args)
                        # DEBUG: Might need to wait short time here for proper I/O?
                        locker.unlock()
                self.queue.put(self.sentinel)  # Put sentinel back in

                # Slow down thread
                QtCore.QThread.msleep(50)

            if DEBUG:
                dprint("Worker_send  %s: done running" % self.dev.name,
                       self.DEBUG_color)

        @QtCore.pyqtSlot()
        def stop(self):
            self.running = False

    # --------------------------------------------------------------------------
    #   Worker_state
    # --------------------------------------------------------------------------

    class Worker_state(QtCore.QObject):
        """This Worker will read the status and readings of the device at a
        fixed rate. No changes to the GUI are allowed inside this class!
        """
        signal_GUI_update = QtCore.pyqtSignal()
        #connection_lost = QtCore.pyqtSignal()

        def __init__(self, dev: chiller_functions.ThermoFlex_chiller,
                     update_interval_ms=1000,
                     DEBUG_color=ANSI.YELLOW):
            super().__init__(None)

            self.dev = dev
            self.dev.update_counter = 0
            self.update_interval_ms = update_interval_ms

            # Terminal text color for DEBUG information
            self.DEBUG_color = DEBUG_color

            if DEBUG:
                 dprint("Worker_state %s init: thread %s" %
                       (self.dev.name, curThread().objectName()),
                       self.DEBUG_color)

        @QtCore.pyqtSlot()
        def run(self):
            if DEBUG:
                dprint("Worker_state %s run : thread %s" %
                   (self.dev.name, curThread().objectName()),
                   self.DEBUG_color)

            self.timer = QtCore.QTimer()
            self.timer.setInterval(self.update_interval_ms)
            self.timer.timeout.connect(self.acquire_state)
            self.timer.start()

        def acquire_state(self):
            self.dev.update_counter += 1

            if DEBUG:
                    dprint("Worker_state %s: iter %i" %
                           (self.dev.name, self.dev.update_counter),
                           self.DEBUG_color)

            locker = QtCore.QMutexLocker(self.dev.mutex)
            self.dev.query_status_bits()
            self.dev.query_state()
            locker.unlock()

            # TO DO: check for connection lost
            #self.connection_lost.emit()

            self.signal_GUI_update.emit()

    # --------------------------------------------------------------------------
    #   close_threads
    # --------------------------------------------------------------------------

    def close_threads(self):
        if self.thread_state is not None:
            #self.worker_state.stop()  # Not necessary
            self.thread_state.quit()
            print("Closing thread %-13s: " %
                  self.thread_state.objectName(), end='')
            if self.thread_state.wait(2000): print("done.\n", end='')
            else: print("FAILED.\n", end='')

        # Close thread_send
        if self.thread_send is not None:
            self.worker_send.stop()
            self.thread_send.quit()
            print("Closing thread %-13s: " %
                  self.thread_send.objectName(), end='')
            if self.thread_send.wait(2000): print("done.\n", end='')
            else: print("FAILED.\n", end='')