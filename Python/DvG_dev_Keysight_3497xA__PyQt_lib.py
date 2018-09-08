#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dennis van Gils
14-06-2018
"""

import queue
#import time

#import logging
#logging.basicConfig(filename='debug_info.log', level=logging.INFO)

from PyQt5 import QtCore, QtGui
from PyQt5 import QtWidgets as QtWid
from PyQt5.QtCore import QDateTime

from DvG_debug_functions import ANSI, dprint
from DvG_PyQt_controls import (create_Toggle_button,
                               SS_TEXTBOX_ERRORS,
                               SS_TEXTBOX_READ_ONLY,
                               SS_GROUP)
import DvG_dev_Keysight_3497xA__fun_SCPI as K3497xA_functions

# Show debug info in terminal? Warning: slow! Do not leave on unintentionally.
DEBUG = False

# Short-hand aliases for DEBUG information
curThread = QtCore.QThread.currentThread
get_tick = QDateTime.currentDateTime

# Monospace font
FONT_MONOSPACE = QtGui.QFont("Monospace", 12, weight=QtGui.QFont.Bold)
FONT_MONOSPACE.setStyleHint(QtGui.QFont.TypeWriter)

FONT_MONOSPACE_SMALL = QtGui.QFont("Monospace", 9)
FONT_MONOSPACE_SMALL.setStyleHint(QtGui.QFont.TypeWriter)

# Infinity cap: values reported by the 3497xA greater than this will be
# displayed as 'inf'
INFINITY_CAP = 9.8e37

# ------------------------------------------------------------------------------
#   K3497xA_pyqt
# ------------------------------------------------------------------------------

class K3497xA_pyqt(QtWid.QWidget):
    """Collection of PyQt related functions and objects to provide a GUI and
    automated data transmission/acquisition for a HP/Agilent/Keysight 34970A/
    34972A data acquisition/switch unit, from now on referred to as the
    'device' or 'mux' (multiplexer).

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
            Periodically perform a scan cycle of the mux.
    """

    def __init__(self, dev: K3497xA_functions.K3497xA,
                 scanning_interval_ms=1000,
                 DEBUG_color=ANSI.YELLOW,
                 parent=None):
        super(K3497xA_pyqt, self).__init__(parent=parent)

        # Store reference to 'K3497xA_functions.K3497xA()' instance
        self.dev = dev

        # Create mutex for proper multithreading
        self.dev.mutex = QtCore.QMutex()

        # Terminal text color for DEBUG information
        self.DEBUG_color = DEBUG_color

        # Periodically query the device for its state.
        # !! To be put in a seperate thread !!
        self.worker_state = self.Worker_state(dev, scanning_interval_ms,
                                              DEBUG_color)

        # Maintains a queue where desired device I/O operations can be put on
        # the stack. The worker will periodically send out the operations to the
        # device as scheduled in the queue.
        # !! To be put in a seperate thread !!
        self.worker_send = self.Worker_send(dev, DEBUG_color)

        # String format to use for the readings in the table widget
        # When type is a single string, all rows will use this format.
        # When type is a list of strings, rows will be formatted consecutively.
        self.table_readings_format = "%.3e"

        # Create the block of GUI elements for the device. The main QWidget
        # object is of type QGroupBox and resides at 'self.grpb'
        self.create_GUI()
        self.connect_signals_to_slots()

        # Populate the table view with QTableWidgetItems.
        # I.e. add the correct number of rows to the table depending on the
        # full scan list.
        self.populate_table_widget()

        # Populate the textbox with the SCPI setup commands
        self.populate_SCPI_commands()

        # Update GUI immediately, instead of waiting for the first refresh
        self.update_GUI()

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
        #  Groupbox containing 'front-panel' controls
        # --------------------------------------------
        self.grpb = QtWid.QGroupBox(self)
        self.grpb.setTitle(self.dev.name)
        self.grpb.setStyleSheet(SS_GROUP)

        p = {'alignment': QtCore.Qt.AlignCenter,
             'font': FONT_MONOSPACE}
        p2 = {'alignment': QtCore.Qt.AlignCenter + QtCore.Qt.AlignVCenter}
        #self.lbl_mux = QtWid.QLabel("Keysight 34972a", **p2)
        self.lbl_mux_state = QtWid.QLabel("Offline", **p)
        self.pbtn_start_scan = create_Toggle_button("Start scan")

        self.SCPI_commands = QtWid.QPlainTextEdit('', readOnly=True,
                                                  lineWrapMode=False)
        self.SCPI_commands.setStyleSheet(SS_TEXTBOX_READ_ONLY)
        self.SCPI_commands.setMaximumHeight(152)
        self.SCPI_commands.setMinimumWidth(200)
        self.SCPI_commands.setFont(FONT_MONOSPACE_SMALL)

        p = {'alignment': QtCore.Qt.AlignRight, 'readOnly': True}
        self.scanning_interval_ms = QtWid.QLineEdit("", **p)
        self.obtained_interval_ms = QtWid.QLineEdit("", **p)

        self.errors = QtWid.QPlainTextEdit('', lineWrapMode=False)
        self.errors.setStyleSheet(SS_TEXTBOX_ERRORS)
        self.errors.setMaximumHeight(90)

        self.pbtn_ackn_errors   = QtWid.QPushButton("Acknowledge errors")
        self.pbtn_reinit        = QtWid.QPushButton("Reinitialize")
        self.lbl_update_counter = QtWid.QLabel("0")
        self.pbtn_debug_test    = QtWid.QPushButton("Debug test")

        i = 0
        p  = {'alignment': QtCore.Qt.AlignLeft + QtCore.Qt.AlignVCenter}

        grid = QtWid.QGridLayout()
        grid.setVerticalSpacing(4)
        #grid.addWidget(self.lbl_mux                       , i, 0, 1, 3); i+=1
        grid.addWidget(QtWid.QLabel("Only scan when necessary.", **p2)
                                                          , i, 0, 1, 2); i+=1
        grid.addWidget(QtWid.QLabel("It wears down the multiplexer.", **p2)
                                                          , i, 0, 1, 2); i+=1
        grid.addItem(QtWid.QSpacerItem(1, 3)              , i, 0)      ; i+=1
        grid.addWidget(self.lbl_mux_state                 , i, 0, 1, 2); i+=1
        grid.addItem(QtWid.QSpacerItem(1, 3)              , i, 0)      ; i+=1
        grid.addWidget(self.pbtn_start_scan               , i, 0, 1, 2); i+=1
        grid.addItem(QtWid.QSpacerItem(1, 4)              , i, 0)      ; i+=1
        grid.addWidget(QtWid.QLabel("SCPI scan commands:"), i, 0, 1, 2); i+=1
        grid.addWidget(self.SCPI_commands                 , i, 0, 1, 2); i+=1
        grid.addWidget(QtWid.QLabel("Scanning interval [ms]"), i, 0)
        grid.addWidget(self.scanning_interval_ms          , i, 1)      ; i+=1
        grid.addWidget(QtWid.QLabel("Obtained [ms]")      , i, 0)
        grid.addWidget(self.obtained_interval_ms          , i, 1)      ; i+=1
        grid.addWidget(self.pbtn_reinit                   , i, 0, 1, 2); i+=1
        grid.addItem(QtWid.QSpacerItem(1, 12)             , i, 0)      ; i+=1
        grid.addWidget(QtWid.QLabel("Errors:")            , i, 0, 1, 2); i+=1
        grid.addWidget(self.errors                        , i, 0, 1, 2); i+=1
        grid.addWidget(self.pbtn_ackn_errors              , i, 0, 1, 2); i+=1
        grid.addWidget(self.lbl_update_counter            , i, 0, 1, 2); i+=1
        #grid.addWidget(self.pbtn_debug_test               , i, 0, 1, 2); i+=1

        #  Table widget containing the readings of the current scan cycle
        # ----------------------------------------------------------------
        self.table_readings = QtWid.QTableWidget(columnCount=1)
        self.table_readings.setHorizontalHeaderLabels(["Readings"])
        self.table_readings.horizontalHeaderItem(0).setFont(FONT_MONOSPACE_SMALL)
        self.table_readings.verticalHeader().setFont(FONT_MONOSPACE_SMALL)
        self.table_readings.verticalHeader().setDefaultSectionSize(24);
        self.table_readings.setFont(FONT_MONOSPACE_SMALL)
        #self.table_readings.setMinimumHeight(600)
        self.table_readings.setFixedWidth(180)
        self.table_readings.setColumnWidth(0, 100)

        grid.addWidget(self.table_readings, 0, 2, i, 1)

        self.grpb.setLayout(grid)

    # --------------------------------------------------------------------------
    #   populate_SCPI_commands
    # --------------------------------------------------------------------------

    def populate_SCPI_commands(self):
        self.SCPI_commands.setPlainText("%s" %
                                        '\n'.join(self.dev.SCPI_setup_commands))
        self.scanning_interval_ms.setText("%i" %
                                          self.worker_state.scanning_interval_ms)

    # --------------------------------------------------------------------------
    #   Table widget related
    # --------------------------------------------------------------------------

    def populate_table_widget(self):
        self.table_readings.setRowCount(len(
                self.dev.state.all_scan_list_channels))
        self.table_readings.setVerticalHeaderLabels(
                self.dev.state.all_scan_list_channels)

        for i in range(len(self.dev.state.all_scan_list_channels)):
            item = QtWid.QTableWidgetItem("nan")
            item.setTextAlignment(QtCore.Qt.AlignRight + QtCore.Qt.AlignCenter)
            self.table_readings.setItem(i, 0, item)

    def set_table_readings_format(self, format_str):
        # String format to use for the readings in the table widget
        # When type is a single string, all rows will use this format.
        # When type is a list of strings, rows will be formatted consecutively.
        self.table_readings_format = format_str

    # --------------------------------------------------------------------------
    #   update_GUI
    # --------------------------------------------------------------------------

    @QtCore.pyqtSlot()
    def update_GUI(self):
        """NOTE: 'self.dev.mutex' is not being locked, because we are only
        reading 'state' for displaying purposes. We can do this because 'state'
        members are written and read atomicly, with the only exception being
        'str_all_errors', and it bears no consequences to read wrongly.
        Not locking the mutex might speed up the program.
        """
        if self.dev.is_alive:
            if (self.worker_state.ENA_periodic_scanning):
                self.lbl_mux_state.setText("Scanning")
                self.pbtn_start_scan.setChecked(True)
            else:
                self.lbl_mux_state.setText("Idle")
                self.pbtn_start_scan.setChecked(False)

            self.errors.setReadOnly(self.dev.state.all_errors != [])
            self.errors.setStyleSheet(SS_TEXTBOX_ERRORS)
            self.errors.setPlainText("%s" %
                                     '\n'.join(self.dev.state.all_errors))

            self.obtained_interval_ms.setText(
                    "%i" % self.worker_state.obtained_scanning_interval_ms)
            self.lbl_update_counter.setText("%s" % self.dev.update_counter)

            for i in range(len(self.dev.state.all_scan_list_channels)):
                if i >= len(self.dev.state.readings):
                    break
                reading = self.dev.state.readings[i]
                if reading > INFINITY_CAP:
                    self.table_readings.item(i, 0).setData(
                            QtCore.Qt.DisplayRole, "Inf")
                else:
                    if type(self.table_readings_format) == list:
                        try:
                            str_format = self.table_readings_format[i]
                        except IndexError:
                            str_format = self.table_readings_format[0]
                    elif type(self.table_readings_format) == str:
                        str_format = self.table_readings_format

                    self.table_readings.item(i, 0).setData(
                            QtCore.Qt.DisplayRole, str_format % reading)
        else:
            self.lbl_mux_state.setText("Offline")
            self.grpb.setEnabled(False)

    # --------------------------------------------------------------------------
    #   GUI functions
    # --------------------------------------------------------------------------

    def process_pbtn_start_scan(self):
        if self.pbtn_start_scan.isChecked():
            self.worker_state.start_scanning()
        else:
            self.worker_state.stop_scanning()

    def process_pbtn_ackn_errors(self):
        # Lock the dev mutex because string operations are not atomic
        locker = QtCore.QMutexLocker(self.dev.mutex)
        self.dev.state.all_errors = []
        self.errors.setPlainText('')
        self.errors.setReadOnly(False)   # To change back to regular colors

    def process_pbtn_reinit(self):
        str_msg = ("Are you sure you want reinitialize the multiplexer?\n\n"
                   "This would abort the current scan, reset the device\n"
                   "and resend the SCPI scan command list.")
        reply = QtWid.QMessageBox.question(None,
                ("Reinitialize %s" % self.dev.name), str_msg,
                QtWid.QMessageBox.Yes | QtWid.QMessageBox.No,
                QtWid.QMessageBox.No)

        if reply == QtWid.QMessageBox.Yes:
            self.pbtn_start_scan.setChecked(False)
            self.worker_state.stop_scanning()
            self.worker_send.queue.put((self.dev.wait_for_OPC,))
            self.worker_send.queue.put((self.dev.begin,))

    def process_pbtn_debug_test(self):
        self.worker_send.queue.put((self.dev.write, "blabla"))

    # --------------------------------------------------------------------------
    #   connect_signals_to_slots
    # --------------------------------------------------------------------------

    def connect_signals_to_slots(self):
        self.pbtn_start_scan.clicked.connect(self.process_pbtn_start_scan)
        self.pbtn_ackn_errors.clicked.connect(self.process_pbtn_ackn_errors)
        self.pbtn_reinit.clicked.connect(self.process_pbtn_reinit)
        self.pbtn_debug_test.clicked.connect(self.process_pbtn_debug_test)

        self.worker_state.signal_GUI_update.connect(self.update_GUI)

    # --------------------------------------------------------------------------
    #   Worker_send
    # --------------------------------------------------------------------------

    class Worker_send(QtCore.QObject):
        """No changes to the GUI are allowed inside this class!
        """

        def __init__(self, dev: K3497xA_functions.K3497xA,
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

                    # Send I/O operation to the device
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
        """This Worker will periodically query the device for errors and it will
        periodically perform scans of the mux as soon as 'start_scanning' has
        been called.
        No changes to the GUI are allowed inside this class!
        """
        signal_GUI_update = QtCore.pyqtSignal()
        #connection_lost = QtCore.pyqtSignal()

        def __init__(self, dev: K3497xA_functions.K3497xA,
                     scanning_interval_ms=1000,
                     DEBUG_color=ANSI.CYAN):
            super().__init__(None)

            self.dev = dev
            self.dev.update_counter = 0
            self.scanning_interval_ms = scanning_interval_ms

            # Additional and optional function to be run when this Worker is
            # performing the 'update' method.
            # This can be used to e.g. parse the recently fetched scan data
            # and/or perform data validity checks asap or add data points to
            # chart arrays.
            # No changes to the GUI are allowed inside this function!
            # [None]: no additional function will be run.
            # [Function handle]: this function will be invoked.
            self.external_function_to_run_in_update = None

            # Keep track of the effective scanning interval
            self.obtained_scanning_interval_ms = 0
            self.prev_time_of_scan = QDateTime.currentDateTime()

            # Is continuous periodic scanning switched on?
            self.ENA_periodic_scanning = False

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
            self.timer.setInterval(self.scanning_interval_ms)
            self.timer.timeout.connect(self.update)
            self.timer.start()

        @QtCore.pyqtSlot()
        def start_scanning(self):
            # Recreate the worker timer and acquire new samples immediately,
            # instead of waiting for the next tick to occur of the 'old' timer

            # Note: Would love to stop the old timer first, but for some strange
            # reason the very first Qtimer appears to be running in another
            # thread than the 'worker_state' thread, eventhough the routine in
            # K3497xA_pyqt.__init__ has finished moving the worker_state thread.
            # When timer is running in another thread than 'this' one, an
            # exception is thrown py Python saying we can't stop the timer from
            # another thread. Hence, I reassign a new Qtimer and hope that the
            # old timer is garbage collected all right.
            #self.timer.stop()  # Note: does not work 100% of the time

            self.ENA_periodic_scanning = True
            self.signal_GUI_update.emit()           # Show we are scanning
            QtWid.QApplication.processEvents()

            """
            # NOTE: disabled the recreation of the timer, because of not
            # understood behavior. The first time iteration of every newly
            # created QTimer seems to be running in the MAIN thread while
            # subsequent iterations take place in the Worker_state thread.
            # This might lead to program instability? Not sure. Simply disabled
            # for now.
            self.timer = QtCore.QTimer()            # Create new timer
            self.timer.setInterval(self.scanning_interval_ms)
            self.timer.timeout.connect(self.update)
            self.timer.start()

            self.update()  # Kickstart at t = 0, because timer doesn't fire now
            """

        @QtCore.pyqtSlot()
        def stop_scanning(self):
            self.ENA_periodic_scanning = False
            self.signal_GUI_update.emit()           # Show we stopped scanning
            QtWid.QApplication.processEvents()

        def update(self):
            DEBUG_LOCAL = False
            self.dev.update_counter += 1

            # Keep track of the effective scanning interval
            tick = get_tick()
            self.obtained_scanning_interval_ms = (
                    self.prev_time_of_scan.msecsTo(tick))
            self.prev_time_of_scan = tick

            if DEBUG:
                dprint("Worker_state %s: iter %i" %
                       (self.dev.name, self.dev.update_counter),
                       self.DEBUG_color)

            if DEBUG_LOCAL:
                tick = get_tick()
                dprint(self.dev.update_counter)
                #logging.info(self.dev.update_counter)
                #logging.info(tick.toString("yyMMdd_HHmmss"))

            locker = QtCore.QMutexLocker(self.dev.mutex)
            if DEBUG_LOCAL:
                tock = get_tick()
                dprint("lock in: %i" % tick.msecsTo(tock))
                #logging.info("lock in: %i" % tick.msecsTo(tock))
                tick = tock

            # Clear input and output buffers of the device. Seems to resolve
            # intermittent communication time-outs.
            self.dev.device.clear()

            success = True
            if self.ENA_periodic_scanning:
                success &= self.dev.init_scan()
                if DEBUG_LOCAL:
                    tock = get_tick();
                    dprint("init in: %i" % tick.msecsTo(tock))
                    #logging.info("init in: %i" % tick.msecsTo(tock))
                    tick = tock

                if success:
                    self.dev.wait_for_OPC()
                    if DEBUG_LOCAL:
                        tock = get_tick()
                        dprint("opc? in: %i" % tick.msecsTo(tock))
                        #logging.info("opc? in: %i" % tick.msecsTo(tock))
                        tick = tock

                    success &= self.dev.fetch_scan()
                    if DEBUG_LOCAL:
                        tock = get_tick()
                        dprint("fetc in: %i" % tick.msecsTo(tock))
                        #logging.info("fetc in: %i" % tick.msecsTo(tock))
                        tick = tock

                if success:
                    self.dev.wait_for_OPC()
                    if DEBUG_LOCAL:
                        tock = get_tick()
                        dprint("opc? in: %i" % tick.msecsTo(tock))
                        #logging.info("opc? in: %i" % tick.msecsTo(tock))
                        tick = tock

            if success:
                # Do not throw additional timeout exceptions when
                # .init_scan() might have already failed. Hence this check
                # for no success.
                self.dev.query_all_errors_in_queue()
                if DEBUG_LOCAL:
                    tock = get_tick()
                    dprint("err? in: %i" % tick.msecsTo(tock))
                    #logging.info("err? in: %i" % tick.msecsTo(tock))
                    tick = tock

                # The next statement seems to trigger timeout, but very
                # intermittently (~once per 20 minutes). After this timeout,
                # everything times out.
                #self.dev.wait_for_OPC()
                #if DEBUG_LOCAL:
                #    dprint("opc? in: %i" %
                #           tick.msecsTo(QDateTime.currentDateTime()))
                #    tick = QDateTime.currentDateTime()

                # NOTE: Another work-around to intermittent time-outs might
                # be sending device.clear() every iter to clear the input and
                # output buffers

            # Additional and optional external function to be run
            if self.external_function_to_run_in_update is not None:
                self.external_function_to_run_in_update()

            if DEBUG_LOCAL:
                tock = get_tick()
                dprint("extf in: %i" % tick.msecsTo(tock))
                #logging.info("extf in: %i" % tick.msecsTo(tock))
                tick = tock

            locker.unlock()

            if DEBUG_LOCAL:
                if self.obtained_scanning_interval_ms > 1500:
                    color = ANSI.RED
                    #logging.info("WARNING:WARNING %i\n" %
                    #             self.obtained_scanning_interval_ms)
                else:
                    color = ANSI.WHITE
                    #logging.info("%i\n" % self.obtained_scanning_interval_ms)
                dprint("%i\n" % self.obtained_scanning_interval_ms, color)

            """
            if not success:
                # Connection lost
                # NOTE: NOT YET IMPLEMENTED
                self.connection_lost.emit()
                return
            """

            self.signal_GUI_update.emit()

    # --------------------------------------------------------------------------
    #   close_threads
    # --------------------------------------------------------------------------

    def close_threads(self):
        # Close thread_state
        if self.thread_state is not None:
            thread_name = self.thread_state.objectName()
            self.thread_state.quit()
            print("Closing thread %-13s: " % thread_name, end='')
            if self.thread_state.wait(5000):
                print("done.\n", end='')
            else:
                print("FAILED.\n", end='')

        # Close thread_send
        if self.thread_send is not None:
            thread_name = self.thread_send.objectName()
            self.worker_send.stop()
            self.thread_send.quit()
            print("Closing thread %-13s: " % thread_name, end='')
            if self.thread_send.wait(5000):
                print("done.\n", end='')
            else:
                print("FAILED.\n", end='')
