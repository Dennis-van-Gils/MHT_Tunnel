#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dennis van Gils
05-07-2018
"""

import sys
import visa
import pylab
from pathlib import Path

from PyQt5 import QtCore, QtGui
from PyQt5 import QtWidgets as QtWid
from PyQt5.QtCore import QDateTime

import pyqtgraph as pg
import numpy as np

from DvG_PyQt_controls import (create_Toggle_button,
                               SS_TEXTBOX_READ_ONLY,
                               SS_GROUP)
from DvG_PyQt_ChartHistory import ChartHistory

import DvG_dev_Keysight_3497xA__fun_SCPI as K3497xA_functions
import DvG_dev_Keysight_3497xA__PyQt_lib as K3497xA_pyqt_lib

import functions_PolyScience_PD_models_RS232

# Global variables for date-time keeping
main_start_time = QDateTime.currentDateTime()

# ------------------------------------------------------------------------------
#   MainWindow
# ------------------------------------------------------------------------------

class MainWindow(QtWid.QWidget):
    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)

        self.setGeometry(20, 60, 1200, 900)
        self.setWindowTitle("Calibration thermistor")

        # ----------------------------------------------------------------------
        #   Top grid
        # ----------------------------------------------------------------------

        self.lbl_title = QtWid.QLabel("Keysight 3497xA control",
                font=QtGui.QFont("Palatino", 14, weight=QtGui.QFont.Bold))
        self.str_cur_date_time = QtWid.QLabel("00-00-0000    00:00:00")
        self.pbtn_record = create_Toggle_button(
                "Click to start recording to file", minimumHeight=40)
        self.pbtn_record.setMinimumWidth(400)

        self.pbtn_exit = QtWid.QPushButton("Exit")
        self.pbtn_exit.clicked.connect(self.close)
        self.pbtn_exit.setMinimumHeight(30)

        grid_top = QtWid.QGridLayout()
        grid_top.addWidget(self.lbl_title        , 0, 0, QtCore.Qt.AlignCenter)
        grid_top.addWidget(self.pbtn_exit        , 0, 2, QtCore.Qt.AlignRight)
        grid_top.addWidget(self.str_cur_date_time, 1, 0, QtCore.Qt.AlignCenter)
        grid_top.addWidget(self.pbtn_record      , 2, 0, QtCore.Qt.AlignCenter)
        grid_top.setColumnMinimumWidth(0, 420)
        grid_top.setColumnStretch(1, 1)

        # ----------------------------------------------------------------------
        #   Chart: Mux readings
        # ----------------------------------------------------------------------

        # GraphicsWindow
        self.gw_mux = pg.GraphicsWindow()
        self.gw_mux.setBackground([20, 20, 20])

        # PlotItem
        self.pi_mux = self.gw_mux.addPlot()
        self.pi_mux.setTitle(
          '<span style="font-size:12pt">Mux readings</span>')
        self.pi_mux.setLabel('bottom',
          '<span style="font-size:12pt">history (min)</span>')
        self.pi_mux.setLabel('left',
          '<span style="font-size:12pt">misc. units</span>')
        self.pi_mux.showGrid(x=1, y=1)
        self.pi_mux.setMenuEnabled(True)
        self.pi_mux.enableAutoRange(axis=pg.ViewBox.XAxis, enable=False)
        self.pi_mux.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
        self.pi_mux.setAutoVisible(y=True)

        # Viewbox properties for the legend
        vb = self.gw_mux.addViewBox(enableMenu=False)
        vb.setMaximumWidth(80)

        # Legend
        self.legend = pg.LegendItem()
        self.legend.setParentItem(vb)
        self.legend.anchor((0,0), (0,0), offset=(1, 10))
        self.legend.setFixedWidth(75)
        self.legend.setScale(1)

        # ----------------------------------------------------------------------
        #   Show curves selection
        # ----------------------------------------------------------------------

        grpb_show_curves = QtWid.QGroupBox("Show")
        grpb_show_curves.setStyleSheet(SS_GROUP)

        self.grid_show_curves = QtWid.QGridLayout()
        self.grid_show_curves.setVerticalSpacing(0)

        grpb_show_curves.setLayout(self.grid_show_curves)

        # ----------------------------------------------------------------------
        #   Chart history time range selection
        # ----------------------------------------------------------------------

        grpb_history = QtWid.QGroupBox("History")
        grpb_history.setStyleSheet(SS_GROUP)

        p = {'maximumWidth': 70}
        self.pbtn_history_1 = QtWid.QPushButton("00:30", **p)
        self.pbtn_history_2 = QtWid.QPushButton("01:00", **p)
        self.pbtn_history_3 = QtWid.QPushButton("03:00", **p)
        self.pbtn_history_4 = QtWid.QPushButton("05:00", **p)
        self.pbtn_history_5 = QtWid.QPushButton("10:00", **p)
        self.pbtn_history_6 = QtWid.QPushButton("30:00", **p)

        self.pbtn_history_clear = QtWid.QPushButton("clear", **p)
        self.pbtn_history_clear.clicked.connect(self.clear_all_charts)

        grid = QtWid.QGridLayout()
        grid.setVerticalSpacing(0)
        grid.addWidget(self.pbtn_history_1, 0, 0)
        grid.addWidget(self.pbtn_history_2, 1, 0)
        grid.addWidget(self.pbtn_history_3, 2, 0)
        grid.addWidget(self.pbtn_history_4, 3, 0)
        grid.addWidget(self.pbtn_history_5, 4, 0)
        grid.addWidget(self.pbtn_history_6, 5, 0)
        grid.addWidget(self.pbtn_history_clear, 6, 0)

        grpb_history.setLayout(grid)

        # ----------------------------------------------------------------------
        #   Multiplexer grid
        # ----------------------------------------------------------------------

        vbox1 = QtWid.QVBoxLayout()
        vbox1.addWidget(grpb_show_curves, stretch=0, alignment=QtCore.Qt.AlignTop)
        vbox1.addWidget(grpb_history, stretch=0, alignment=QtCore.Qt.AlignTop)
        vbox1.addStretch(1)

        hbox_mux = QtWid.QHBoxLayout()
        hbox_mux.addWidget(mux_pyqt.grpb, stretch=0, alignment=QtCore.Qt.AlignTop)
        hbox_mux.addWidget(self.gw_mux, stretch=1)
        hbox_mux.addLayout(vbox1)

        # ----------------------------------------------------------------------
        #   Chart: Bath temperatures
        # ----------------------------------------------------------------------

        # GraphicsWindow
        self.gw_bath = pg.GraphicsWindow()
        self.gw_bath.setBackground([20, 20, 20])

        # PlotItem
        self.pi_bath = self.gw_bath.addPlot()
        self.pi_bath.setTitle(
          '<span style="font-size:12pt">Polyscience bath</span>')
        self.pi_bath.setLabel('bottom',
          '<span style="font-size:12pt">history (min)</span>')
        self.pi_bath.setLabel('left',
          '<span style="font-size:12pt">(%sC)</span>' % chr(176))
        self.pi_bath.showGrid(x=1, y=1)
        self.pi_bath.setMenuEnabled(True)
        self.pi_bath.enableAutoRange(axis=pg.ViewBox.XAxis, enable=False)
        self.pi_bath.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
        self.pi_bath.setAutoVisible(y=True)

        pen1 = pg.mkPen(color='r', width=2)
        pen2 = pg.mkPen(color='c', width=2)
        self.CH_P1_temp = ChartHistory(CH_SAMPLES_MUX,
                                       self.pi_bath.plot(pen=pen1))
        self.CH_P2_temp = ChartHistory(CH_SAMPLES_MUX,
                                       self.pi_bath.plot(pen=pen2))

        # ----------------------------------------------------------------------
        #   Group: Bath temperatures
        # ----------------------------------------------------------------------

        grpb_bath = QtWid.QGroupBox("Polyscience bath")
        grpb_bath.setStyleSheet(SS_GROUP)

        self.qled_P1_temp = QtWid.QLineEdit("nan")
        self.qled_P2_temp = QtWid.QLineEdit("nan")

        grid = QtWid.QGridLayout()
        grid.setVerticalSpacing(4)
        grid.addWidget(QtWid.QLabel("P1 (red)")      , 0, 0)
        grid.addWidget(QtWid.QLabel("P2 (cyan)")     , 1, 0)
        grid.addWidget(self.qled_P1_temp             , 0, 1)
        grid.addWidget(self.qled_P2_temp             , 1, 1)
        grid.addWidget(QtWid.QLabel("%sC" % chr(176)), 0, 2)
        grid.addWidget(QtWid.QLabel("%sC" % chr(176)), 1, 2)

        grpb_bath.setLayout(grid)

        # ----------------------------------------------------------------------
        #   Polyscience grid
        # ----------------------------------------------------------------------

        hbox_bath = QtWid.QHBoxLayout()
        hbox_bath.addWidget(grpb_bath, stretch=0, alignment=QtCore.Qt.AlignTop)
        hbox_bath.addWidget(self.gw_bath, stretch=1)

        # ----------------------------------------------------------------------
        #   Round up full window
        # ----------------------------------------------------------------------

        vbox = QtWid.QVBoxLayout(self)
        vbox.addLayout(grid_top)
        vbox.addLayout(hbox_mux)
        vbox.addLayout(hbox_bath)
        vbox.addStretch(1)

    def clear_all_charts(self):
        str_msg = "Are you sure you want to clear all charts?"
        reply = QtWid.QMessageBox.warning(self, "Clear charts", str_msg,
                                          QtWid.QMessageBox.Yes |
                                          QtWid.QMessageBox.No,
                                          QtWid.QMessageBox.No)

        if reply == QtWid.QMessageBox.Yes:
            [CH.clear() for CH in self.CHs_mux]
            self.CH_P1_temp.clear()
            self.CH_P2_temp.clear()

# ------------------------------------------------------------------------------
#   update_GUI
# ------------------------------------------------------------------------------

def update_GUI():
    cur_date_time = QDateTime.currentDateTime()
    window.str_cur_date_time.setText(cur_date_time.toString("dd-MM-yyyy") +
                                     "    " +
                                     cur_date_time.toString("HH:mm:ss"))

    # Update curves
    [CH.update_curve() for CH in window.CHs_mux]
    window.CH_P1_temp.update_curve()
    window.CH_P2_temp.update_curve()

    window.qled_P1_temp.setText("%.2f" % bath.state.P1_temp)
    window.qled_P2_temp.setText("%.2f" % bath.state.P2_temp)

    # Show or hide curve depending on checkbox
    for i in range(N_channels):
        window.CHs_mux[i].curve.setVisible(
                window.chkbs_show_curves[i].isChecked())

# ------------------------------------------------------------------------------
#   This function should be 'injected' into the 'update' method of the
#   [dev_Keysight_3497xA__PyQt_lib.Worker_state] instance. This is done by
#   assigning this function to [Worker_state.external_function_to_run_in_update]
#   NOTE: no GUI changes are allowed in this function.
# ------------------------------------------------------------------------------

def mux_process():
    cur_date_time = QDateTime.currentDateTime()

    # DEBUG info
    #dprint("thread: %s" % QtCore.QThread.currentThread().objectName())

    if mux_pyqt.worker_state.ENA_periodic_scanning:
        readings = mux.state.readings

        for i in range(N_channels):
            if readings[i] > 9.8e37:
                readings[i] = np.nan
    else:
        # Multiplexer is not scanning. No readings available
        readings = [np.nan] * N_channels
        mux.state.readings = readings

    # Add readings to charts
    elapsed_time = main_start_time.msecsTo(cur_date_time)
    for i in range(N_channels):
        window.CHs_mux[i].add_new_reading(elapsed_time, readings[i])

    # UGLY HACK: put in Polyscience temperature bath update here
    bath.query_P1_temp()
    bath.query_P2_temp()
    window.CH_P1_temp.add_new_reading(elapsed_time, bath.state.P1_temp)
    window.CH_P2_temp.add_new_reading(elapsed_time, bath.state.P2_temp)

    # ----------------------------------------------------------------------
    #   Logging to file
    # ----------------------------------------------------------------------

    locker = QtCore.QMutexLocker(mux_pyqt.mutex_log)

    if mux_pyqt.startup_recording:
        mux_pyqt.startup_recording = False
        mux_pyqt.is_recording = True

        # Create log file on disk
        mux_pyqt.fn_log = ("d:/data/mux_" +
                           cur_date_time.toString("yyMMdd_HHmmss") +
                           ".txt")
        window.pbtn_record.setText("Recording to file: " + mux_pyqt.fn_log)
        mux_pyqt.log_start_time = cur_date_time

        mux_pyqt.f_log = open(mux_pyqt.fn_log, 'w')
        try:
            mux_pyqt.f_log.write("time[s]\t")
            mux_pyqt.f_log.write("P1_temp[degC]\t")
            mux_pyqt.f_log.write("P2_temp[degC]\t")
            for i in range(N_channels - 1):
                mux_pyqt.f_log.write("CH%s\t" %
                                     mux.state.all_scan_list_channels[i])
            mux_pyqt.f_log.write("CH%s\n" %
                                 mux.state.all_scan_list_channels[-1])
        except:
            raise

    if mux_pyqt.closing_recording:
        if mux_pyqt.is_recording:
            mux_pyqt.f_log.close()
        mux_pyqt.closing_recording = False
        mux_pyqt.is_recording = False

    locker.unlock()

    if mux_pyqt.is_recording:
        # Add new data to the log
        log_elapsed_time = mux_pyqt.log_start_time.msecsTo(cur_date_time)/1e3  # [sec]
        try:
            mux_pyqt.f_log.write("%.3f\t" % log_elapsed_time)
            mux_pyqt.f_log.write("%.2f\t" % bath.state.P1_temp)
            mux_pyqt.f_log.write("%.2f"   % bath.state.P2_temp)
            for i in range(N_channels):
                if len(mux.state.readings) <= i:
                    mux_pyqt.f_log.write("\t%.5e" % np.nan)
                else:
                    mux_pyqt.f_log.write("\t%.5e" % mux.state.readings[i])
            mux_pyqt.f_log.write("\n")
        except:
            raise

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

def process_pbtn_record():
    locker = QtCore.QMutexLocker(mux_pyqt.mutex_log)
    if (window.pbtn_record.isChecked()):
        mux_pyqt.startup_recording = True
        mux_pyqt.closing_recording = False
    else:
        mux_pyqt.startup_recording = False
        mux_pyqt.closing_recording = True
        window.pbtn_record.setText("Click to start recording to file")

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
    window.pi_mux.setXRange(time_axis_range, 0)
    window.pi_mux.setLabel('bottom', time_axis_label)

    window.pi_bath.setXRange(time_axis_range, 0)
    window.pi_bath.setLabel('bottom', time_axis_label)

    for i in range(N_channels):
        window.CHs_mux[i].x_axis_divisor = time_axis_factor
    window.CH_P1_temp.x_axis_divisor   = time_axis_factor
    window.CH_P2_temp.x_axis_divisor   = time_axis_factor

def process_pbtn_show_all_curves():
    # First: if any curve is hidden --> show all
    # Second: if all curves are shown --> hide all

    any_hidden = False
    for i in range(N_channels):
        if (not window.chkbs_show_curves[i].isChecked()):
            window.chkbs_show_curves[i].setChecked(True)
            any_hidden = True

    if (not any_hidden):
        for i in range(N_channels):
            window.chkbs_show_curves[i].setChecked(False)

# ------------------------------------------------------------------------------
#   about_to_quit
# ------------------------------------------------------------------------------

def about_to_quit():
    print("About to quit")

    # First make sure to process all pending events
    app.processEvents()

    # Close threads
    mux_pyqt.close_threads()

    # Close log if open
    locker = QtCore.QMutexLocker(mux_pyqt.mutex_log)
    if mux_pyqt.is_recording:
        mux_pyqt.f_log.close()
        mux_pyqt.startup_recording = False
        mux_pyqt.closing_recording = False
        mux_pyqt.is_recording = False
    locker.unlock()

    # Close device connections
    try: mux.close()
    except: pass

    try: bath.close()
    except: pass

    # Close VISA resource manager
    try: rm.close()
    except: pass

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
#
#   MAIN
#
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

if __name__ == '__main__':
    # VISA address of the Keysight 3497xA data acquisition/switch unit
    # containing a multiplexer plug-in module. Hence, we simply call this device
    # a 'mux'.
    #MUX_VISA_ADDRESS = "USB0::0x0957::0x2007::MY49018071::INSTR"
    MUX_VISA_ADDRESS = "GPIB0::9::INSTR"

    # A scan will be performed by the mux every N milliseconds
    MUX_SCANNING_INTERVAL_MS = 1000       # [ms]

    # Chart history (CH) buffer sizes in [samples].
    # Multiply this with the corresponding SCANNING_INTERVAL constants to get
    # the history size in time.
    CH_SAMPLES_MUX = 1800

    # The chart will be updated at this interval
    UPDATE_INTERVAL_GUI = 1000          # [ms]

    # SCPI commands to be send to the 3497xA to set up the scan cycle.
    """
    scan_list = "(@301:310)"
    MUX_SCPI_COMMANDS = [
                "rout:open %s" % scan_list,
                "conf:temp TC,J,%s" % scan_list,
                "unit:temp C,%s" % scan_list,
                "sens:temp:tran:tc:rjun:type INT,%s" % scan_list,
                "sens:temp:tran:tc:check ON,%s" % scan_list,
                "sens:temp:nplc 1,%s" % scan_list,
                "rout:scan %s" % scan_list]
    """
    scan_list = "(@101)"
    MUX_SCPI_COMMANDS = [
                "rout:open %s" % scan_list,
                "conf:res 1e5,%s" % scan_list,
                "sens:res:nplc 1,%s" % scan_list,
                "rout:scan %s" % scan_list]
    #"""

    # --------------------------------------------------------------------------
    #   Connect to and set up Keysight 3497xA
    # --------------------------------------------------------------------------

    rm = visa.ResourceManager()

    mux = K3497xA_functions.K3497xA(MUX_VISA_ADDRESS, "MUX")
    if mux.connect(rm):
        mux.begin(MUX_SCPI_COMMANDS)

    # --------------------------------------------------------------------------
    #   Connect to and set up Polyscience chiller
    # --------------------------------------------------------------------------
    # Temperature setpoint limits in software, not on a hardware level
    BATH_MIN_SETPOINT_DEG_C = 10     # [deg C]
    BATH_MAX_SETPOINT_DEG_C = 87     # [deg C]

    # Serial settings
    RS232_BAUDRATE = 57600      # Baudrate according to the manual
    RS232_TIMEOUT  = 0.5        # [sec]

    # Path to the config textfile containing the (last used) RS232 port
    PATH_CONFIG = Path("config/port_PolyScience.txt")

    # Create a PolyScience_bath class instance
    bath = functions_PolyScience_PD_models_RS232.PolyScience_bath()

    # Were we able to connect to a PolyScience bath?
    if bath.auto_connect(PATH_CONFIG):
        # TO DO: display internal settings of the PolyScience bath, like
        # its temperature limits, etc.
        pass
    else:
        sys.exit(0)


    # --------------------------------------------------------------------------
    #   Create application
    # --------------------------------------------------------------------------

    app = 0    # Work-around for kernel crash when using Spyder IDE
    app = QtWid.QApplication(sys.argv)
    app.setFont(QtGui.QFont("Arial", 9))
    app.setStyleSheet(SS_TEXTBOX_READ_ONLY)
    app.aboutToQuit.connect(about_to_quit)

    # For DEBUG info
    QtCore.QThread.currentThread().setObjectName('MAIN')

    # Create PyQt GUI interfaces and communication threads per 3497xA
    mux_pyqt = K3497xA_pyqt_lib.K3497xA_pyqt(
            dev=mux, scanning_interval_ms=MUX_SCANNING_INTERVAL_MS)

    mux_pyqt.set_table_readings_format("%.5e")

    # Add variables for logging
    mux_pyqt.mutex_log = QtCore.QMutex()
    mux_pyqt.is_recording = False
    mux_pyqt.startup_recording = False
    mux_pyqt.closing_recording = False

    # Create window
    window = MainWindow()

    # --------------------------------------------------------------------------
    #   Create pens and chart histories depending on the number of scan channels
    # --------------------------------------------------------------------------

    N_channels = len(mux.state.all_scan_list_channels)

    # Pen styles for plotting
    PENS = [None] * N_channels
    cm = pylab.get_cmap('gist_rainbow')
    params = {'width': 2}
    for i in range(N_channels):
        color = cm(1.*i/N_channels)  # color will now be an RGBA tuple
        color = np.array(color) * 255
        PENS[i] = pg.mkPen(color=color, **params)

    # Create Chart Histories (CH) and PlotDataItems and link them together
    # Also add legend entries
    window.CHs_mux = [None] * N_channels
    window.chkbs_show_curves = [None] * N_channels
    for i in range(N_channels):
        window.CHs_mux[i] = ChartHistory(CH_SAMPLES_MUX,
                                         window.pi_mux.plot(pen=PENS[i]))
        window.legend.addItem(window.CHs_mux[i].curve,
                              name=mux.state.all_scan_list_channels[i])

        # Add checkboxes for showing the curves
        window.chkbs_show_curves[i] = QtWid.QCheckBox(
                parent=window,
                text=mux.state.all_scan_list_channels[i],
                checked=True)
        window.grid_show_curves.addWidget(window.chkbs_show_curves[i], i, 0)

    window.pbtn_show_all_curves = QtWid.QPushButton("toggle", maximumWidth=70)
    window.pbtn_show_all_curves.clicked.connect(process_pbtn_show_all_curves)

    window.grid_show_curves.addWidget(window.pbtn_show_all_curves, N_channels, 0)

    # --------------------------------------------------------------------------
    #   Start threads
    # --------------------------------------------------------------------------

    if mux.is_alive:
        mux_pyqt.worker_state.external_function_to_run_in_update = (
                lambda: mux_process())
        mux_pyqt.thread_state.start()
        mux_pyqt.thread_send.start()

        mux_pyqt.thread_state.setPriority(QtCore.QThread.TimeCriticalPriority)

    mux_pyqt.grpb.setFixedWidth(420)

    # --------------------------------------------------------------------------
    #   Connect remaining signals from GUI
    # --------------------------------------------------------------------------

    window.pbtn_history_1.clicked.connect(process_pbtn_history_1)
    window.pbtn_history_2.clicked.connect(process_pbtn_history_2)
    window.pbtn_history_3.clicked.connect(process_pbtn_history_3)
    window.pbtn_history_4.clicked.connect(process_pbtn_history_4)
    window.pbtn_history_5.clicked.connect(process_pbtn_history_5)
    window.pbtn_history_6.clicked.connect(process_pbtn_history_6)

    window.pbtn_record.clicked.connect(process_pbtn_record)

    # --------------------------------------------------------------------------
    #   Set up timers
    # --------------------------------------------------------------------------

    timer_GUI = QtCore.QTimer()
    timer_GUI.timeout.connect(update_GUI)
    timer_GUI.start(UPDATE_INTERVAL_GUI)

    # --------------------------------------------------------------------------
    #   Start the main GUI loop
    # --------------------------------------------------------------------------

    # Init the time axis of the strip charts
    process_pbtn_history_3()

    window.show()
    sys.exit(app.exec_())