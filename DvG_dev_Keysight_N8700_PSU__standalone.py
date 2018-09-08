#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dennis van Gils
17-04-2018
"""

import sys
import os
import visa
from pathlib import Path

from PyQt5 import QtCore, QtGui
from PyQt5 import QtWidgets as QtWid

from DvG_debug_functions import ANSI, dprint
from DvG_PyQt_controls import SS_TEXTBOX_READ_ONLY

import DvG_dev_Keysight_N8700_PSU__fun_SCPI as N8700_functions
import DvG_dev_Keysight_N8700_PSU__PyQt_lib as N8700_pyqt_lib

# Show debug info in terminal? Warning: slow! Do not leave on unintentionally.
DEBUG = False

# ------------------------------------------------------------------------------
#   MainWindow
# ------------------------------------------------------------------------------

class MainWindow(QtWid.QWidget):
    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)

        self.setGeometry(600, 120, 0, 0)
        self.setWindowTitle("Keysight N8700 power supply control")

        # Top grid
        self.lbl_title = QtWid.QLabel("Keysight N8700 power supply control",
            font=QtGui.QFont("Palatino", 14, weight=QtGui.QFont.Bold))
        self.pbtn_exit = QtWid.QPushButton("Exit")
        self.pbtn_exit.clicked.connect(self.close)
        self.pbtn_exit.setMinimumHeight(30)

        grid_top = QtWid.QGridLayout()
        grid_top.addWidget(self.lbl_title, 0, 0)
        grid_top.addWidget(self.pbtn_exit, 0, 1, QtCore.Qt.AlignRight)

        # PSU groups
        hbox1 = QtWid.QHBoxLayout()
        for psu_pyqt in psus_pyqt:
            hbox1.addWidget(psu_pyqt.grpb)
        hbox1.addStretch(1)

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
    for psu_pyqt in psus_pyqt:
        psu_pyqt.close_threads()

    # Close device connections
    for psu in psus:
        try: psu.close()
        except: pass

    # Close VISA resource manager
    try: rm.close()
    except: pass

# ------------------------------------------------------------------------------
#   trigger_update_psus
# ------------------------------------------------------------------------------

def trigger_update_psus():
    # Update PSU readings by waking up the 'state' threads
    if DEBUG: dprint("worker_state: wake all", ANSI.RED)
    for psu_pyqt in psus_pyqt:
        psu_pyqt.worker_state.qwc.wakeAll()

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
#
#   MAIN
#
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

if __name__ == '__main__':
    # VISA addresses of the Keysight PSUs
    VISA_ADDRESS_PSU_1 = "USB0::0x0957::0x8707::US15M3727P::INSTR"
    VISA_ADDRESS_PSU_2 = "USB0::0x0957::0x8707::US15M3728P::INSTR"
    VISA_ADDRESS_PSU_3 = "USB0::0x0957::0x8707::US15M3726P::INSTR"

    # Config files
    PATH_CONFIG_PSU_1 = Path(os.getcwd() +
                             "/config/settings_Keysight_PSU_1.txt")
    PATH_CONFIG_PSU_2 = Path(os.getcwd() +
                             "/config/settings_Keysight_PSU_2.txt")
    PATH_CONFIG_PSU_3 = Path(os.getcwd() +
                             "/config/settings_Keysight_PSU_3.txt")

    # The state of the PSUs is polled with this time interval
    UPDATE_INTERVAL_MS = 1000       # [ms]

    # --------------------------------------------------------------------------
    #   Connect to and set up Keysight power supplies (PSU)
    # --------------------------------------------------------------------------

    rm = visa.ResourceManager()

    psu1 = N8700_functions.PSU(VISA_ADDRESS_PSU_1, PATH_CONFIG_PSU_1, "PSU 1")
    psu2 = N8700_functions.PSU(VISA_ADDRESS_PSU_2, PATH_CONFIG_PSU_2, "PSU 2")
    psu3 = N8700_functions.PSU(VISA_ADDRESS_PSU_3, PATH_CONFIG_PSU_3, "PSU 3")
    psus = [psu1, psu2, psu3]

    for psu in psus:
        if psu.connect(rm):
            psu.read_config_file()
            psu.begin()

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
    DEBUG_colors = (ANSI.YELLOW, ANSI.CYAN, ANSI.GREEN)

    # Create PyQt GUI interfaces and communication threads per power supply
    psus_pyqt = list()
    for i in range(len(psus)):
        psus_pyqt.append(N8700_pyqt_lib.PSU_pyqt(
                dev=psus[i], DEBUG_color=DEBUG_colors[i]))

    # Create window
    window = MainWindow()

    # --------------------------------------------------------------------------
    #   Set up PSU update timer
    # --------------------------------------------------------------------------

    timer_psus = QtCore.QTimer()
    timer_psus.timeout.connect(trigger_update_psus)
    timer_psus.start(UPDATE_INTERVAL_MS)

    # --------------------------------------------------------------------------
    #   Start threads
    # --------------------------------------------------------------------------

    for psu_pyqt in psus_pyqt:
        if psu_pyqt.dev.is_alive:
            psu_pyqt.thread_state.start()
            psu_pyqt.thread_send.start()

    # --------------------------------------------------------------------------
    #   Start the main GUI loop
    # --------------------------------------------------------------------------

    window.show()
    sys.exit(app.exec_())