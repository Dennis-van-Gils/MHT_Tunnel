#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dennis van Gils
08-11-2018
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

from DvG_pyqt_controls import (create_Toggle_button,
                               SS_TEXTBOX_READ_ONLY,
                               SS_TITLE,
                               SS_GROUP)
from DvG_pyqt_ChartHistory import ChartHistory
from DvG_pyqt_FileLogger import FileLogger

import DvG_dev_Keysight_3497xA__fun_SCPI as K3497xA_functions
import DvG_dev_Keysight_3497xA__pyqt_lib as K3497xA_pyqt_lib
import DvG_dev_Picotech_PT104__fun_UDP   as pt104_functions
import DvG_dev_Picotech_PT104__pyqt_lib  as pt104_pyqt_lib

import functions_PolyScience_PD_models_RS232

# ------------------------------------------------------------------------------
#   MainWindow
# ------------------------------------------------------------------------------

class MainWindow(QtWid.QWidget):
    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)

        self.setGeometry(20, 60, 1200, 900)
        self.setWindowTitle("Calibration thermistors")

        # ----------------------------------------------------------------------
        #   Top frame
        # ----------------------------------------------------------------------

        # Left box
        vbox_left = QtWid.QVBoxLayout()
        vbox_left.addStretch(1)

        # Middle box
        self.lbl_title = QtWid.QLabel(
                text="Calibration thermistors",
                font=QtGui.QFont("Verdana", 12),
                minimumHeight=40)
        self.lbl_title.setStyleSheet(SS_TITLE)
        self.lbl_title.setAlignment(QtCore.Qt.AlignCenter)

        self.str_cur_date_time = QtWid.QLabel("00-00-0000    00:00:00")
        self.str_cur_date_time.setAlignment(QtCore.Qt.AlignCenter)

        self.qpbt_record = create_Toggle_button(
                "Click to start recording to file", minimumHeight=40)
        self.qpbt_record.setMinimumWidth(500)

        vbox_middle = QtWid.QVBoxLayout()
        vbox_middle.addWidget(self.lbl_title)
        vbox_middle.addWidget(self.str_cur_date_time)
        vbox_middle.addWidget(self.qpbt_record)

        # Right box
        self.qpbt_exit = QtWid.QPushButton("Exit")
        self.qpbt_exit.clicked.connect(self.close)
        self.qpbt_exit.setMinimumHeight(30)

        vbox_right = QtWid.QVBoxLayout()
        vbox_right.addWidget(self.qpbt_exit, stretch=0)
        vbox_right.addStretch(1)

        # Round up top frame
        hbox_top = QtWid.QHBoxLayout()
        hbox_top.addLayout(vbox_left, stretch=0)
        hbox_top.addStretch(1)
        hbox_top.addLayout(vbox_middle, stretch=0)
        hbox_top.addStretch(1)
        hbox_top.addLayout(vbox_right, stretch=0)

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
        self.qpbt_history_1 = QtWid.QPushButton("00:30", **p)
        self.qpbt_history_2 = QtWid.QPushButton("01:00", **p)
        self.qpbt_history_3 = QtWid.QPushButton("03:00", **p)
        self.qpbt_history_4 = QtWid.QPushButton("05:00", **p)
        self.qpbt_history_5 = QtWid.QPushButton("10:00", **p)
        self.qpbt_history_6 = QtWid.QPushButton("30:00", **p)

        self.qpbt_history_clear = QtWid.QPushButton("clear", **p)
        self.qpbt_history_clear.clicked.connect(self.clear_all_charts)

        grid = QtWid.QGridLayout()
        grid.setVerticalSpacing(0)
        grid.addWidget(self.qpbt_history_1, 0, 0)
        grid.addWidget(self.qpbt_history_2, 1, 0)
        grid.addWidget(self.qpbt_history_3, 2, 0)
        grid.addWidget(self.qpbt_history_4, 3, 0)
        grid.addWidget(self.qpbt_history_5, 4, 0)
        grid.addWidget(self.qpbt_history_6, 5, 0)
        grid.addWidget(self.qpbt_history_clear, 6, 0)

        grpb_history.setLayout(grid)

        # ----------------------------------------------------------------------
        #   Multiplexer grid
        # ----------------------------------------------------------------------

        vbox1 = QtWid.QVBoxLayout()
        vbox1.addWidget(grpb_show_curves, stretch=0, alignment=QtCore.Qt.AlignTop)
        vbox1.addWidget(grpb_history, stretch=0, alignment=QtCore.Qt.AlignTop)
        vbox1.addStretch(1)

        hbox_mux = QtWid.QHBoxLayout()
        hbox_mux.addWidget(mux_pyqt.qgrp, stretch=0, alignment=QtCore.Qt.AlignTop)
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
          '<span style="font-size:12pt">Temperatures</span>')
        self.pi_bath.setLabel('bottom',
          '<span style="font-size:12pt">history (min)</span>')
        self.pi_bath.setLabel('left',
          '<span style="font-size:12pt">(%sC)</span>' % chr(176))
        self.pi_bath.showGrid(x=1, y=1)
        self.pi_bath.setMenuEnabled(True)
        self.pi_bath.enableAutoRange(axis=pg.ViewBox.XAxis, enable=False)
        self.pi_bath.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
        self.pi_bath.setAutoVisible(y=True)

        pen1 = pg.mkPen(color=[255,   0,   0], width=2)
        pen2 = pg.mkPen(color=[255, 255,   0], width=2)
        pen3 = pg.mkPen(color=[0  , 128, 255], width=2)
        self.CH_P1_temp = ChartHistory(CH_SAMPLES_MUX,
                                       self.pi_bath.plot(pen=pen1))
        self.CH_P2_temp = ChartHistory(CH_SAMPLES_MUX,
                                       self.pi_bath.plot(pen=pen2))
        self.CH_PT104_ch1_T = ChartHistory(CH_SAMPLES_MUX,
                                       self.pi_bath.plot(pen=pen3))

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
        grid.addWidget(QtWid.QLabel("P2 (yel)")     , 1, 0)
        grid.addWidget(self.qled_P1_temp             , 0, 1)
        grid.addWidget(self.qled_P2_temp             , 1, 1)
        grid.addWidget(QtWid.QLabel("%sC" % chr(176)), 0, 2)
        grid.addWidget(QtWid.QLabel("%sC" % chr(176)), 1, 2)

        grpb_bath.setLayout(grid)

        # ----------------------------------------------------------------------
        #   Polyscience and PT104
        # ----------------------------------------------------------------------

        vbox_tmp = QtWid.QVBoxLayout()
        vbox_tmp.addWidget(grpb_bath, stretch=0)
        vbox_tmp.addWidget(pt104_pyqt.qgrp, stretch=0)
        vbox_tmp.addStretch(1)

        hbox_bath = QtWid.QHBoxLayout()
        hbox_bath.addLayout(vbox_tmp)
        hbox_bath.addWidget(self.gw_bath, stretch=1)

        # ----------------------------------------------------------------------
        #   Round up full window
        # ----------------------------------------------------------------------

        vbox = QtWid.QVBoxLayout(self)
        vbox.addLayout(hbox_top)
        vbox.addLayout(hbox_mux)
        vbox.addLayout(hbox_bath)
        vbox.addStretch(1)

    @QtCore.pyqtSlot()
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
            self.CH_PT104_ch1_T.clear()

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
    window.CH_P2_temp.curve.setVisible(False)
    window.CH_PT104_ch1_T.update_curve()

    window.qled_P1_temp.setText("%.2f" % bath.state.P1_temp)
    window.qled_P2_temp.setText("%.2f" % bath.state.P2_temp)

    # Show or hide curve depending on checkbox
    for i in range(N_channels):
        window.CHs_mux[i].curve.setVisible(
                window.chkbs_show_curves[i].isChecked())

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

@QtCore.pyqtSlot()
def process_qpbt_history_1():
    change_history_axes(time_axis_factor=1e3,      # transform [msec] to [sec]
                        time_axis_range=-30,       # [sec]
                        time_axis_label=
                        '<span style="font-size:12pt">history (sec)</span>')

@QtCore.pyqtSlot()
def process_qpbt_history_2():
    change_history_axes(time_axis_factor=1e3,      # transform [msec] to [sec]
                        time_axis_range=-60,       # [sec]
                        time_axis_label=
                        '<span style="font-size:12pt">history (sec)</span>')

@QtCore.pyqtSlot()
def process_qpbt_history_3():
    change_history_axes(time_axis_factor=60e3,     # transform [msec] to [min]
                        time_axis_range=-3,        # [min]
                        time_axis_label=
                        '<span style="font-size:12pt">history (min)</span>')

@QtCore.pyqtSlot()
def process_qpbt_history_4():
    change_history_axes(time_axis_factor=60e3,     # transform [msec] to [min]
                        time_axis_range=-5,        # [min]
                        time_axis_label=
                        '<span style="font-size:12pt">history (min)</span>')

@QtCore.pyqtSlot()
def process_qpbt_history_5():
    change_history_axes(time_axis_factor=60e3,     # transform [msec] to [min]
                        time_axis_range=-10,       # [min]
                        time_axis_label=
                        '<span style="font-size:12pt">history (min)</span>')

@QtCore.pyqtSlot()
def process_qpbt_history_6():
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
    window.CH_PT104_ch1_T.x_axis_divisor = time_axis_factor

@QtCore.pyqtSlot()
def process_qpbt_show_all_curves():
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

@QtCore.pyqtSlot()
def process_qpbt_record():
    if (window.qpbt_record.isChecked()):
        file_logger.starting = True
    else:
        file_logger.stopping = True

@QtCore.pyqtSlot(str)
def set_text_qpbt_record(text_str):
    window.qpbt_record.setText(text_str)

# ------------------------------------------------------------------------------
#   about_to_quit
# ------------------------------------------------------------------------------

def about_to_quit():
    print("About to quit")
    app.processEvents()
    file_logger.close_log()
    mux_pyqt.close_all_threads()
    pt104_pyqt.close_all_threads()

    try: mux.close()
    except: pass
    try: bath.close()
    except: pass
    try: pt104.close()
    except: pass
    try: rm.close()
    except: pass

# ------------------------------------------------------------------------------
#   mux_process
# ------------------------------------------------------------------------------

def mux_process():
    cur_date_time = QDateTime.currentDateTime()
    epoch_time = cur_date_time.toMSecsSinceEpoch()

    # DEBUG info
    #dprint("thread: %s" % QtCore.QThread.currentThread().objectName())

    if mux_pyqt.is_MUX_scanning:
        readings = mux.state.readings

        for i in range(N_channels):
            if readings[i] > 9.8e37:
                readings[i] = np.nan
    else:
        # Multiplexer is not scanning. No readings available
        readings = [np.nan] * N_channels
        mux.state.readings = readings

    # Add readings to charts
    for i in range(N_channels):
        window.CHs_mux[i].add_new_reading(epoch_time, readings[i])

    # UGLY HACK: put in Polyscience temperature bath and PT104 update here
    bath.query_P1_temp()
    #bath.query_P2_temp()  # External probe
    window.CH_P1_temp.add_new_reading(epoch_time, bath.state.P1_temp)
    window.CH_P2_temp.add_new_reading(epoch_time, bath.state.P2_temp)
    window.CH_PT104_ch1_T.add_new_reading(epoch_time, pt104.state.ch1_T)

    # ----------------------------------------------------------------------
    #   Logging to file
    # ----------------------------------------------------------------------

    if file_logger.starting:
        fn_log = ("d:/data/calib_thermistors_" +
                  cur_date_time.toString("yyMMdd_HHmmss") +
                  ".txt")
        if file_logger.create_log(epoch_time, fn_log, mode='w'):
            file_logger.signal_set_recording_text.emit(
                "Recording to file: " + fn_log)

            # Header
            file_logger.write("time[s]\t")
            file_logger.write("P1_temp[degC]\t")
            file_logger.write("P2_temp[degC]\t")
            file_logger.write("PT104_Ch1[degC]\t")
            for i in range(N_channels - 1):
                file_logger.write("CH%s\t" %
                                  mux.state.all_scan_list_channels[i])
            file_logger.write("CH%s\n" %
                              mux.state.all_scan_list_channels[-1])

    if file_logger.stopping:
        file_logger.signal_set_recording_text.emit(
            "Click to start recording to file")
        file_logger.close_log()

    if file_logger.is_recording:
        log_elapsed_time = (epoch_time - file_logger.start_time)/1e3  # [sec]

        # Add new data to the log
        file_logger.write("%.3f\t" % log_elapsed_time)
        file_logger.write("%.2f\t" % bath.state.P1_temp)
        file_logger.write("%.2f\t" % bath.state.P2_temp)
        file_logger.write("%.3f"   % pt104.state.ch1_T)
        for i in range(N_channels):
            if len(mux.state.readings) <= i:
                file_logger.write("\t%.5e" % np.nan)
            else:
                file_logger.write("\t%.5e" % mux.state.readings[i])
        file_logger.write("\n")

# ------------------------------------------------------------------------------
#   Main
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

    # --------------------------------------------------------------------------
    #   Connect to and set up Keysight 3497xA
    # --------------------------------------------------------------------------

    rm = visa.ResourceManager()

    mux = K3497xA_functions.K3497xA(MUX_VISA_ADDRESS, "MUX")
    if mux.connect(rm):
        mux.begin(MUX_SCPI_COMMANDS)

    # --------------------------------------------------------------------------
    #   Connect to and set up Picotech PT-104
    # --------------------------------------------------------------------------

    IP_ADDRESS    = "10.10.100.2"
    PORT          = 1234
    ENA_channels  = [1, 0, 0, 0]
    gain_channels = [1, 0, 0, 0]

    pt104 = pt104_functions.PT104(name="PT104")
    if pt104.connect(IP_ADDRESS, PORT):
        pt104.begin()
        pt104.start_conversion(ENA_channels, gain_channels)

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
    QtCore.QThread.currentThread().setObjectName('MAIN')    # For DEBUG info

    app = 0    # Work-around for kernel crash when using Spyder IDE
    app = QtWid.QApplication(sys.argv)
    app.setFont(QtGui.QFont("Arial", 9))
    app.setStyleSheet(SS_TEXTBOX_READ_ONLY)
    app.aboutToQuit.connect(about_to_quit)

    # Create PyQt GUI interfaces and communication threads
    mux_pyqt = K3497xA_pyqt_lib.K3497xA_pyqt(
            dev=mux,
            DAQ_update_interval_ms=MUX_SCANNING_INTERVAL_MS,
            DAQ_postprocess_MUX_scan_function=mux_process)
    mux_pyqt.set_table_readings_format("%.5e")
    mux_pyqt.qgrp.setFixedWidth(420)

    pt104_pyqt = pt104_pyqt_lib.PT104_pyqt(dev=pt104,
                                           DAQ_update_interval_ms=1000)
    pt104_pyqt.start_thread_worker_DAQ()

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

    window.qpbt_show_all_curves = QtWid.QPushButton("toggle", maximumWidth=70)
    window.qpbt_show_all_curves.clicked.connect(process_qpbt_show_all_curves)
    window.grid_show_curves.addWidget(window.qpbt_show_all_curves,
                                      N_channels, 0)

    # --------------------------------------------------------------------------
    #   File logger
    # --------------------------------------------------------------------------

    file_logger = FileLogger()
    file_logger.signal_set_recording_text.connect(set_text_qpbt_record)

    # --------------------------------------------------------------------------
    #   Start threads
    # --------------------------------------------------------------------------

    mux_pyqt.start_thread_worker_DAQ(QtCore.QThread.TimeCriticalPriority)
    mux_pyqt.start_thread_worker_send()

    # --------------------------------------------------------------------------
    #   Connect remaining signals from GUI
    # --------------------------------------------------------------------------

    window.qpbt_history_1.clicked.connect(process_qpbt_history_1)
    window.qpbt_history_2.clicked.connect(process_qpbt_history_2)
    window.qpbt_history_3.clicked.connect(process_qpbt_history_3)
    window.qpbt_history_4.clicked.connect(process_qpbt_history_4)
    window.qpbt_history_5.clicked.connect(process_qpbt_history_5)
    window.qpbt_history_6.clicked.connect(process_qpbt_history_6)
    window.qpbt_record.clicked.connect(process_qpbt_record)

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
    process_qpbt_history_3()

    window.show()
    sys.exit(app.exec_())