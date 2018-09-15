#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Constructs the graphical user interface (GUI) and defines GUI constants

No signals should be connected here that target device i/o operations. Instead,
these signals should be connected in the main py file, such that multithreading
can be properly implemented with mutex.lock() and mutex.unlock(). Signals that
target only other GUI elements can be connected here.

Dennis van Gils
15-09-2018
"""

from PyQt5 import QtCore, QtGui
from PyQt5 import QtWidgets as QtWid

import pyqtgraph as pg
import numpy as np

import MHT_tunnel_constants as C
from MHT_tunnel_constants import FSM_FS_PROGRAMS

from DvG_pyqt_controls import (create_LED_indicator,
                               create_Relay_button,
                               create_Toggle_button,
                               create_Toggle_button_2,
                               create_Toggle_button_3,
                               SS_GROUP, SS_TEXT_MSGS,
                               SS_TEXTBOX_READ_ONLY,
                               SS_TITLE)
from DvG_pyqt_ChartHistory import ChartHistory


# Fonts
FONT_DEFAULT   = QtGui.QFont("Arial", 9)
FONT_LARGE     = QtGui.QFont("Verdana", 12)
FONT_MONOSPACE = QtGui.QFont("Courier", 8)
FONT_MONOSPACE.setFamily("Monospace")
FONT_MONOSPACE.setStyleHint(QtGui.QFont.Monospace)

# Special characters
CHAR_DEG_C = chr(176) + 'C'
CHAR_PM    = chr(177)

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

# ------------------------------------------------------------------------------
#   MainWindow
# ------------------------------------------------------------------------------

class MainWindow(QtWid.QWidget):
    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)

        self.setGeometry(30, 50, 0, 0)
        self.setWindowTitle("MHT tunnel control")
        self.setStyleSheet(SS_TEXTBOX_READ_ONLY)

        # -------------------------
        #   Top frame
        # -------------------------

        # Left box
        self.Ard_1_label = QtWid.QLabel("Arduino #1")
        self.Ard_2_label = QtWid.QLabel("Arduino #2")
        self.update_counter = QtWid.QLabel("0")
        self.lbl_DAQ_rate = QtWid.QLabel("DAQ: 0 Hz")

        vbox_left = QtWid.QVBoxLayout()
        vbox_left.addWidget(self.Ard_1_label, stretch=0)
        vbox_left.addWidget(self.Ard_2_label, stretch=0)
        vbox_left.addWidget(self.update_counter, stretch=0)
        vbox_left.addStretch(1)
        vbox_left.addWidget(self.lbl_DAQ_rate, stretch=0)

        # Middle box
        self.lbl_title = QtWid.QLabel(
          text="    MASS & HEAT TRANSFER TUNNEL CONTROL   ", font=FONT_LARGE,
          minimumHeight=40)
        self.lbl_title.setStyleSheet(SS_TITLE)
        self.lbl_title.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_title.mousePressEvent = self.toggle_visibility_debug_GUI

        self.str_cur_date_time = QtWid.QLabel("00-00-0000    00:00:00")
        self.str_cur_date_time.setAlignment(QtCore.Qt.AlignCenter)

        self.pbtn_record = create_Toggle_button(
                "Click to start recording to file", minimumHeight=40)

        vbox_middle = QtWid.QVBoxLayout()
        vbox_middle.addWidget(self.lbl_title)
        vbox_middle.addWidget(self.str_cur_date_time)
        vbox_middle.addWidget(self.pbtn_record)

        # Right box
        self.pbtn_exit = QtWid.QPushButton("Exit")
        self.pbtn_exit.clicked.connect(self.close)
        self.pbtn_exit.setMinimumHeight(30)

        self.pbtn_reset = QtWid.QPushButton("Soft reset")
        self.pbtn_reset.setMinimumHeight(30)

        vbox_right = QtWid.QVBoxLayout()
        vbox_right.addWidget(self.pbtn_exit, stretch=0)
        vbox_right.addWidget(self.pbtn_reset, stretch=0)
        vbox_right.addStretch(1)

        # Round up top frame
        hbox_top = QtWid.QHBoxLayout()
        hbox_top.addLayout(vbox_left, stretch=0)
        hbox_top.addStretch(1)
        hbox_top.addLayout(vbox_middle, stretch=0)
        hbox_top.addStretch(1)
        hbox_top.addLayout(vbox_right, stretch=0)

        # -------------------------
        #   Tab control frame
        # -------------------------

        self.tabs = QtWid.QTabWidget()
        self.tab_main           = QtWid.QWidget()
        self.tab_chiller        = QtWid.QWidget()
        self.tab_heater_control = QtWid.QWidget()
        self.tab_traverse       = QtWid.QWidget()
        self.tab_filling        = QtWid.QWidget()
        self.tab_debug          = QtWid.QWidget()

        self.tabs.addTab(self.tab_main          , "Main")
        self.tabs.addTab(self.tab_heater_control, "Heater control")
        self.tabs.addTab(self.tab_chiller       , "Chiller")
        self.tabs.addTab(self.tab_traverse      , "Traverse")
        self.tabs.addTab(self.tab_debug         , "Debug")
        self.tabs.addTab(self.tab_filling       , "Filling system")

        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        #
        #   TAB PAGE: Main
        #
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------

        def heater_TC(): pass # Spyder IDE outline item
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        #
        #   Heater thermocouples
        #
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------

        grp_HTC = QtWid.QGroupBox("Heater temp.")
        grp_HTC.setStyleSheet(SS_GROUP)

        p = {'layoutDirection': QtCore.Qt.LeftToRight,
             'checked': True}
        self.chkbs_heater_TC = [QtWid.QCheckBox("#01", **p),
                                QtWid.QCheckBox("#02", **p),
                                QtWid.QCheckBox("#03", **p),
                                QtWid.QCheckBox("#04", **p),
                                QtWid.QCheckBox("#05", **p),
                                QtWid.QCheckBox("#06", **p),
                                QtWid.QCheckBox("#07", **p),
                                QtWid.QCheckBox("#08", **p),
                                QtWid.QCheckBox("#09", **p),
                                QtWid.QCheckBox("#10", **p),
                                QtWid.QCheckBox("#11", **p),
                                QtWid.QCheckBox("#12", **p)]

        p = {'alignment': QtCore.Qt.AlignRight,
             'readOnly': True,
             'minimumWidth': 50,
             'maximumWidth': 30}
        self.heater_TC_01_degC = QtWid.QLineEdit(**p)
        self.heater_TC_02_degC = QtWid.QLineEdit(**p)
        self.heater_TC_03_degC = QtWid.QLineEdit(**p)
        self.heater_TC_04_degC = QtWid.QLineEdit(**p)
        self.heater_TC_05_degC = QtWid.QLineEdit(**p)
        self.heater_TC_06_degC = QtWid.QLineEdit(**p)
        self.heater_TC_07_degC = QtWid.QLineEdit(**p)
        self.heater_TC_08_degC = QtWid.QLineEdit(**p)
        self.heater_TC_09_degC = QtWid.QLineEdit(**p)
        self.heater_TC_10_degC = QtWid.QLineEdit(**p)
        self.heater_TC_11_degC = QtWid.QLineEdit(**p)
        self.heater_TC_12_degC = QtWid.QLineEdit(**p)

        self.pbtn_heater_TC_all  = QtWid.QPushButton("Show all / none")
        self.pbtn_heater_TC_1_6  = QtWid.QPushButton("1 - 6")
        self.pbtn_heater_TC_7_12 = QtWid.QPushButton("7 - 12")

        self.pbtn_heater_TC_all.clicked.connect(self.process_pbtn_heater_TC_all)
        self.pbtn_heater_TC_1_6.clicked.connect(
          lambda: self.process_pbtn_heater_TC_selection(np.linspace(0, 5, 6)))
        self.pbtn_heater_TC_7_12.clicked.connect(
          lambda: self.process_pbtn_heater_TC_selection(np.linspace(6, 11, 6)))

        grid = QtWid.QGridLayout()
        grid.setVerticalSpacing(4)
        grid.addWidget(QtWid.QLabel(CHAR_DEG_C), 0, 1)
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
        grid.addWidget(self.pbtn_heater_TC_all , 13, 0, 1, 2)
        grid.addWidget(self.pbtn_heater_TC_1_6 , 14, 0, 1, 2)
        grid.addWidget(self.pbtn_heater_TC_7_12, 15, 0, 1, 2)
        grid.setAlignment(QtCore.Qt.AlignTop)

        grp_HTC.setLayout(grid)

        def chart_heater_TC(): pass # Spyder IDE outline item
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        #
        #   Chart: Heater thermocouples
        #
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------

        # GraphicsWindow
        self.gw_heater_TC = pg.GraphicsWindow()
        self.gw_heater_TC.setBackground([20, 20, 20])

        # PlotItem
        self.pi_heater_TC = self.gw_heater_TC.addPlot()
        self.pi_heater_TC.setTitle(
          '<span style="font-size:12pt">Heater temperatures ('+CHAR_PM+
          ' 1 K)</span>')
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
        vb.setMaximumWidth(80)

        # Legend
        legend = pg.LegendItem()
        legend.setParentItem(vb)
        legend.anchor((0,0), (0,0), offset=(1, 10))
        legend.setFixedWidth(75)
        legend.setScale(1)

        # Create Chart Histories and PlotDataItems and link them together
        # Also add legend entries
        self.CHs_heater_TC = [None] * C.N_HEATER_TC
        for i in range(C.N_HEATER_TC):
            self.CHs_heater_TC[i] = ChartHistory(
                    C.CH_SAMPLES_HEATER_TC, self.pi_heater_TC.plot(pen=PENS[i]))
            legend.addItem(self.CHs_heater_TC[i].curve, name=('#%02i' % (i+1)))

        def bubble_injection(): pass # Spyder IDE outline item
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        #
        #   Bubble injection
        #
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------

        grpb_bubbles = QtWid.QGroupBox("Bubble injection")
        grpb_bubbles.setStyleSheet(SS_GROUP)

        self.relay_1_4 = create_Relay_button()
        self.relay_1_5 = create_Relay_button()
        self.relay_1_6 = create_Relay_button()
        self.relay_1_7 = create_Relay_button()
        self.relay_1_8 = create_Relay_button()

        grid = QtWid.QGridLayout()
        grid.setVerticalSpacing(0)
        # Space reserved for QGroupBox of dev_Bronkhorst_MFC__PyQt_lib
        grid.addItem(QtWid.QSpacerItem(1, 16)        , 2, 0)
        grid.addWidget(QtWid.QLabel("bubble_valve_1"), 3, 0)
        grid.addWidget(QtWid.QLabel("bubble_valve_2"), 4, 0)
        grid.addWidget(QtWid.QLabel("bubble_valve_3"), 5, 0)
        grid.addWidget(QtWid.QLabel("bubble_valve_4"), 6, 0)
        grid.addWidget(QtWid.QLabel("bubble_valve_5"), 7, 0)
        grid.addWidget(self.relay_1_4                , 3, 1, QtCore.Qt.AlignCenter)
        grid.addWidget(self.relay_1_5                , 4, 1, QtCore.Qt.AlignCenter)
        grid.addWidget(self.relay_1_6                , 5, 1, QtCore.Qt.AlignCenter)
        grid.addWidget(self.relay_1_7                , 6, 1, QtCore.Qt.AlignCenter)
        grid.addWidget(self.relay_1_8                , 7, 1, QtCore.Qt.AlignCenter)
        grid.addWidget(QtWid.QLabel("relay 1.4")     , 3, 2)
        grid.addWidget(QtWid.QLabel("relay 1.5")     , 4, 2)
        grid.addWidget(QtWid.QLabel("relay 1.6")     , 5, 2)
        grid.addWidget(QtWid.QLabel("relay 1.7")     , 6, 2)
        grid.addWidget(QtWid.QLabel("relay 1.8")     , 7, 2)

        self.grid_bubbles = grid
        grpb_bubbles.setLayout(grid)

        def gas_volume_fraction(): pass # Spyder IDE outline item
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        #
        #   Gas volume fraction
        #
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------

        grpb_GVF = QtWid.QGroupBox("Gas volume fraction")
        grpb_GVF.setStyleSheet(SS_GROUP)

        p = {'alignment': QtCore.Qt.AlignCenter, 'visible': False}
        self.lbl_read_GVF_P_diff_mA   = QtWid.QLabel("mA", **p)
        self.lbl_read_GVF_P_diff_bitV = QtWid.QLabel("0-4095", **p)

        p = {'alignment': QtCore.Qt.AlignRight,
             'minimumWidth': 50, 'maximumWidth': 30}
        self.read_GVF_P_diff_mbar = QtWid.QLineEdit(**p, text="0.0",
                                                    readOnly=True)
        self.read_GVF_P_diff_mA   = QtWid.QLineEdit(**p, readOnly=True,
                                                    visible=False)
        self.read_GVF_P_diff_bitV = QtWid.QLineEdit(**p, readOnly=True,
                                                    visible=False)
        self.GVF_density_liquid = QtWid.QLineEdit(**p, text="998")
        self.GVF_pct = QtWid.QLineEdit(**p, readOnly=True)

        grid = QtWid.QGridLayout()
        grid.setVerticalSpacing(4)
        grid.addWidget(QtWid.QLabel("α = Δp/(ρ_l g d), d = 0.96 m"), 0, 0, 1, 3)
        grid.addWidget(self.lbl_read_GVF_P_diff_mA        , 1, 3)
        grid.addWidget(self.lbl_read_GVF_P_diff_bitV      , 1, 4)
        grid.addWidget(QtWid.QLabel("Diff. pressure: Δp") , 2, 0)
        grid.addWidget(self.read_GVF_P_diff_mbar          , 2, 1)
        grid.addWidget(QtWid.QLabel("mbar")               , 2, 2)
        grid.addWidget(self.read_GVF_P_diff_mA            , 2, 3)
        grid.addWidget(self.read_GVF_P_diff_bitV          , 2, 4)
        grid.addWidget(QtWid.QLabel("Liquid density: ρ_l"), 3, 0)
        grid.addWidget(self.GVF_density_liquid            , 3, 1)
        grid.addWidget(QtWid.QLabel("kg/m3")              , 3, 2)
        grid.addWidget(QtWid.QLabel("Gas vol. fract.: α") , 4, 0)
        grid.addWidget(self.GVF_pct                       , 4, 1)
        grid.addWidget(QtWid.QLabel("%")                  , 4, 2)

        grpb_GVF.setLayout(grid)

        def OTP(): pass # Spyder IDE outline item
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        #
        #   Over-temperature protection
        #
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------

        self.grpb_OTP = QtWid.QGroupBox("Over-temp. protection")
        self.grpb_OTP.setStyleSheet(SS_GROUP)

        self.pbtn_ENA_OTP = create_Toggle_button_3("Protection\nENABLED")
        self.qled_OTP_max_temp = QtWid.QLineEdit("%s" % C.OTP_MAX_TEMP_DEGC,
                                 readOnly=True,
                                 alignment=QtCore.Qt.AlignCenter +
                                           QtCore.Qt.AlignVCenter,
                                 minimumWidth=30,
                                 maximumWidth=30)

        self.relay_1_1 = create_Relay_button()
        self.relay_1_2 = create_Relay_button()
        self.relay_1_3 = create_Relay_button()

        i = 0
        grid = QtWid.QGridLayout()
        grid.setVerticalSpacing(0)
        grid.addWidget(self.pbtn_ENA_OTP          , i, 0, 1, 3) ; i+=1
        grid.addItem(QtWid.QSpacerItem(1, 4)      , i, 0)       ; i+=1
        grid.addWidget(QtWid.QLabel("Temp. limit"), i, 0)
        grid.addWidget(self.qled_OTP_max_temp     , i, 1)
        grid.addWidget(QtWid.QLabel(CHAR_DEG_C)   , i, 2)       ; i+=1
        grid.addItem(QtWid.QSpacerItem(1, 8)      , i, 0)       ; i+=1
        grid.addWidget(QtWid.QLabel("ENA_PSU_1")  , i, 0)
        grid.addWidget(self.relay_1_1             , i, 1, QtCore.Qt.AlignCenter)
        grid.addWidget(QtWid.QLabel("relay 1.1")  , i, 2)       ; i+=1
        grid.addWidget(QtWid.QLabel("ENA_PSU_2")  , i, 0)
        grid.addWidget(self.relay_1_2             , i, 1, QtCore.Qt.AlignCenter)
        grid.addWidget(QtWid.QLabel("relay 1.2")  , i, 2)       ; i+=1
        grid.addWidget(QtWid.QLabel("ENA_PSU_3")  , i, 0)
        grid.addWidget(self.relay_1_3             , i, 1, QtCore.Qt.AlignCenter)
        grid.addWidget(QtWid.QLabel("relay 1.3")  , i, 2)       ; i+=1

        self.grpb_OTP.setLayout(grid)

        def tunnel_temp(): pass # Spyder IDE outline item
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        #
        #   Tunnel temperatures
        #
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------

        grp_tunnel_temp = QtWid.QGroupBox("Tunnel temperatures")
        grp_tunnel_temp.setStyleSheet(SS_GROUP)

        p = {'layoutDirection': QtCore.Qt.LeftToRight}
        self.chkbs_tunnel_temp = [
                QtWid.QCheckBox("Tunnel outlet", **p, checked=True),
                QtWid.QCheckBox("Tunnel inlet" , **p, checked=True),
                QtWid.QCheckBox("Chiller"      , **p, checked=False),
                QtWid.QCheckBox("Chiller setp.", **p, checked=False)]

        params = {'alignment': QtCore.Qt.AlignCenter,
                  'minimumWidth': 50,
                  'maximumWidth': 30}
        self.pt104_offline = QtWid.QLabel("PT-104 OFFLINE", visible=False,
            font=QtGui.QFont("Palatino", 12, weight=QtGui.QFont.Bold),
            alignment=QtCore.Qt.AlignCenter)
        self.tunnel_outlet_temp     = QtWid.QLineEdit(**params, readOnly=True)
        self.tunnel_inlet_temp      = QtWid.QLineEdit(**params, readOnly=True)
        self.chiller_read_temp      = QtWid.QLineEdit(**params, readOnly=True)
        self.chiller_read_setpoint  = QtWid.QLineEdit(**params, readOnly=True)

        grid = QtWid.QGridLayout()
        grid.setVerticalSpacing(4)
        grid.addWidget(self.pt104_offline         , 0, 0, 1, 3)
        grid.addWidget(self.chkbs_tunnel_temp[0]  , 1, 0)
        grid.addWidget(self.chkbs_tunnel_temp[1]  , 2, 0)
        grid.addWidget(self.chkbs_tunnel_temp[2]  , 3, 0)
        grid.addWidget(self.chkbs_tunnel_temp[3]  , 4, 0)
        grid.addWidget(self.tunnel_outlet_temp    , 1, 1)
        grid.addWidget(self.tunnel_inlet_temp     , 2, 1)
        grid.addWidget(self.chiller_read_temp     , 3, 1)
        grid.addWidget(self.chiller_read_setpoint , 4, 1)
        grid.addWidget(QtWid.QLabel(CHAR_DEG_C)   , 1, 2)  # u"\u00B1" + "0.015"
        grid.addWidget(QtWid.QLabel(CHAR_DEG_C)   , 2, 2)
        grid.addWidget(QtWid.QLabel(CHAR_DEG_C)   , 3, 2)
        grid.addWidget(QtWid.QLabel(CHAR_DEG_C)   , 4, 2)

        grp_tunnel_temp.setLayout(grid)

        def chart_tunnel_temp(): pass # Spyder IDE outline item
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        #
        #   Chart: Tunnel temperature
        #
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------

        # GraphicsWindow
        self.gw_tunnel_temp = pg.GraphicsWindow()
        self.gw_tunnel_temp.setBackground([20, 20, 20])

        # PlotItem
        self.pi_tunnel_temp = self.gw_tunnel_temp.addPlot()
        self.pi_tunnel_temp.setTitle(
          '<span style="font-size:12pt">Tunnel temperatures</span>')
        self.pi_tunnel_temp.setLabel('bottom',
          '<span style="font-size:12pt">history (min)</span>')
        self.pi_tunnel_temp.setLabel('left',
          '<span style="font-size:12pt">temperature ('+CHAR_DEG_C+')</span>')
        self.pi_tunnel_temp.showGrid(x=1, y=1)
        self.pi_tunnel_temp.setMenuEnabled(True)
        self.pi_tunnel_temp.enableAutoRange(axis=pg.ViewBox.XAxis, enable=False)
        self.pi_tunnel_temp.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
        self.pi_tunnel_temp.setAutoVisible(y=True)

        # Viewbox properties for the legend
        vb = self.gw_tunnel_temp.addViewBox(enableMenu=False)
        vb.setMaximumWidth(80)

        # Legend
        legend = pg.LegendItem()
        legend.setParentItem(vb)
        legend.anchor((0,0), (0,0), offset=(1, 10))
        legend.setFixedWidth(75)
        legend.setScale(1)

        # Create Chart Histories and PlotDataItems and link them together
        self.CH_tunnel_outlet = ChartHistory(
                C.CH_SAMPLES_PT104, self.pi_tunnel_temp.plot(pen=PENS[5]))
        self.CH_tunnel_inlet = ChartHistory(
                C.CH_SAMPLES_PT104, self.pi_tunnel_temp.plot(pen=PENS[1]))
        self.CH_chiller_temp = ChartHistory(
                C.CH_SAMPLES_CHILLER, self.pi_tunnel_temp.plot(pen=PENS[2]))
        self.CH_chiller_setpoint = ChartHistory(
                C.CH_SAMPLES_CHILLER, self.pi_tunnel_temp.plot(pen=PENS[4]))

        # Add legend entries
        legend.addItem(self.CH_tunnel_outlet.curve   , name="outlet")
        legend.addItem(self.CH_tunnel_inlet.curve    , name="inlet")
        legend.addItem(self.CH_chiller_temp.curve    , name="chiller")
        legend.addItem(self.CH_chiller_setpoint.curve, name="chill sp")

        def tunnel_flow(): pass # Spyder IDE outline item
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        #
        #   Tunnel flow
        #
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------

        grp_pump = QtWid.QGroupBox("Tunnel flow")
        grp_pump.setStyleSheet(SS_GROUP)

        self.enable_pump = create_Toggle_button("Pump ON")

        p = {'alignment': QtCore.Qt.AlignCenter, 'visible': False}
        self.lbl_tunnel_pump_mA   = QtWid.QLabel("mA", **p)
        self.lbl_tunnel_pump_bitV = QtWid.QLabel("0-4095", **p)

        p = {'alignment': QtCore.Qt.AlignCenter, 'minimumWidth': 50,
             'maximumWidth': 30}
        self.set_pump_speed_pct = QtWid.QLineEdit(**p, text="0.0")
        self.set_pump_speed_mA  = QtWid.QLineEdit(**p, text="4.00",
                                                  visible=False)

        self.read_flow_rate_m3h  = QtWid.QLineEdit(**p, readOnly=True)
        self.read_flow_rate_mA   = QtWid.QLineEdit(**p, readOnly=True,
                                                   visible=False)
        self.read_flow_rate_bitV = QtWid.QLineEdit(**p, readOnly=True,
                                                   visible=False)

        self.enable_pump_PID = create_Toggle_button("PID feedback OFF")

        self.rbtn_MS1 = QtWid.QRadioButton("0.3 x 0.08 m2")
        self.rbtn_MS2 = QtWid.QRadioButton("0.3 x 0.06 m2")
        self.rbtn_MS3 = QtWid.QRadioButton("0.3 x 0.04 m2")
        self.rbtn_MS2.setChecked(True)

        self.set_flow_speed_cms  = QtWid.QLineEdit(**p)
        self.read_flow_speed_cms = QtWid.QLineEdit(**p, readOnly=True)
        self.set_flow_rate_m3h   = QtWid.QLineEdit(**p, readOnly=True,
                                                   visible=False)
        self.lbl_flow_rate_m3h   = QtWid.QLabel("m3/h", visible=False)

        grid = QtWid.QGridLayout()
        grid.setVerticalSpacing(4)

        grid.addWidget(self.enable_pump               , 0, 0, 1, 2)
        grid.addWidget(QtWid.QLabel("relay 2.8")      , 0, 2)

        grid.addWidget(self.lbl_tunnel_pump_mA        , 1, 3)
        grid.addWidget(self.lbl_tunnel_pump_bitV      , 1, 4)

        grid.addWidget(QtWid.QLabel("Set pump speed") , 2, 0)
        grid.addWidget(self.set_pump_speed_pct        , 2, 1)
        grid.addWidget(QtWid.QLabel("%")              , 2, 2)
        grid.addWidget(self.set_pump_speed_mA         , 2, 3)

        grid.addWidget(QtWid.QLabel("Read flow rate") , 4, 0)
        grid.addWidget(self.read_flow_rate_m3h        , 4, 1)
        grid.addWidget(QtWid.QLabel("m3/h")           , 4, 2)
        grid.addWidget(self.read_flow_rate_mA         , 4, 3)
        grid.addWidget(self.read_flow_rate_bitV       , 4, 4)

        grid.addItem(QtWid.QSpacerItem(1, 12)         , 7, 0)
        grid.addWidget(self.enable_pump_PID           , 8, 0, 1, 2)

        grid.addWidget(QtWid.QLabel("Meas. section")  , 9, 0)
        grid.addWidget(self.rbtn_MS1                  , 9, 1, 1, 3)
        grid.addWidget(self.rbtn_MS2                  , 10, 1, 1, 3)
        grid.addWidget(self.rbtn_MS3                  , 11, 1, 1, 3)

        grid.addWidget(QtWid.QLabel("Set flow speed") , 12, 0)
        grid.addWidget(self.set_flow_speed_cms        , 12, 1)
        grid.addWidget(QtWid.QLabel("cm/s")           , 12, 2)
        grid.addWidget(self.set_flow_rate_m3h         , 12, 3)
        grid.addWidget(self.lbl_flow_rate_m3h         , 12, 4)
        grid.addWidget(QtWid.QLabel("Read flow speed"), 13, 0)
        grid.addWidget(self.read_flow_speed_cms       , 13, 1)
        grid.addWidget(QtWid.QLabel("cm/s")           , 13, 2)

        grp_pump.setLayout(grid)

        def chart_flow_speed(): pass # Spyder IDE outline item
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        #
        #   Chart: Flow speed
        #
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------

        # GraphicsWindow
        self.gw_flow_speed = pg.GraphicsWindow()
        self.gw_flow_speed.setBackground([20, 20, 20])

        # PlotItem
        self.pi_flow_speed = self.gw_flow_speed.addPlot()
        self.pi_flow_speed.setTitle(
          '<span style="font-size:12pt">Tunnel flow</span>')
        self.pi_flow_speed.setLabel('bottom',
          '<span style="font-size:12pt">history (min)</span>')
        self.pi_flow_speed.setLabel('left',
          '<span style="font-size:12pt">flow speed (cm/s)</span>',
          color="#FF2222")
        self.pi_flow_speed.showGrid(x=1, y=1)
        self.pi_flow_speed.setMenuEnabled(True)
        self.pi_flow_speed.enableAutoRange(axis=pg.ViewBox.XAxis, enable=False)
        self.pi_flow_speed.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
        self.pi_flow_speed.setAutoVisible(y=True)

        # Create Chart History and PlotDataItem and link them together
        self.CH_flow_speed = ChartHistory(C.CH_SAMPLES_FLOW_SPEED,
                                          self.pi_flow_speed.plot(pen=PENS[5]))

        # Create a second y-axis on the right side
        # We do so by creating a new ViewBox and AxisItem and adding these to
        # the original GraphicsWindow and setting correct links
        self.vb_set_pump_speed = pg.ViewBox()
        ax_2 = pg.AxisItem("right", linkView=self.vb_set_pump_speed)
        self.pi_flow_speed.layout.addItem(ax_2, 2, 3)
        self.gw_flow_speed.scene().addItem(self.vb_set_pump_speed)
        self.vb_set_pump_speed.setXLink(self.pi_flow_speed)

        ax_2.setLabel('<span style="font-size:12pt">set pump speed (%)</span>',
                      color="#0080FC")
        self.vb_set_pump_speed.setMenuEnabled(True)
        self.vb_set_pump_speed.enableAutoRange(axis=pg.ViewBox.YAxis,
                                               enable=True)
        self.vb_set_pump_speed.setAutoVisible(y=True)

        # Slot: Update view when resized
        self.pi_flow_speed.vb.sigResized.connect(lambda:
            self.vb_set_pump_speed.setGeometry(
                    self.pi_flow_speed.vb.sceneBoundingRect()))

        # Create Chart History and PlotDataItem and link them together
        self.plot_set_pump_speed = pg.PlotDataItem(pen=PENS[1])
        self.vb_set_pump_speed.addItem(self.plot_set_pump_speed)
        self.CH_set_pump_speed = ChartHistory(C.CH_SAMPLES_FLOW_SPEED,
                                              self.plot_set_pump_speed)

        def chart_history(): pass # Spyder IDE outline item
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        #
        #   Chart history time range selection
        #
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------

        grp_history = QtWid.QGroupBox("History")
        grp_history.setStyleSheet(SS_GROUP)

        self.pbtn_history_1 = QtWid.QPushButton("00:30")
        self.pbtn_history_2 = QtWid.QPushButton("01:00")
        self.pbtn_history_3 = QtWid.QPushButton("03:00")
        self.pbtn_history_4 = QtWid.QPushButton("05:00")
        self.pbtn_history_5 = QtWid.QPushButton("10:00")
        self.pbtn_history_6 = QtWid.QPushButton("30:00")

        self.pbtn_history_clear = QtWid.QPushButton("clear")
        self.pbtn_history_clear.clicked.connect(self.clear_all_charts)

        grid = QtWid.QGridLayout()
        grid.setVerticalSpacing(2)
        grid.addWidget(self.pbtn_history_1, 0, 0)
        grid.addWidget(self.pbtn_history_2, 1, 0)
        grid.addWidget(self.pbtn_history_3, 2, 0)
        grid.addWidget(self.pbtn_history_4, 3, 0)
        grid.addWidget(self.pbtn_history_5, 4, 0)
        grid.addWidget(self.pbtn_history_6, 5, 0)
        grid.addWidget(self.pbtn_history_clear, 6, 0)

        grp_history.setLayout(grid)

        # Round up tab page
        # -------------------
        hbox1 = QtWid.QHBoxLayout()
        hbox1.addWidget(grp_HTC, alignment=QtCore.Qt.AlignTop)
        hbox1.addWidget(self.gw_heater_TC)

        vbox1 = QtWid.QVBoxLayout()
        vbox1.addWidget(grp_tunnel_temp)
        vbox1.addWidget(grpb_GVF)
        vbox1.addStretch(1)

        hbox1.addWidget(self.gw_tunnel_temp)
        hbox1.addLayout(vbox1)
        hbox1.addStretch(1)

        hbox2 = QtWid.QHBoxLayout()
        hbox2.addWidget(grpb_bubbles, stretch=0, alignment=QtCore.Qt.AlignTop)
        hbox2.addWidget(grp_pump, stretch=0, alignment=QtCore.Qt.AlignTop)
        hbox2.addWidget(self.gw_flow_speed, stretch=1)
        hbox2.addWidget(grp_history, stretch=0, alignment=QtCore.Qt.AlignTop)

        vbox = QtWid.QVBoxLayout()
        vbox.addLayout(hbox1)
        vbox.addLayout(hbox2)
        vbox.addStretch(1)

        self.tab_main.setLayout(vbox)

        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        #
        #   TAB PAGE: Heater control
        #
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------

        def chart_heater_power(): pass # Spyder IDE outline item
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        #
        #   Chart: heater power
        #
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------

        # Groupbox
        self.grpb_show_PSU = QtWid.QGroupBox("PSU")
        self.grpb_show_PSU.setStyleSheet(SS_GROUP)

        p = {'layoutDirection': QtCore.Qt.LeftToRight}
        self.chkb_PSU_1 = QtWid.QCheckBox("#1", **p, checked=True)
        self.chkb_PSU_2 = QtWid.QCheckBox("#2", **p, checked=True)
        self.chkb_PSU_3 = QtWid.QCheckBox("#3", **p, checked=True)

        grid = QtWid.QGridLayout()
        grid.setVerticalSpacing(4)
        grid.addWidget(self.chkb_PSU_1, 0, 0)
        grid.addWidget(self.chkb_PSU_2, 1, 0)
        grid.addWidget(self.chkb_PSU_3, 2, 0)

        self.grpb_show_PSU.setLayout(grid)

        # GraphicsWindow
        self.gw_heater_power = pg.GraphicsWindow()
        self.gw_heater_power.setBackground([20, 20, 20])

        # PlotItem
        self.pi_heater_power = self.gw_heater_power.addPlot()
        self.pi_heater_power.setTitle(
          '<span style="font-size:12pt">PSU power</span>')
        self.pi_heater_power.setLabel('bottom',
          '<span style="font-size:12pt">history (min)</span>')
        self.pi_heater_power.setLabel('left',
          '<span style="font-size:12pt">power (W)</span>')
        self.pi_heater_power.showGrid(x=1, y=1)
        self.pi_heater_power.setMenuEnabled(True)
        self.pi_heater_power.enableAutoRange(axis=pg.ViewBox.XAxis, enable=False)
        self.pi_heater_power.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
        self.pi_heater_power.setAutoVisible(y=True)

        # Viewbox properties for the legend
        vb = self.gw_heater_power.addViewBox(enableMenu=False)
        vb.setMaximumWidth(60)

        # Legend
        legend = pg.LegendItem()
        legend.setParentItem(vb)
        legend.anchor((0,0), (0,0), offset=(1, 10))
        legend.setFixedWidth(55)
        legend.setScale(1)

        # Create Chart History and PlotDataItem and link them together
        self.CH_power_PSU_1 = ChartHistory(
                C.CH_SAMPLES_HEATER_POWER,
                self.pi_heater_power.plot(pen=PENS[6]))  # 5
        self.CH_power_PSU_2 = ChartHistory(
                C.CH_SAMPLES_HEATER_POWER,
                self.pi_heater_power.plot(pen=PENS[8]))  # 3
        self.CH_power_PSU_3 = ChartHistory(
                C.CH_SAMPLES_HEATER_POWER,
                self.pi_heater_power.plot(pen=PENS[10])) # 1

        # Add legend entries
        legend.addItem(self.CH_power_PSU_1.curve, name="#1")
        legend.addItem(self.CH_power_PSU_2.curve, name="#2")
        legend.addItem(self.CH_power_PSU_3.curve, name="#3")

        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        #
        #   TAB PAGE: Debug
        #
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------

        def chart_DAQ_rate(): pass # Spyder IDE outline item
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        #
        #   Chart: DAQ rate
        #
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------

        # GraphicsWindow
        self.gw_DAQ_rate = pg.GraphicsWindow()
        self.gw_DAQ_rate.setBackground([20, 20, 20])

        # PlotItem
        self.pi_DAQ_rate = self.gw_DAQ_rate.addPlot()
        self.pi_DAQ_rate.setTitle(
          '<span style="font-size:12pt">DAQ rate</span>')
        self.pi_DAQ_rate.setLabel('bottom',
          '<span style="font-size:12pt">history (min)</span>')
        self.pi_DAQ_rate.setLabel('left',
          '<span style="font-size:12pt">DAQ rate (Hz)</span>')
        self.pi_DAQ_rate.showGrid(x=1, y=1)
        self.pi_DAQ_rate.setMenuEnabled(True)
        self.pi_DAQ_rate.enableAutoRange(axis=pg.ViewBox.XAxis, enable=False)
        self.pi_DAQ_rate.enableAutoRange(axis=pg.ViewBox.YAxis, enable=False)
        self.pi_DAQ_rate.setAutoVisible(y=True)
        self.pi_DAQ_rate.setXRange(
                -C.CH_SAMPLES_DAQ_RATE / 1e3 * C.UPDATE_INTERVAL_ARDUINOS *
                C.CALC_DAQ_RATE_EVERY_N_ITER/60, 0)
        self.pi_DAQ_rate.setYRange(round(1e3/C.UPDATE_INTERVAL_ARDUINOS) - 1,
                                   round(1e3/C.UPDATE_INTERVAL_ARDUINOS) + 1)

        # Create Chart History and PlotDataItem and link them together
        self.CH_DAQ_rate = ChartHistory(C.CH_SAMPLES_DAQ_RATE,
                                        self.pi_DAQ_rate.plot(pen=PENS[0]))
        self.CH_DAQ_rate.x_axis_divisor = 60e3   # From [ms] to [min]

        def debug(): pass # Spyder IDE outline item
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        #
        #   Debug
        #
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------

        grp_debug = QtWid.QGroupBox("Debug")
        grp_debug.setStyleSheet(SS_GROUP)

        self.fill_TC_chart_random = QtWid.QPushButton(
                "Fill TC chart\nwith random data")

        self.pbtn_debug_1 = QtWid.QPushButton("Enable\ndownsamping")
        self.pbtn_debug_2 = QtWid.QPushButton("Disable\ndownsamping")
        self.pbtn_debug_3 = QtWid.QPushButton("Window pos.")

        self.pbtn_debug_3.clicked.connect(lambda: print(self.geometry()))

        grid = QtWid.QGridLayout()
        grid.setVerticalSpacing(0)
        grid.addWidget(self.fill_TC_chart_random, 0, 0)
        grid.addWidget(self.pbtn_debug_1, 1, 0)
        grid.addWidget(self.pbtn_debug_2, 2, 0)
        grid.addItem(QtWid.QSpacerItem(1, 12), 3, 0)
        grid.addWidget(self.pbtn_debug_3, 4, 0)

        grp_debug.setLayout(grid)

        # Round up tab page
        # -------------------
        hbox1 = QtWid.QHBoxLayout()
        hbox1.addWidget(self.gw_DAQ_rate)
        hbox1.addWidget(grp_debug)
        hbox1.addStretch(1)
        hbox1.setAlignment(grp_debug, QtCore.Qt.AlignTop)

        self.tab_debug.setLayout(hbox1)

        def traverse(): pass # Spyder IDE outline item
        # ---------------------------------------------------------------------
        # ---------------------------------------------------------------------
        #
        #   TAB PAGE: traverse
        #
        # ---------------------------------------------------------------------
        # ---------------------------------------------------------------------

         # Traverse schematic image
        lbl_trav_img = QtWid.QLabel()
        lbl_trav_img.setPixmap(QtGui.QPixmap("Traverse_layout.png"))
        lbl_trav_img.setFixedSize(244, 240)

        grid = QtWid.QGridLayout()
        grid.addWidget(lbl_trav_img, 0, 0, QtCore.Qt.AlignTop)

        self.grpb_trav_img = QtWid.QGroupBox("Traverse schematic")
        self.grpb_trav_img.setStyleSheet(SS_GROUP)
        self.grpb_trav_img.setLayout(grid)

        # ---------------------------------------------------------------------
        # ---------------------------------------------------------------------
        #
        #   TAB PAGE: filling system
        #
        # ---------------------------------------------------------------------
        # ---------------------------------------------------------------------

        def FS_image(): pass # Spyder IDE outline item
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        #
        #   Filling system image
        #
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------

        grp_FSI = QtWid.QGroupBox("Schematic")
        grp_FSI.setStyleSheet(SS_GROUP)

        label_FS_img = QtWid.QLabel()
        pixmap_FS_img = QtGui.QPixmap("Filling_system_schematic_small.png")
        label_FS_img.setPixmap(pixmap_FS_img)
        #label_FS_img.setPixmap(pixmap_FS_img.scaled(400, 500,
        #                                            QtCore.Qt.KeepAspectRatio))

        grid = QtWid.QGridLayout()
        grid.addWidget(label_FS_img, 0, 0)

        grp_FSI.setLayout(grid)

        def FS_input_switches(): pass # Spyder IDE outline item
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        #
        #   Filling system input switches
        #
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------

        grp_ISW = QtWid.QGroupBox("Input switches")
        grp_ISW.setStyleSheet(SS_GROUP)

        self.prox_switch_1  = create_LED_indicator()
        self.prox_switch_2  = create_LED_indicator()
        self.prox_switch_3  = create_LED_indicator()
        self.prox_switch_4  = create_LED_indicator()
        self.floater_switch = create_LED_indicator()

        grid = QtWid.QGridLayout()
        grid.setVerticalSpacing(0)
        grid.addWidget(QtWid.QLabel("full barrel 1?"), 0, 0)
        grid.addWidget(QtWid.QLabel("full barrel 2?"), 1, 0)
        grid.addWidget(QtWid.QLabel("empty barrel?"), 2, 0)
        grid.addWidget(QtWid.QLabel("empty tunnel?"), 3, 0)
        grid.addWidget(QtWid.QLabel("full tunnel?"), 4, 0)
        grid.addWidget(self.prox_switch_1 , 0, 1)
        grid.addWidget(self.prox_switch_2 , 1, 1)
        grid.addWidget(self.prox_switch_3 , 2, 1)
        grid.addWidget(self.prox_switch_4 , 3, 1)
        grid.addWidget(self.floater_switch, 4, 1)
        grid.addWidget(QtWid.QLabel("prox. #1"), 0, 2)
        grid.addWidget(QtWid.QLabel("prox. #2"), 1, 2)
        grid.addWidget(QtWid.QLabel("prox. #3"), 2, 2)
        grid.addWidget(QtWid.QLabel("prox. #4"), 3, 2)
        grid.addWidget(QtWid.QLabel("floater") , 4, 2)
        grid.setColumnStretch(2, 1)
        grid.setAlignment(QtCore.Qt.AlignTop)

        grp_ISW.setLayout(grid)

        def FS_relays(): pass # Spyder IDE outline item
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        #
        #   Filling system relays
        #
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------

        grp_RB3 = QtWid.QGroupBox("Relays")
        grp_RB3.setStyleSheet(SS_GROUP)

        self.relay_3_MC = create_Toggle_button_2("")
        self.relay_3_MC.setMinimumWidth(156)
        self.relay_3_MC.clicked.connect(self.relay_3_manual_control)

        self.relay_3_1 = create_Relay_button()
        self.relay_3_2 = create_Relay_button()
        self.relay_3_3 = create_Relay_button()
        self.relay_3_4 = create_Relay_button()
        self.relay_3_5 = create_Relay_button()
        self.relay_3_6 = create_Relay_button()
        self.relay_3_7 = create_Relay_button()
        self.relay_3_8 = create_Relay_button()

        grid = QtWid.QGridLayout()
        grid.setVerticalSpacing(0)
        grid.addWidget(self.relay_3_MC, 0, 0, 1, 3, QtCore.Qt.AlignCenter)
        grid.addItem(QtWid.QSpacerItem(0, 10), 1, 0, 1, 3)
        grid.addWidget(QtWid.QLabel("filling_valve_1"), 2, 0)
        grid.addWidget(QtWid.QLabel("filling_valve_2"), 3, 0)
        grid.addWidget(QtWid.QLabel("filling_valve_3"), 4, 0)
        grid.addWidget(QtWid.QLabel("filling_valve_4"), 5, 0)
        grid.addWidget(QtWid.QLabel("filling_valve_5"), 6, 0)
        grid.addWidget(QtWid.QLabel("filling_valve_6"), 7, 0)
        grid.addWidget(QtWid.QLabel("filling_pump")   , 8, 0)
        grid.addWidget(QtWid.QLabel("n.c.")           , 9, 0)
        grid.addWidget(self.relay_3_1, 2, 1)
        grid.addWidget(self.relay_3_2, 3, 1)
        grid.addWidget(self.relay_3_3, 4, 1)
        grid.addWidget(self.relay_3_4, 5, 1)
        grid.addWidget(self.relay_3_5, 6, 1)
        grid.addWidget(self.relay_3_6, 7, 1)
        grid.addWidget(self.relay_3_7, 8, 1)
        grid.addWidget(self.relay_3_8, 9, 1)
        grid.addWidget(QtWid.QLabel("relay 3.1"), 2, 2)
        grid.addWidget(QtWid.QLabel("relay 3.2"), 3, 2)
        grid.addWidget(QtWid.QLabel("relay 3.3"), 4, 2)
        grid.addWidget(QtWid.QLabel("relay 3.4"), 5, 2)
        grid.addWidget(QtWid.QLabel("relay 3.5"), 6, 2)
        grid.addWidget(QtWid.QLabel("relay 3.6"), 7, 2)
        grid.addWidget(QtWid.QLabel("relay 3.7"), 8, 2)
        grid.addWidget(QtWid.QLabel("relay 3.8"), 9, 2)

        grp_RB3.setLayout(grid)

        def FS_programs(): pass # Spyder IDE outline item
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        #
        #   Filling system programs
        #
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------

        grp_FS = QtWid.QGroupBox("Automated programs")
        grp_FS.setStyleSheet(SS_GROUP)

        self.FS_exec_1 = create_Toggle_button("Idle")
        self.FS_exec_2 = create_Toggle_button("Barrel 1 to tunnel")
        self.FS_exec_3 = create_Toggle_button("Barrel 2 to tunnel")
        self.FS_exec_4 = create_Toggle_button("Tunnel to barrel 1")
        self.FS_exec_5 = create_Toggle_button("Tunnel to barrel 2")
        self.FS_exec_6 = create_Toggle_button("Barrel 1 to sewer")
        self.FS_exec_7 = create_Toggle_button("Barrel 2 to sewer")
        self.FS_exec_8 = create_Toggle_button("Tunnel to sewer")
        self.FS_exec_8.setMinimumWidth(138)

        self.FS_exec_button_list = np.array([None] * 8)
        self.FS_exec_button_list[FSM_FS_PROGRAMS.idle              ] = \
            self.FS_exec_1
        self.FS_exec_button_list[FSM_FS_PROGRAMS.barrel_1_to_tunnel] = \
            self.FS_exec_2
        self.FS_exec_button_list[FSM_FS_PROGRAMS.barrel_2_to_tunnel] = \
            self.FS_exec_3
        self.FS_exec_button_list[FSM_FS_PROGRAMS.tunnel_to_barrel_1] = \
            self.FS_exec_4
        self.FS_exec_button_list[FSM_FS_PROGRAMS.tunnel_to_barrel_2] = \
            self.FS_exec_5
        self.FS_exec_button_list[FSM_FS_PROGRAMS.barrel_1_to_sewer ] = \
            self.FS_exec_6
        self.FS_exec_button_list[FSM_FS_PROGRAMS.barrel_2_to_sewer ] = \
            self.FS_exec_7
        self.FS_exec_button_list[FSM_FS_PROGRAMS.tunnel_to_sewer   ] = \
            self.FS_exec_8

        self.FS_text_msgs = QtWid.QPlainTextEdit()
        self.FS_text_msgs.setVerticalScrollBarPolicy( \
            QtCore.Qt.ScrollBarAlwaysOff)
        self.FS_text_msgs.ensureCursorVisible()
        self.FS_text_msgs.setMinimumWidth(270)
        self.FS_text_msgs.setEnabled(False)
        self.FS_text_msgs.setReadOnly(True)
        self.FS_text_msgs.setStyleSheet(SS_TEXT_MSGS)
        self.FS_text_msgs.setFont(FONT_MONOSPACE)

        grid = QtWid.QGridLayout()
        grid.addWidget(self.FS_exec_1, 0, 0)
        grid.addWidget(self.FS_exec_2, 1, 0)
        grid.addWidget(self.FS_exec_3, 2, 0)
        grid.addWidget(self.FS_exec_4, 3, 0)
        grid.addWidget(self.FS_exec_5, 4, 0)
        grid.addWidget(self.FS_exec_6, 5, 0)
        grid.addWidget(self.FS_exec_7, 6, 0)
        grid.addWidget(self.FS_exec_8, 7, 0)
        grid.addWidget(self.FS_text_msgs, 0, 1, 8, 1)

        grp_FS.setLayout(grid)

        # Round up tab page
        # -------------------
        vbox1 = QtWid.QVBoxLayout()
        vbox1.addWidget(grp_ISW)
        vbox1.addWidget(grp_RB3)
        vbox1.setAlignment(grp_ISW, QtCore.Qt.AlignLeft)
        vbox1.setAlignment(grp_RB3, QtCore.Qt.AlignLeft)
        vbox1.setAlignment(QtCore.Qt.AlignTop)

        hbox1 = QtWid.QHBoxLayout()
        hbox1.addWidget(grp_FSI)
        hbox1.addLayout(vbox1)
        hbox1.addWidget(grp_FS)
        hbox1.addStretch(1)
        hbox1.setAlignment(grp_FS, QtCore.Qt.AlignTop)
        hbox1.setAlignment(grp_FSI, QtCore.Qt.AlignTop)
        #hbox1.setAlignment(QtCore.Qt.AlignLeft)

        self.tab_filling.setLayout(hbox1)

        # ---------------------------------------------------------------------
        # ---------------------------------------------------------------------
        #
        #   Round up full window
        #
        # ---------------------------------------------------------------------
        # ---------------------------------------------------------------------

        vbox = QtWid.QVBoxLayout(self)
        vbox.addLayout(hbox_top)
        vbox.addWidget(self.tabs)

    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------

    def relay_3_manual_control(self):
        if self.relay_3_MC.isChecked():
            self.relay_3_MC.setText("WARNING:\nMANUAL CONTROL")
            self.relay_3_1.setEnabled(True)
            self.relay_3_2.setEnabled(True)
            self.relay_3_3.setEnabled(True)
            self.relay_3_4.setEnabled(True)
            self.relay_3_5.setEnabled(True)
            self.relay_3_6.setEnabled(True)
            self.relay_3_7.setEnabled(True)
            self.relay_3_8.setEnabled(True)
        else:
            self.relay_3_MC.setText("Take manual control")
            self.relay_3_1.setEnabled(False)
            self.relay_3_2.setEnabled(False)
            self.relay_3_3.setEnabled(False)
            self.relay_3_4.setEnabled(False)
            self.relay_3_5.setEnabled(False)
            self.relay_3_6.setEnabled(False)
            self.relay_3_7.setEnabled(False)
            self.relay_3_8.setEnabled(False)

    def process_pbtn_heater_TC_all(self):
        # First: if any heater is hidden --> show all
        # Second: if all heaters are shown --> hide all
        """ Routine for when all 12 thermocouples are fine
        any_hidden = False
        for i in range(len(self.chkbs_heater_TC)):
            if (not self.chkbs_heater_TC[i].isChecked()):
                self.chkbs_heater_TC[i].setChecked(True)
                any_hidden = True

        if (not any_hidden):
            for i in range(len(self.chkbs_heater_TC)):
                self.chkbs_heater_TC[i].setChecked(False)
        """

        # Routine for when thermocouples 11 and 12 are broken
        any_hidden = False
        for i in range(10):
            if (not self.chkbs_heater_TC[i].isChecked()):
                self.chkbs_heater_TC[i].setChecked(True)
                any_hidden = True

        if (not any_hidden):
            for i in range(10):
                self.chkbs_heater_TC[i].setChecked(False)

        self.chkbs_heater_TC[10].setChecked(False)
        self.chkbs_heater_TC[11].setChecked(False)

    def process_pbtn_heater_TC_selection(self, heaters_idx_array):
        for i in range(len(self.chkbs_heater_TC)):
            if (np.any(heaters_idx_array == i)):
                self.chkbs_heater_TC[i].setChecked(True)
            else:
                self.chkbs_heater_TC[i].setChecked(False)

    def clear_all_charts(self):
        str_msg = "Are you sure you want to clear all charts?"
        reply = QtWid.QMessageBox.warning(self, "Clear charts", str_msg,
                                          QtWid.QMessageBox.Yes |
                                          QtWid.QMessageBox.No,
                                          QtWid.QMessageBox.No)

        if reply == QtWid.QMessageBox.Yes:
            [CH.clear() for CH in self.CHs_heater_TC]
            self.CH_flow_speed.clear()
            self.CH_chiller_setpoint.clear()
            self.CH_chiller_temp.clear()
            self.CH_tunnel_inlet.clear()
            self.CH_tunnel_outlet.clear()
            self.CH_set_pump_speed.clear()
            self.CH_power_PSU_1.clear()
            self.CH_power_PSU_2.clear()
            self.CH_power_PSU_3.clear()
            self.CH_DAQ_rate.clear()

    def toggle_visibility_debug_GUI(self, event=None):
        toggle_widget_visibility(self.lbl_tunnel_pump_mA)
        toggle_widget_visibility(self.lbl_tunnel_pump_bitV)
        toggle_widget_visibility(self.set_pump_speed_mA)
        toggle_widget_visibility(self.read_flow_rate_mA)
        toggle_widget_visibility(self.read_flow_rate_bitV)
        toggle_widget_visibility(self.set_flow_rate_m3h)
        toggle_widget_visibility(self.lbl_flow_rate_m3h)

        toggle_widget_visibility(self.lbl_read_GVF_P_diff_mA)
        toggle_widget_visibility(self.lbl_read_GVF_P_diff_bitV)
        toggle_widget_visibility(self.read_GVF_P_diff_mA)
        toggle_widget_visibility(self.read_GVF_P_diff_bitV)

    @QtCore.pyqtSlot(str)
    def set_text_qpbt_record(self, text_str):
        self.pbtn_record.setText(text_str)

def toggle_widget_visibility(my_widget):
    my_widget.setHidden(not my_widget.isHidden())

if __name__ == '__main__':
    exec(open("MHT_tunnel_control_v1p1.py").read())