#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PyQt5 module to provide multithreaded communication and periodical data
acquisition for the two Arduino devices running the Twente MHT Tunnel.
"""
__author__      = "Dennis van Gils"
__authoremail__ = "vangils.dennis@gmail.com"
__url__         = "Modified https://github.com/Dennis-van-Gils/DvG_dev_Arduino"
__date__        = "14-09-2018"
__version__     = "1.0.0 modified for MHT tunnel"

import queue
import numpy as np

from PyQt5 import QtCore
from PyQt5.QtCore import QDateTime

from DvG_debug_functions import ANSI, dprint
import DvG_dev_Arduino__fun_serial as Arduino_functions

# Show debug info in terminal? Warning: Slow! Do not leave on unintentionally.
DEBUG_worker_DAQ  = False
DEBUG_worker_send = False

# Short-hand alias for DEBUG information
def curThreadName(): return QtCore.QThread.currentThread().objectName()

# ------------------------------------------------------------------------------
#   InnerClassDescriptor
# ------------------------------------------------------------------------------

class InnerClassDescriptor(object):
    """Allows an inner class instance to get the attributes from the outer class
    instance by referring to 'self.outer'. Used in this module by the
    'Worker_DAQ' and 'Worker_send' classes. Usage: @InnerClassDescriptor.
    Not to be used outside of this module.
    """
    def __init__(self, cls):
        self.cls = cls

    def __get__(self, instance, outerclass):
        class Wrapper(self.cls):
            outer = instance
        Wrapper.__name__ = self.cls.__name__
        return Wrapper

# ------------------------------------------------------------------------------
#   Arduino_pyqt
# ------------------------------------------------------------------------------

class Arduino_pyqt(QtCore.QObject):
    """Manages multithreaded communication and periodical data acquisition for
    the two Arduino devices running the Twente MHT Tunnel.

    All device I/O operations will be offloaded to 'workers', each running in
    a newly created thread instead of in the main/GUI thread.

        - Worker_DAQ:
            Periodically acquires data from the device.

        - Worker_send:
            Maintains a thread-safe queue where desired device I/O operations
            can be put onto, and sends the queued operations first in first out
            (FIFO) to the device.
    """
    from DvG_dev_Base__pyqt_lib import close_all_threads

    signal_DAQ_updated     = QtCore.pyqtSignal()
    signal_connection_lost = QtCore.pyqtSignal()

    def __init__(self,
                 ard1: Arduino_functions.Arduino,
                 ard2: Arduino_functions.Arduino,
                 DAQ_update_interval_ms=250,
                 DAQ_function_to_run_each_update=None,
                 parent=None):
        super(Arduino_pyqt, self).__init__(parent=parent)

        self.ard1 = ard1
        self.ard2 = ard2

        self.ard1.mutex = QtCore.QMutex()
        self.ard2.mutex = QtCore.QMutex()

        self.worker_DAQ = self.Worker_DAQ(
                ard1=ard1,
                ard2=ard2,
                DAQ_update_interval_ms=DAQ_update_interval_ms,
                DAQ_function_to_run_each_update=DAQ_function_to_run_each_update,
                DAQ_critical_not_alive_count=3,
                DAQ_timer_type=QtCore.Qt.PreciseTimer,
                DEBUG=DEBUG_worker_DAQ)
        self.worker_send = self.Worker_send(
                ard1,
                ard2,
                DEBUG=DEBUG_worker_send)

        # Create and set up threads
        if (self.ard1.is_alive and self.ard2.is_alive):
            self.thread_DAQ = QtCore.QThread()
            self.thread_DAQ.setObjectName("%s_DAQ" % "Ards")
            self.worker_DAQ.moveToThread(self.thread_DAQ)
            self.thread_DAQ.started.connect(self.worker_DAQ.run)

            self.thread_send = QtCore.QThread()
            self.thread_send.setObjectName("%s_send" % "Ards")
            self.worker_send.moveToThread(self.thread_send)
            self.thread_send.started.connect(self.worker_send.run)
        else:
            self.thread_DAQ = None
            self.thread_send = None

    # --------------------------------------------------------------------------
    #   Worker_DAQ
    # --------------------------------------------------------------------------

    @InnerClassDescriptor
    class Worker_DAQ(QtCore.QObject):
        """This worker acquires data from the device at a fixed update interval.
        It does so by calling a user-supplied function containing your device
        I/O operations (and data parsing, processing or more), every update
        period.

        The worker should be placed inside a separate thread. No direct changes
        to the GUI should be performed inside this class. If needed, use the
        QtCore.pyqtSignal() mechanism to instigate GUI changes.

        The Worker_DAQ routine is robust in the following sense. It can be set
        to quit as soon as a communication error appears, or it could be set to
        allow a certain number of communication errors before it quits. The
        latter can be useful in non-critical implementations where continuity of
        the program is of more importance than preventing drops in data
        transmission. This, obviously, is a work-around for not having to tackle
        the source of the communication error, but sometimes you just need to
        struggle on. E.g., when your Arduino is out in the field and picks up
        occasional unwanted interference/ground noise that messes with your data
        transmission.

        Args:
            DAQ_update_interval_ms:
                Desired data acquisition update interval in milliseconds.

            DAQ_function_to_run_each_update (optional, default=None):
                Reference to a user-supplied function containing the device
                query operations and subsequent data processing, to be invoked
                every DAQ update. It should return True when everything went
                successful, and False otherwise.

                NOTE: No changes to the GUI should run inside this function! If
                you do anyhow, expect a penalty in the timing stability of this
                worker.

                E.g. pseudo-code, where 'time' and 'reading_1' are variables
                that live at a higher scope, presumably at main/GUI scope level.

                def my_update_function():
                    # Query the device for its state
                    [success, tmp_state] = dev.query_ascii_values("state?")
                    if not(success):
                        print("Device IOerror")
                        return False

                    # Parse readings into separate variables
                    try:
                        [time, reading_1] = tmp_state
                    except Exception as err:
                        print(err)
                        return False

                    return True

            DAQ_critical_not_alive_count (optional, default=1):
                The worker will allow for up to a certain number of
                communication failures with the device before hope is given up
                and a 'connection lost' signal is emitted. Use at your own
                discretion.

            DAQ_timer_type (PyQt5.QtCore.Qt.TimerType, optional, default=
                            PyQt5.QtCore.Qt.CoarseTimer):
                The update interval is timed to a QTimer running inside
                Worker_DAQ. The accuracy of the timer can be improved by setting
                it to PyQt5.QtCore.Qt.PreciseTimer with ~1 ms granularity, but
                it is resource heavy. Use sparingly.

            DEBUG (bool, optional, default=False):
                Show debug info in terminal? Warning: Slow! Do not leave on
                unintentionally.
        """
        def __init__(self,
                     ard1: Arduino_functions.Arduino,
                     ard2: Arduino_functions.Arduino,
                     DAQ_update_interval_ms,
                     DAQ_function_to_run_each_update=None,
                     DAQ_critical_not_alive_count=3,
                     DAQ_timer_type=QtCore.Qt.CoarseTimer,
                     DEBUG=False):
            super().__init__(None)
            self.DEBUG = DEBUG
            self.DEBUG_color = ANSI.CYAN

            self.ard1 = ard1
            self.ard2 = ard2
            self.update_interval_ms = DAQ_update_interval_ms
            self.function_to_run_each_update = DAQ_function_to_run_each_update
            self.critical_not_alive_count = DAQ_critical_not_alive_count
            self.timer_type = DAQ_timer_type

            self.calc_DAQ_rate_every_N_iter = round(1e3/self.update_interval_ms)
            self.prev_tick_DAQ_update = 0
            self.prev_tick_DAQ_rate = 0

            if self.DEBUG:
                dprint("Worker_DAQ  %s init: thread %s" %
                       (self.dev.name, curThreadName()), self.DEBUG_color)

        @QtCore.pyqtSlot()
        def run(self):
            if self.DEBUG:
                dprint("Worker_DAQ  %s run : thread %s" %
                       (self.dev.name, curThreadName()), self.DEBUG_color)

            self.timer = QtCore.QTimer()
            self.timer.setInterval(self.update_interval_ms)
            self.timer.timeout.connect(self.update)
            self.timer.setTimerType(self.timer_type)
            self.timer.start()

        @QtCore.pyqtSlot()
        def update(self):
            self.outer.DAQ_update_counter += 1
            locker1 = QtCore.QMutexLocker(self.ard1.mutex)
            locker2 = QtCore.QMutexLocker(self.ard2.mutex)

            if self.DEBUG:
                dprint("Worker_DAQ  %s: iter %i" %
                       ("Ards", self.outer.DAQ_update_counter),
                       self.DEBUG_color)

            # Keep track of the obtained DAQ update interval
            now = QtCore.QDateTime.currentMSecsSinceEpoch()
            self.outer.obtained_DAQ_update_interval_ms = (
                    now - self.prev_tick_DAQ_update)
            self.prev_tick_DAQ_update = now

            # Keep track of the obtained DAQ rate
            # Start at iteration 5 to ensure we have stabilized
            if self.outer.DAQ_update_counter == 5:
                self.prev_tick_DAQ_rate = now
            elif (self.outer.DAQ_update_counter %
                  self.calc_DAQ_rate_every_N_iter == 5):
                self.outer.obtained_DAQ_rate_Hz = (
                        self.calc_DAQ_rate_every_N_iter /
                        (now - self.prev_tick_DAQ_rate) * 1e3)
                self.prev_tick_DAQ_rate = now

#### DEBUG: PICK UP WORK FROM HERE

            # Check the alive counters
            if (self.ard1.not_alive_counter >= self.critical_not_alive_count):
                dprint("\nWorker_DAQ determined Arduino '%s' is not alive." %
                       self.ard1.name)
                self.ard1.is_alive = False

                locker1.unlock()
                locker2.unlock()
                self.timer.stop()
                self.signal_DAQ_updated.emit()
                self.signal_connection_lost.emit()
                return

            if (self.ard2.not_alive_counter >= self.critical_not_alive_count):
                dprint("\nWorker_DAQ determined Arduino '%s' is not alive." %
                       self.ard2.name)
                self.ard2.is_alive = False

                locker1.unlock()
                locker2.unlock()
                self.timer.stop()
                self.signal_DAQ_updated.emit()
                self.signal_connection_lost.emit()
                return

            # ------------------------
            #   External code
            # ------------------------

            if not(self.function_to_run_each_update is None):
                [success1, success2] = self.function_to_run_each_update()
                if not success1: self.ard1.not_alive_counter += 1
                if not success2: self.ard2.not_alive_counter += 1

            # ------------------------
            #   End external code
            # ------------------------

            locker1.unlock()
            locker2.unlock()

            if DEBUG:
                dprint("Worker_DAQ  %s: unlocked" % "Ards", self.DEBUG_color)

            self.signal_DAQ_updated.emit()

    # --------------------------------------------------------------------------
    #   Worker_send
    # --------------------------------------------------------------------------

    class Worker_send(QtCore.QObject):
        """This worker maintains a thread-safe queue where messages to be sent
        to the device can be put on the stack. The worker will send out the
        messages to the device, first in first out (FIFO), until the stack is
        empty again. It sends messages whenever it is woken up by calling
        'Worker_send.qwc.wakeAll()'

        Args:
            ard: Reference to 'DvG_dev_Arduino__fun_serial.Arduino()' instance.

        No changes to the GUI are allowed inside this class!
        """

        def __init__(self,
                     ard1: Arduino_functions.Arduino,
                     ard2: Arduino_functions.Arduino):
            super().__init__(None)
            self.DEBUG_color=ANSI.YELLOW

            self.ard1 = ard1
            self.ard2 = ard2
            self.running = True
            self.mutex = QtCore.QMutex()
            self.qwc = QtCore.QWaitCondition()

            # Use a 'sentinel' value to signal the start and end of the queue
            # to ensure proper multithreaded operation.
            self.sentinel = None
            self.queue = queue.Queue()
            self.queue.put(self.sentinel)

            if DEBUG:
                dprint("Worker_send %s init: thread %s" %
                       (self.dev.name, curThreadName()), self.DEBUG_color)

        @QtCore.pyqtSlot()
        def run(self):
            if DEBUG:
                dprint("Worker_send %s run : thread %s" %
                       (self.dev.name, curThreadName()), self.DEBUG_color)

            while self.running:
                locker_worker = QtCore.QMutexLocker(self.mutex)

                if DEBUG:
                    dprint("Worker_send %s: waiting for trigger" %
                           "Ards", self.DEBUG_color)
                self.qwc.wait(self.mutex)
                if DEBUG:
                    dprint("Worker_send %s: trigger received" %
                           "Ards", self.DEBUG_color)

                # Process all jobs until the queue is empty.
                # We must iterate 2 times because we use a sentinel in a FIFO
                # queue. First iter will remove the old sentinel. Second iter
                # will process the remaining queue items and will put back the
                # sentinel again.
                for i in range(2):
                    for job in iter(self.queue.get_nowait, self.sentinel):
                        ard  = job[0]
                        func = ard.write
                        args = job[1:]

                        if DEBUG:
                            dprint("Worker_send %s: %s %s" %
                                   (ard.name, func.__name__, args),
                                   self.DEBUG_color)

                        # Send I/O operation to the device
                        locker = QtCore.QMutexLocker(ard.mutex)
                        func(*args)
                        locker.unlock()

                    # Put sentinel back in
                    self.queue.put(self.sentinel)

                locker_worker.unlock()

            if DEBUG:
                dprint("Worker_send %s: done running" % "Ards",
                       self.DEBUG_color)

        @QtCore.pyqtSlot()
        def stop(self):
            self.running = False

    # --------------------------------------------------------------------------
    #   send
    # --------------------------------------------------------------------------

    def send(self, ard: Arduino_functions.Arduino, write_msg_str):
        """Put a 'write a string message' operation on the worker_send queue and
        process the queue.
        """
        self.worker_send.queue.put((ard, write_msg_str))

        # Schedule sending out the full queue to the device by waking up the
        # thread
        self.worker_send.qwc.wakeAll()