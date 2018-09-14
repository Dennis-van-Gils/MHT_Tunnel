#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dennis van Gils
15-09-2018
"""

import queue
#import time

import numpy as np
from PyQt5 import QtCore, QtGui
from PyQt5 import QtWidgets as QtWid

import DvG_PID_controller
from DvG_debug_functions import ANSI, dprint
from DvG_pyqt_controls import (create_Toggle_button,
                               create_tiny_error_LED,
                               SS_TEXTBOX_ERRORS,
                               SS_GROUP)
import DvG_dev_Keysight_N8700_PSU__fun_SCPI as N8700_functions

# Show debug info in terminal? Warning: slow! Do not leave on unintentionally.
DEBUG = False

# Short-hand aliases for DEBUG information
curThread = QtCore.QThread.currentThread

# Monospace font
FONT_MONOSPACE = QtGui.QFont("Monospace", 12, weight=QtGui.QFont.Bold)
FONT_MONOSPACE.setStyleHint(QtGui.QFont.TypeWriter)

# Enumeration
class GUI_input_fields():
    [ALL, OVP_level, V_source, I_source, P_source] = range(5)

# ------------------------------------------------------------------------------
#   PSU_pyqt
# ------------------------------------------------------------------------------

class PSU_pyqt(QtWid.QWidget):
    """Collection of PyQt related functions and objects to provide a GUI and
    automated data transmission/acquisition for a Keysight N8700 power supply,
    from now on referred to as the 'device'.

    Create the block of PyQt GUI elements for the device and handle the control
    functionality. The main QWidget object is of type QGroupBox and resides at
    'self.grpb'. This can be added to e.g. the main window of the app.
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

    def __init__(self, dev: N8700_functions.PSU, DEBUG_color=ANSI.YELLOW,
                 parent=None):
        super(PSU_pyqt, self).__init__(parent=parent)

        # Store reference to 'N8700_functions.PSU()' instance
        self.dev = dev

        # Create mutex for proper multithreading
        self.dev.mutex = QtCore.QMutex()

        # Terminal text color for DEBUG information
        self.DEBUG_color = DEBUG_color

        # Add PID controller on the power output
        # DvG, 25-06-2018: Kp=0.5, Ki=2, Kd=0
        self.dev.PID_power = DvG_PID_controller.PID(Kp=0.5, Ki=2, Kd=0)

        # Periodically query the PSU for its state.
        # !! To be put in a seperate thread !!
        self.worker_state = self.Worker_state(dev, DEBUG_color)

        # Maintains a queue where desired PSU I/O operations can be put on the
        # stack. The worker will periodically send out the operations to the
        # PSU as scheduled in the queue.
        # !! To be put in a seperate thread !!
        self.worker_send = self.Worker_send(dev, DEBUG_color)

        # Create the block of GUI elements for the PSU. The main QWidget object
        # is of type QGroupBox and resides at 'self.grpb'
        self.create_GUI()
        self.connect_signals_to_slots()

        # Update GUI immediately, instead of waiting for the first refresh
        self.update_GUI()
        self.update_GUI_input_field()

        # Create and set up threads
        if self.dev.is_alive:
            self.thread_state = QtCore.QThread()
            self.thread_state.setObjectName("%s state" % self.dev.name)
            self.worker_state.moveToThread(self.thread_state)
            self.thread_state.started.connect(self.worker_state.run)

            self.thread_send = QtCore.QThread()
            self.thread_send.setObjectName("%s send" % self.dev.name)
            self.worker_send.moveToThread(self.thread_send)
            self.thread_send.started.connect(self.worker_send.run)
        else:
            self.thread_state = None
            self.thread_send = None

    # --------------------------------------------------------------------------
    #   Create QGroupBox with controls
    # --------------------------------------------------------------------------

    def create_GUI(self):
        self.grpb = QtWid.QGroupBox(self)
        self.grpb.setTitle(self.dev.name)
        self.grpb.setStyleSheet(SS_GROUP)

        # Measure
        p = {'alignment': QtCore.Qt.AlignRight,
             'font': FONT_MONOSPACE}
        self.V_meas = QtWid.QLabel("0.00  V   ", **p)
        self.I_meas = QtWid.QLabel("0.000 A   ", **p)
        self.P_meas = QtWid.QLabel("0.00  W   ", **p)

        # Source
        p = {'maximumWidth': 60, 'alignment': QtCore.Qt.AlignRight}
        self.pbtn_ENA_output = create_Toggle_button("Output OFF")
        self.V_source = QtWid.QLineEdit("0.00" , **p)
        self.I_source = QtWid.QLineEdit("0.000", **p)
        self.P_source = QtWid.QLineEdit("0.00" , **p)
        self.pbtn_ENA_PID = create_Toggle_button("OFF",
                                                 minimumHeight=24)
        self.pbtn_ENA_PID.setMinimumWidth(60)

        # Protection
        self.OVP_level = QtWid.QLineEdit("0.000", **p)
        self.pbtn_ENA_OCP = create_Toggle_button("OFF", minimumHeight=24)
        self.pbtn_ENA_OCP.setMinimumWidth(60)

        # Questionable condition status registers
        self.status_QC_OV  = create_tiny_error_LED()
        self.status_QC_OC  = create_tiny_error_LED()
        self.status_QC_PF  = create_tiny_error_LED()
        self.status_QC_OT  = create_tiny_error_LED()
        self.status_QC_INH = create_tiny_error_LED()
        self.status_QC_UNR = create_tiny_error_LED()

        # Operation condition status registers
        self.status_OC_WTG = create_tiny_error_LED()
        self.status_OC_CV  = create_tiny_error_LED()
        self.status_OC_CC  = create_tiny_error_LED()

        # Final elements
        self.errors             = QtWid.QLineEdit('')
        self.errors.setStyleSheet(SS_TEXTBOX_ERRORS)
        self.pbtn_ackn_errors   = QtWid.QPushButton("Acknowledge errors")
        self.pbtn_reinit        = QtWid.QPushButton("Reinitialize")
        self.pbtn_save_defaults = QtWid.QPushButton("Save")
        self.pbtn_debug_test    = QtWid.QPushButton("Debug test")
        self.lbl_update_counter = QtWid.QLabel("0")

        i = 0
        p = {'alignment': QtCore.Qt.AlignLeft + QtCore.Qt.AlignVCenter}

        grid = QtWid.QGridLayout()
        grid.setVerticalSpacing(0)
        grid.addWidget(self.V_meas                       , i, 0, 1, 4); i+=1
        grid.addWidget(self.I_meas                       , i, 0, 1, 4); i+=1
        grid.addWidget(self.P_meas                       , i, 0, 1, 4); i+=1
        grid.addItem(QtWid.QSpacerItem(1, 8)             , i, 0)      ; i+=1
        grid.addWidget(self.pbtn_ENA_output              , i, 0, 1, 4); i+=1

        grid.addItem(QtWid.QSpacerItem(1, 10)            , i, 0)      ; i+=1
        grid.addWidget(QtWid.QLabel("Source:")           , i, 0, 1, 4); i+=1
        grid.addItem(QtWid.QSpacerItem(1, 4)             , i, 0)      ; i+=1
        grid.addWidget(QtWid.QLabel("Voltage")           , i, 0, 1, 2)
        grid.addWidget(self.V_source                     , i, 2)
        grid.addWidget(QtWid.QLabel("V", **p)            , i, 3)      ; i+=1
        grid.addItem(QtWid.QSpacerItem(1, 2)             , i, 0)      ; i+=1
        grid.addWidget(QtWid.QLabel("Current")           , i, 0, 1, 2)
        grid.addWidget(self.I_source                     , i, 2)
        grid.addWidget(QtWid.QLabel("A", **p)            , i, 3)      ; i+=1
        grid.addItem(QtWid.QSpacerItem(1, 2)             , i, 0)      ; i+=1
        grid.addWidget(QtWid.QLabel("Power PID")         , i, 0, 1, 2)
        grid.addWidget(self.pbtn_ENA_PID                 , i, 2,
                                                  QtCore.Qt.AlignLeft); i+=1
        grid.addItem(QtWid.QSpacerItem(1, 2)             , i, 0)      ; i+=1
        grid.addWidget(QtWid.QLabel("Power")             , i, 0, 1, 2)
        grid.addWidget(self.P_source                     , i, 2)
        grid.addWidget(QtWid.QLabel("W", **p)            , i, 3)      ; i+=1

        grid.addItem(QtWid.QSpacerItem(1, 10)            , i, 0)      ; i+=1
        grid.addWidget(QtWid.QLabel("Protection:")       , i, 0, 1, 4); i+=1
        grid.addItem(QtWid.QSpacerItem(1, 4)             , i, 0)      ; i+=1
        grid.addWidget(QtWid.QLabel("OVP")               , i, 0, 1, 2)
        grid.addWidget(self.OVP_level                    , i, 2)
        grid.addWidget(QtWid.QLabel("V", **p)            , i, 3)      ; i+=1
        grid.addItem(QtWid.QSpacerItem(1, 2)             , i, 0)      ; i+=1
        grid.addWidget(QtWid.QLabel("OCP")               , i, 0, 1, 2)
        grid.addWidget(self.pbtn_ENA_OCP                 , i, 2,
                                                  QtCore.Qt.AlignLeft); i+=1

        grid.addItem(QtWid.QSpacerItem(1, 10)            , i, 0)      ; i+=1
        grid.addWidget(self.status_QC_OV                 , i, 0)
        grid.addWidget(QtWid.QLabel("OV")                , i, 1)
        grid.addWidget(QtWid.QLabel("| over-voltage")    , i, 2, 1, 2); i+=1
        grid.addWidget(self.status_QC_OC                 , i, 0)
        grid.addWidget(QtWid.QLabel("OC")                , i, 1)
        grid.addWidget(QtWid.QLabel("| over-current")    , i, 2, 1, 2); i+=1
        grid.addWidget(self.status_QC_PF                 , i, 0)
        grid.addWidget(QtWid.QLabel("PF")                , i, 1)
        grid.addWidget(QtWid.QLabel("| AC power failure"), i, 2, 1, 2); i+=1
        grid.addWidget(self.status_QC_OT                 , i, 0)
        grid.addWidget(QtWid.QLabel("OT")                , i, 1)
        grid.addWidget(QtWid.QLabel("| over-temperature"), i, 2, 1, 2); i+=1
        grid.addWidget(self.status_QC_INH                , i, 0)
        grid.addWidget(QtWid.QLabel("INH")               , i, 1)
        grid.addWidget(QtWid.QLabel("| output inhibited"), i, 2, 1, 2); i+=1
        grid.addWidget(self.status_QC_UNR                , i, 0)
        grid.addWidget(QtWid.QLabel("UNR")               , i, 1)
        grid.addWidget(QtWid.QLabel("| unregulated")     , i, 2, 1, 2); i+=1

        grid.addItem(QtWid.QSpacerItem(1, 10)            , i, 0)      ; i+=1
        grid.addWidget(self.status_OC_WTG                , i, 0)
        grid.addWidget(QtWid.QLabel("WTG")               , i, 1)
        grid.addWidget(QtWid.QLabel("| waiting for trigger"), i, 2, 1, 2); i+=1
        grid.addWidget(self.status_OC_CV                 , i, 0)
        grid.addWidget(QtWid.QLabel("CV")                , i, 1)
        grid.addWidget(QtWid.QLabel("| constant voltage"), i, 2, 1, 2); i+=1
        grid.addWidget(self.status_OC_CC                 , i, 0)
        grid.addWidget(QtWid.QLabel("CC")                , i, 1)
        grid.addWidget(QtWid.QLabel("| constant current"), i, 2, 1, 2); i+=1

        grid.addItem(QtWid.QSpacerItem(1, 10)            , i, 0)      ; i+=1
        grid.addWidget(QtWid.QLabel("Errors")            , i, 0, 1, 2)
        grid.addWidget(self.errors                       , i, 2, 1, 2); i+=1
        grid.addItem(QtWid.QSpacerItem(1, 4)             , i, 0)      ; i+=1
        grid.addWidget(self.pbtn_ackn_errors             , i, 0, 1, 4); i+=1

        hbox = QtWid.QHBoxLayout()
        hbox.addWidget(self.pbtn_save_defaults)
        hbox.addWidget(self.pbtn_reinit)
        grid.addLayout(hbox                              , i, 0, 1, 4); i+=1
        grid.addItem(QtWid.QSpacerItem(1, 4)             , i, 0)      ; i+=1
        grid.addWidget(self.lbl_update_counter           , i, 0, 1, 4); i+=1
        #grid.addWidget(self.pbtn_debug_test              , i, 0, 1, 4); i+=1

        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 0)
        grid.setColumnStretch(2, 0)
        grid.setColumnStretch(3, 1)
        grid.setAlignment(QtCore.Qt.AlignTop)
        #grid.setAlignment(QtCore.Qt.AlignLeft)

        self.grpb.setLayout(grid)

    # --------------------------------------------------------------------------
    #   update_GUI
    # --------------------------------------------------------------------------

    @QtCore.pyqtSlot()
    def update_GUI(self):
        """NOTE: 'self.dev.mutex' is not being locked, because we are only
        reading 'state' for displaying purposes. We can do this because 'state'
        members are written and read atomicly, with the only exception being
        'all_errors', and it bears no consequences to read wrongly.
        Not locking the mutex might speed up the program.
        """
        if self.dev.is_alive:
            if self.dev.state.ENA_PID:
                self.pbtn_ENA_PID.setChecked(True)
                self.pbtn_ENA_PID.setText("ON")
                self.V_source.setReadOnly(True)
                self.V_source.setText("%.2f" % self.dev.state.V_source)
            else:
                self.pbtn_ENA_PID.setChecked(False)
                self.pbtn_ENA_PID.setText("OFF")
                self.V_source.setReadOnly(False)

            if (self.dev.state.status_QC_INH):
                self.V_meas.setText("")
                self.I_meas.setText("Inhibited")
                self.I_meas.setAlignment(QtCore.Qt.AlignCenter)
                self.P_meas.setText("")
            else:
                self.V_meas.setText("%.2f  V   " % self.dev.state.V_meas)
                self.I_meas.setText("%.3f A   "  % self.dev.state.I_meas)
                self.I_meas.setAlignment(QtCore.Qt.AlignRight)
                self.P_meas.setText("%.2f  W   " % self.dev.state.P_meas)

            self.pbtn_ENA_output.setChecked(self.dev.state.ENA_output)
            if self.pbtn_ENA_output.isChecked():
                self.pbtn_ENA_output.setText("Output ON")
            else:
                self.pbtn_ENA_output.setText("Output OFF")

            self.pbtn_ENA_OCP.setChecked(self.dev.state.ENA_OCP)
            if self.pbtn_ENA_OCP.isChecked():
                self.pbtn_ENA_OCP.setText("ON")
            else:
                self.pbtn_ENA_OCP.setText("OFF")

            self.status_QC_OV.setChecked(self.dev.state.status_QC_OV)
            self.status_QC_OC.setChecked(self.dev.state.status_QC_OC)
            self.status_QC_PF.setChecked(self.dev.state.status_QC_PF)
            self.status_QC_OT.setChecked(self.dev.state.status_QC_OT)
            self.status_QC_INH.setChecked(self.dev.state.status_QC_INH)
            self.status_QC_UNR.setChecked(self.dev.state.status_QC_UNR)

            self.status_OC_WTG.setChecked(self.dev.state.status_OC_WTG)
            self.status_OC_CV.setChecked(self.dev.state.status_OC_CV)
            self.status_OC_CC.setChecked(self.dev.state.status_OC_CC)

            self.errors.setReadOnly(self.dev.state.all_errors != [])
            self.errors.setText("%s" % ';'.join(self.dev.state.all_errors))

            self.lbl_update_counter.setText("%s" % self.dev.update_counter)
        else:
            self.V_meas.setText("")
            self.I_meas.setText("Offline")
            self.I_meas.setAlignment(QtCore.Qt.AlignCenter)
            self.P_meas.setText("")
            self.grpb.setEnabled(False)

    # --------------------------------------------------------------------------
    #   update_GUI_input_field
    # --------------------------------------------------------------------------

    @QtCore.pyqtSlot()
    @QtCore.pyqtSlot(int)
    def update_GUI_input_field(self, GUI_input_field=GUI_input_fields.ALL):
        if GUI_input_field == GUI_input_fields.OVP_level:
            self.OVP_level.setText("%.2f" % self.dev.state.OVP_level)
            self.dev.PID_power.set_output_limits(0,
                                                 self.dev.state.OVP_level*.95)

        elif GUI_input_field == GUI_input_fields.V_source:
            self.V_source.setText("%.2f" % self.dev.state.V_source)

        elif GUI_input_field == GUI_input_fields.I_source:
            self.I_source.setText("%.3f" % self.dev.state.I_source)

        elif GUI_input_field == GUI_input_fields.P_source:
            self.P_source.setText("%.2f" % self.dev.state.P_source)

        else:
            self.OVP_level.setText("%.2f" % self.dev.state.OVP_level)
            self.dev.PID_power.set_output_limits(0,
                                                 self.dev.state.OVP_level*.95)

            self.V_source.setText("%.2f" % self.dev.state.V_source)
            self.I_source.setText("%.3f" % self.dev.state.I_source)
            self.P_source.setText("%.2f" % self.dev.state.P_source)

    # --------------------------------------------------------------------------
    #   GUI functions
    # --------------------------------------------------------------------------

    def process_pbtn_ENA_output(self):
        if self.pbtn_ENA_output.isChecked():
            # Clear output protection, if triggered and turn on output
            self.worker_send.queue.put(
                    (self.dev.clear_output_protection_and_turn_on,))
        else:
            # Turn off output
            self.worker_send.queue.put((self.dev.turn_off,))

    def process_pbtn_ENA_PID(self):
        self.dev.state.ENA_PID = self.pbtn_ENA_PID.isChecked()

    def process_pbtn_ENA_OCP(self):
        self.worker_send.queue.put((self.dev.set_ENA_OCP,
                                    self.pbtn_ENA_OCP.isChecked()))

    def process_pbtn_ackn_errors(self):
        # Lock the dev mutex because string operations are not atomic
        locker = QtCore.QMutexLocker(self.dev.mutex)
        self.dev.state.all_errors = []
        self.errors.setText('')
        self.errors.setReadOnly(False)   # To change back to regular colors

    def process_pbtn_reinit(self):
        str_msg = ("Are you sure you want reinitialize the power supply?")
        reply = QtWid.QMessageBox.question(None,
                ("Reinitialize %s" % self.dev.name), str_msg,
                QtWid.QMessageBox.Yes | QtWid.QMessageBox.No,
                QtWid.QMessageBox.No)

        if reply == QtWid.QMessageBox.Yes:
            self.dev.read_config_file()
            self.worker_send.queue.put((self.dev.reinitialize,))
            self.worker_send.queue.put(("signal_GUI_input_field_update",
                                        GUI_input_fields.ALL))

            self.dev.state.ENA_PID = False

    def process_pbtn_save_defaults(self):
        str_title = "Save defaults %s"  % self.dev.name
        str_msg = ("Are you sure you want to save the current values:\n\n"
                   "  - Source voltage\n"
                   "  - Source current\n"
                   "  - Source power\n"
                   "  - OVP\n"
                   "  - OCP\n\n"
                   "as default?\n"
                   "These will then automatically be loaded next time.")
        reply = QtWid.QMessageBox.question(None, str_title, str_msg,
                                           QtWid.QMessageBox.Yes |
                                           QtWid.QMessageBox.No,
                                           QtWid.QMessageBox.No)

        if reply == QtWid.QMessageBox.Yes:
            if (self.dev.write_config_file()):
                QtWid.QMessageBox.information(None, str_title,
                    "Successfully saved to disk:\n%s" %
                    self.dev.path_config)
            else:
                QtWid.QMessageBox.critical(None, str_title,
                    "Failed to save to disk:\n%s" % self.dev.path_config)

    def process_pbtn_debug_test(self):
        pass

    def send_V_source_from_textbox(self):
        try:
            voltage = float(self.V_source.text())
        except (TypeError, ValueError):
            voltage = 0.0
        except:
            raise()

        if (voltage < 0): voltage = 0

        self.worker_send.queue.put((self.dev.set_V_source, voltage))
        self.worker_send.queue.put((self.dev.query_V_source,))
        self.worker_send.queue.put(("signal_GUI_input_field_update",
                                    GUI_input_fields.V_source))

    def send_I_source_from_textbox(self):
        try:
            current = float(self.I_source.text())
        except (TypeError, ValueError):
            current = 0.0
        except:
            raise()

        if (current < 0): current = 0

        self.worker_send.queue.put((self.dev.set_I_source, current))
        self.worker_send.queue.put((self.dev.query_I_source,))
        self.worker_send.queue.put(("signal_GUI_input_field_update",
                                    GUI_input_fields.I_source))

    def set_P_source_from_textbox(self):
        try:
            power = float(self.P_source.text())
        except (TypeError, ValueError):
            power = 0.0
        except:
            raise()

        if (power < 0): power = 0
        self.dev.state.P_source = power
        self.update_GUI_input_field(GUI_input_fields.P_source)

    def send_OVP_level_from_textbox(self):
        try:
            OVP_level = float(self.OVP_level.text())
        except (TypeError, ValueError):
            OVP_level = 0.0
        except:
            raise()

        self.worker_send.queue.put((self.dev.set_OVP_level, OVP_level))
        self.worker_send.queue.put((self.dev.query_OVP_level,))
        self.worker_send.queue.put(("signal_GUI_input_field_update",
                                    GUI_input_fields.OVP_level))

    # --------------------------------------------------------------------------
    #   connect_signals_to_slots
    # --------------------------------------------------------------------------

    def connect_signals_to_slots(self):
        self.pbtn_ENA_output.clicked.connect(self.process_pbtn_ENA_output)
        self.pbtn_ENA_PID.clicked.connect(self.process_pbtn_ENA_PID)
        self.pbtn_ENA_OCP.clicked.connect(self.process_pbtn_ENA_OCP)
        self.pbtn_ackn_errors.clicked.connect(self.process_pbtn_ackn_errors)
        self.pbtn_reinit.clicked.connect(self.process_pbtn_reinit)
        self.pbtn_save_defaults.clicked.connect(self.process_pbtn_save_defaults)
        self.pbtn_debug_test.clicked.connect(self.process_pbtn_debug_test)

        self.V_source.editingFinished.connect(self.send_V_source_from_textbox)
        self.I_source.editingFinished.connect(self.send_I_source_from_textbox)
        self.P_source.editingFinished.connect(self.set_P_source_from_textbox)
        self.OVP_level.editingFinished.connect(self.send_OVP_level_from_textbox)

        self.worker_state.signal_GUI_update.connect(self.update_GUI)
        self.worker_send.signal_GUI_input_field_update.connect(
                self.update_GUI_input_field)

    # --------------------------------------------------------------------------
    #   Worker_send
    # --------------------------------------------------------------------------

    class Worker_send(QtCore.QObject):
        """No changes to the GUI are allowed inside this class!
        """
        signal_GUI_input_field_update = QtCore.pyqtSignal(int)

        def __init__(self, dev: N8700_functions.PSU, DEBUG_color=ANSI.YELLOW):
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

                    if (func == "signal_GUI_input_field_update"):
                        # Special instruction
                        if DEBUG:
                            dprint("Worker_send  %s: %s %s" %
                                   (self.dev.name, func, args),
                                   self.DEBUG_color)
                        self.signal_GUI_input_field_update.emit(*args)
                    else:
                        # Send I/O operation to the PSU device
                        if DEBUG:
                            dprint("Worker_send  %s: %s %s" %
                                   (self.dev.name, func.__name__, args),
                                   self.DEBUG_color)
                        locker = QtCore.QMutexLocker(self.dev.mutex)
                        func(*args)
                        self.dev.wait_for_OPC()
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
        """This Worker will read the status and readings of the PSU whenever the
        thread is woken up from sleep by calling 'self.qwc.wakeAll()'.
        No changes to the GUI are allowed inside this class!
        """
        signal_GUI_update = QtCore.pyqtSignal()
        #connection_lost = QtCore.pyqtSignal()

        def __init__(self, dev: N8700_functions.PSU, DEBUG_color=ANSI.YELLOW):
            super().__init__(None)

            self.dev = dev
            self.dev.update_counter = 0
            self.qwc = QtCore.QWaitCondition()
            self.mutex_wait = QtCore.QMutex()
            self.running = True

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

            while self.running:
                locker_wait = QtCore.QMutexLocker(self.mutex_wait)

                if DEBUG:
                    dprint("Worker_state %s: waiting for trigger" %
                           self.dev.name, self.DEBUG_color)

                self.qwc.wait(self.mutex_wait)
                self.dev.update_counter += 1

                if DEBUG:
                    dprint("Worker_state %s: iter %i" %
                           (self.dev.name, self.dev.update_counter),
                           self.DEBUG_color)

                #tick = time.time()

                locker_dev = QtCore.QMutexLocker(self.dev.mutex)

                #locker_dev.unlock(); locker_dev.unlock()
                self.dev.wait_for_OPC()
                self.dev.query_V_meas()

                #locker_dev.unlock(); locker_dev.relock()
                self.dev.wait_for_OPC()
                self.dev.query_I_meas()

                self.dev.wait_for_OPC()

                # --------------------------------------------------------------
                #   Heater power PID
                # --------------------------------------------------------------
                # PID controllers work best when the process and control
                # variables have a linear relationship.
                # Here:
                #   Process var: V (voltage)
                #   Control var: P (power)
                #   Relation   : P = R / V^2
                #
                # Hence, we transform P into P_star
                #   Control var: P_star = sqrt(P)
                #   Relation   : P_star = sqrt(R) / V
                # When we assume R remains constant (which is not the case as
                # the resistance is a function of the heater temperature, but
                # the dependence is expected to be insignificant in our small
                # temperature range of 20 to 100 deg C), we now have linearized
                # the PID feedback relation.

                self.dev.PID_power.set_mode((self.dev.state.ENA_output and
                                             self.dev.state.ENA_PID),
                                            self.dev.state.P_meas,
                                            self.dev.state.V_source)

                self.dev.PID_power.setpoint = np.sqrt(self.dev.state.P_source)
                if self.dev.PID_power.compute(np.sqrt(self.dev.state.P_meas)):
                    # New PID output got computed -> send new voltage to PSU
                    if self.dev.PID_power.output < 1:
                        # Power supply does not regulate well below 1 V,
                        # hence clamp to 0
                        self.dev.PID_power.output = 0
                    self.dev.set_V_source(self.dev.PID_power.output)
                    self.dev.wait_for_OPC()

                self.dev.wait_for_OPC(); self.dev.query_ENA_OCP()
                self.dev.wait_for_OPC(); self.dev.query_status_OC()
                self.dev.wait_for_OPC(); self.dev.query_status_QC()
                self.dev.wait_for_OPC(); self.dev.query_ENA_output()
                self.dev.wait_for_OPC()

                # Explicitly force the output state to off when the output got
                # disabled on a hardware level by a triggered protection or
                # fault.
                if self.dev.state.ENA_output & (self.dev.state.status_QC_OV |
                                                self.dev.state.status_QC_OC |
                                                self.dev.state.status_QC_PF |
                                                self.dev.state.status_QC_OT |
                                                self.dev.state.status_QC_INH):
                    self.dev.state.ENA_output = False
                    self.dev.set_ENA_output(False)

                # Check if there are errors in the device queue and retrieve all
                # if any and append these to 'dev.state.all_errors'.
                #locker_dev.unlock(); locker_dev.relock()
                self.dev.query_all_errors_in_queue()

                locker_dev.unlock()
                locker_wait.unlock()

                # DEBUG info
                #print("%s done in %.3f s" % (self.dev.name, time.time() - tick))

                self.signal_GUI_update.emit()

                # TO DO: check for connection lost
                #self.connection_lost.emit()

            if DEBUG:
                dprint("Worker_state %s: done running" % self.dev.name,
                       self.DEBUG_color)

        @QtCore.pyqtSlot()
        def stop(self):
            self.running = False

            # Must make sure to take 'Worker_state.run' out of a suspended
            # state in order to have it stop correctly.
            self.qwc.wakeAll()

    # --------------------------------------------------------------------------
    #   close_threads
    # --------------------------------------------------------------------------

    def close_threads(self):
        # Close thread_state
        if self.thread_state is not None:
            thread_name = self.thread_state.objectName()
            self.worker_state.stop()
            self.thread_state.quit()
            print("Closing thread %-13s: " % thread_name, end='')
            if self.thread_state.wait(2000):
                print("done.\n", end='')
            else:
                print("FAILED.\n", end='')

        # Close thread_send
        if self.thread_send is not None:
            thread_name = self.thread_send.objectName()
            self.worker_send.stop()
            self.thread_send.quit()
            print("Closing thread %-13s: " % thread_name, end='')
            if self.thread_send.wait(2000):
                print("done.\n", end='')
            else:
                print("FAILED.\n", end='')
