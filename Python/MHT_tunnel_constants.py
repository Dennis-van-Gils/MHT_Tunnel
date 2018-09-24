#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Defines constants regarding data acquisition and device i/o operations.

Note: Constants concerning GUI elements should be defined in UI_MainWindow.py
only exception being the chart history lengths

Dennis van Gils
24-09-2018
"""

from enum import IntEnum, unique
from pathlib import Path

# Update intervals in [ms]
UPDATE_INTERVAL_ARDUINOS = 100      # 100  [ms]
UPDATE_INTERVAL_PT104    = 1000     # 1000 [ms], PT100 logger
UPDATE_INTERVAL_MFC      = 200      # 200  [ms], mass flow controllers
UPDATE_INTERVAL_CHILLER  = 1000     # 1000 [ms]
UPDATE_INTERVAL_PSUs     = 1000     # 1000 [ms]
UPDATE_INTERVAL_TRAVs    = 250      # 250  [ms]

# Stripchart update intervals in [ms]
UPDATE_INTERVAL_CHARTS   = 1000     # 1000 [ms]

# Data acquisition (DAQ) rate quality checker
CALC_DAQ_RATE_EVERY_N_ITER = round(1e3/UPDATE_INTERVAL_ARDUINOS)  # Near 1 sec

# Chart history (CH) buffer sizes in [samples].
# Multiply this with the corresponding UPDATE_INTERVAL constants to get the
# history size in time.
CH_SAMPLES_HEATER_TC    = 1800      # @ MUX_1_SCANNING_INTERVAL  --> 30 min
CH_SAMPLES_HEATER_POWER = 1800
CH_SAMPLES_FLOW_SPEED   = 18000     # @ UPDATE_INTERVAL_ARDUINOS --> 30 min
CH_SAMPLES_PT104        = 1800      # @ UPDATE_INTERVAL_PT104    --> 30 min
CH_SAMPLES_CHILLER      = 1800      # @ UPDATE_INTERVAL_CHILLER  --> 30 min
CH_SAMPLES_MUX2         = 1800      # @ UPDATE_INTERVAL_CHILLER  --> 30 min
CH_SAMPLES_DAQ_RATE     = 1800      # @ UPDATE_INTERVAL_DAQ_RATE &
                                    # CALC_DAQ_RATE_EVERY_N_ITER --> 30 min

# Total number of heaters with embedded thermocouples
N_HEATER_TC = 12

# Over-temperature protection
OTP_MAX_TEMP_DEGC = 95              # 95 [deg C]

# MUX 1: read out thermocouples inside heaters
# Agilent Technologies 34972A
MUX_1_VISA_ADDRESS      = "USB0::0x0957::0x2007::MY49018071::INSTR"
MUX_1_SCANNING_INTERVAL = 1000      # 1000 [ms]
MUX_1_SCAN_LIST         = "(@301:310)"
MUX_1_SCPI_COMMANDS     = [
        "rout:open %s" % MUX_1_SCAN_LIST,
        "conf:temp TC,J,%s" % MUX_1_SCAN_LIST,
        "unit:temp C,%s" % MUX_1_SCAN_LIST,
        "sens:temp:tran:tc:rjun:type INT,%s" % MUX_1_SCAN_LIST,
        "sens:temp:tran:tc:check ON,%s" % MUX_1_SCAN_LIST,
        "sens:temp:nplc 1,%s" % MUX_1_SCAN_LIST,
        "rout:scan %s" % MUX_1_SCAN_LIST]

# MUX 2: read out thermistors
# HEWLETT-PACKARD 34970A
MUX_2_VISA_ADDRESS      = "GPIB::09::INSTR"
MUX_2_SCANNING_INTERVAL = 500      # 1000 [ms]
MUX_2_SCAN_LIST         = "(@101)"
MUX_2_SCPI_COMMANDS = [
        "rout:open %s" % MUX_2_SCAN_LIST,
        "conf:res 1e5,%s" % MUX_2_SCAN_LIST,
        "sens:res:nplc 1,%s" % MUX_2_SCAN_LIST,
        "rout:scan %s" % MUX_2_SCAN_LIST]

# Measurement section cross-sectional areas, used to transform the flow rate
# from m3/h to m/s
# AMS: area measurement section [m2]
AMS_1 = 0.3 * 0.08              # [m2]
AMS_2 = 0.3 * 0.06              # [m2]
AMS_3 = 0.3 * 0.04              # [m2]

# The maximum flow rate that corresponds to 20 mA output of the mass flow meter
# NOTE: this can be explicitly set in the flow meter parameter menu
QMAX_FLOW_METER = 80            # [m3/h]

# Min and max values for the temperature setpoint that can be send to the
# chiller over RS232. Note that these values are separate from the internal
# alarm values set in the chiller.
CHILLER_MIN_TEMP_DEG_C = 10.0   # [deg C]
CHILLER_MAX_TEMP_DEG_C = 36.0   # [deg C]

# VISA addresses of the Keysight PSUs
VISA_ADDRESS_PSU_1 = "USB0::0x0957::0x8707::US15M3727P::INSTR"
VISA_ADDRESS_PSU_2 = "USB0::0x0957::0x8707::US15M3728P::INSTR"
VISA_ADDRESS_PSU_3 = "USB0::0x0957::0x8707::US15M3726P::INSTR"

# Serial number of Bronkhorst mass flow controller # 1.
# This will be used to scan over all serial ports and try to find the device.
SERIAL_MFC_1 = "M16216843A"

# Picotech PT-104 settings
PT104_IP_ADDRESS    = "10.10.100.2"
PT104_PORT          = 1234
PT104_ENA_CHANNELS  = [1, 1, 0, 0]
PT104_GAIN_CHANNELS = [1, 1, 0, 0]

# Gas volume fraction estimation
GRAVITY = 9.81                  # [m/s2]
GVF_PORTHOLE_DISTANCE = 0.96    # [m]

# Compax3 traverse controllers
SERIAL_TRAV_HORZ = "4409980001"
SERIAL_TRAV_VERT = "4319370001"

# Config files
PATH_CONFIG_MEAS_SECTION = Path("config/measurement_section.txt")
PATH_CONFIG_ARD1         = Path("config/port_Arduino_1.txt")
PATH_CONFIG_ARD2         = Path("config/port_Arduino_2.txt")
PATH_CONFIG_CHILLER      = Path("config/port_ThermoFlex_chiller.txt")
PATH_CONFIG_MFC_1        = Path("config/port_Bronkhorst_MFC_1.txt")
PATH_CONFIG_PSU_1        = Path("config/settings_Keysight_PSU_1.txt")
PATH_CONFIG_PSU_2        = Path("config/settings_Keysight_PSU_2.txt")
PATH_CONFIG_PSU_3        = Path("config/settings_Keysight_PSU_3.txt")
PATH_CONFIG_TRAV_HORZ    = Path("config/port_Compax3_trav_horz.txt")
PATH_CONFIG_TRAV_VERT    = Path("config/port_Compax3_trav_vert.txt")

@unique
class FSM_FS_PROGRAMS(IntEnum):
    # From the Arduino C-code:
    # enum FSM_FS_PROGRAMS : uint8_t {FSM_FS_PROGRAMS_idle,
    #                                 FSM_FS_PROGRAMS_barrel_1._to_tunnel,
    #                                 FSM_FS_PROGRAMS_barrel_2_to_tunnel,
    #                                 FSM_FS_PROGRAMS_tunnel_to_barrel_1,
    #                                 FSM_FS_PROGRAMS_tunnel_to_barrel_2,
    #                                 FSM_FS_PROGRAMS_barrel_1_to_sewer,
    #                                 FSM_FS_PROGRAMS_barrel_2_to_sewer,
    #                                 FSM_FS_PROGRAMS_tunnel_to_sewer};
    #
    # These identities must match exactly in Python
    # They indicate the program that is currently running on Arduino #2 in the
    # Finite State Machine (FSM) controlling the filling system (FS)
    idle               = 0
    barrel_1_to_tunnel = 1
    barrel_2_to_tunnel = 2
    tunnel_to_barrel_1 = 3
    tunnel_to_barrel_2 = 4
    barrel_1_to_sewer  = 5
    barrel_2_to_sewer  = 6
    tunnel_to_sewer    = 7