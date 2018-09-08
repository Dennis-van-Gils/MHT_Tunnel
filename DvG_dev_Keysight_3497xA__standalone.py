#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dennis van Gils
14-06-2018
"""

import sys
import visa

from PyQt5 import QtCore, QtGui
from PyQt5 import QtWidgets as QtWid

from DvG_PyQt_controls import SS_TEXTBOX_READ_ONLY

import DvG_dev_Keysight_3497xA__fun_SCPI as K3497xA_functions
import DvG_dev_Keysight_3497xA__PyQt_lib as K3497xA_pyqt_lib

# ------------------------------------------------------------------------------
#   MainWindow
# ------------------------------------------------------------------------------

class MainWindow(QtWid.QWidget):
    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)

        self.setGeometry(600, 120, 0, 0)
        self.setWindowTitle("Keysight 3497xA control")

        # Top grid
        self.lbl_title = QtWid.QLabel("Keysight 3497xA control",
            font=QtGui.QFont("Palatino", 14, weight=QtGui.QFont.Bold))
        self.pbtn_exit = QtWid.QPushButton("Exit")
        self.pbtn_exit.clicked.connect(self.close)
        self.pbtn_exit.setMinimumHeight(30)

        grid_top = QtWid.QGridLayout()
        grid_top.addWidget(self.lbl_title, 0, 0)
        grid_top.addWidget(self.pbtn_exit, 0, 1, QtCore.Qt.AlignRight)

        # Bottom grid
        hbox1 = QtWid.QHBoxLayout()
        hbox1.addWidget(mux_pyqt.grpb)
        hbox1.addStretch(1)
        hbox1.setAlignment(mux_pyqt.grpb, QtCore.Qt.AlignTop)

        # Round up full window
        vbox = QtWid.QVBoxLayout(self)
        vbox.addLayout(grid_top)
        vbox.addLayout(hbox1)
        vbox.addStretch(1)

# ------------------------------------------------------------------------------
#   about_to_quit
# ------------------------------------------------------------------------------

def about_to_quit():
    print("About to quit")

    # First make sure to process all pending events
    app.processEvents()

    # Close threads
    mux_pyqt.close_threads()

    # Close device connections
    try: mux.close()
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

    # SCPI commands to be send to the 3497xA to set up the scan cycle.
    """
    scan_list = "(@301:312)"
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

    mux = K3497xA_functions.K3497xA(MUX_VISA_ADDRESS, "MUX 1")
    if mux.connect(rm):
        mux.begin(MUX_SCPI_COMMANDS)

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

    # Create window
    window = MainWindow()

    # --------------------------------------------------------------------------
    #   Start threads
    # --------------------------------------------------------------------------

    if mux.is_alive:
        mux_pyqt.thread_state.start()
        mux_pyqt.thread_send.start()

    # --------------------------------------------------------------------------
    #   Start the main GUI loop
    # --------------------------------------------------------------------------

    window.show()
    sys.exit(app.exec_())