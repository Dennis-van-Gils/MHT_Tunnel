#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MHT_read_file
Reads in a log file acquired with the Python MHT Tunnel Control program.

Dennis van Gils
29-06-2018
"""

import numpy as np
from pathlib import Path

class MHT():
    def __init__(self):
        self.filename      = ''
        self.header        = ['']
        self.gravity               = np.nan
        self.area_meas_section     = np.nan
        self.GVF_porthole_distance = np.nan
        self.density_liquid        = np.nan
        self.time          = np.array([])
        self.wall_time     = np.array([])
        self.Q_tunnel_setp = np.array([])
        self.Q_tunnel      = np.array([])
        self.S_pump_setp   = np.array([])
        self.Q_bubbles     = np.array([])
        self.Pdiff_GVF     = np.array([])
        self.T_TC_01       = np.array([])
        self.T_TC_02       = np.array([])
        self.T_TC_03       = np.array([])
        self.T_TC_04       = np.array([])
        self.T_TC_05       = np.array([])
        self.T_TC_06       = np.array([])
        self.T_TC_07       = np.array([])
        self.T_TC_08       = np.array([])
        self.T_TC_09       = np.array([])
        self.T_TC_10       = np.array([])
        self.T_TC_11       = np.array([])
        self.T_TC_12       = np.array([])
        self.T_inlet       = np.array([])
        self.T_outlet      = np.array([])
        self.T_chill_setp  = np.array([])
        self.T_chill       = np.array([])
        self.P_PSU_1       = np.array([])
        self.P_PSU_2       = np.array([])
        self.P_PSU_3       = np.array([])

def MHT_read_file(filepath=None):
    """ Reads in a log file acquired with the Python MHT Tunnel Control program
    Args:
        filepath (pathlib.Path, str): path to the data file to open

    Returns: instance of MHT class
    """
    if isinstance(filepath, str):
        filepath = Path(filepath)

    if not isinstance(filepath, Path):
        raise Exception("Wrong type passed to MHT_read_file(). "
                        "Should be (str) or (pathlib.Path).")

    if not filepath.is_file():
        raise Exception("File can not be found\n %s" % filepath._str)

    with filepath.open() as f:
        mht = MHT()

        # Scan the first lines for the start of the header and data sections
        MAX_LINES = 100  # Stop scanning after this number of lines
        str_header = []
        success = False
        for i_line in range(MAX_LINES):
            str_line = f.readline().strip()

            if str_line.upper() == "[HEADER]":
                # Simply skip
                pass
            elif str_line.upper() == "[DATA]":
                # Found data section. Exit loop.
                i_line_data = i_line
                success = True
                break
            else:
                # We must be in the header section now
                str_header.append(str_line)

        if not success:
            raise Exception("Incorrect file format. Could not find [DATA] "
                            "section.")

        # Read in all data columns including column names
        tmp_table = np.genfromtxt(filepath._str, delimiter='\t',
                                  names=True,
                                  skip_header=i_line_data+2)

        # Parse info out of the header
        for line in str_header:
            if line.find("Gravity [m2/s]:") == 0:
                parts = line.split("\t")
                mht.gravity = float(parts[1])
            if line.find("Area meas. section [m2]:") == 0:
                parts = line.split("\t")
                mht.area_meas_section = float(parts[1])
            if line.find("GVF porthole distance [m]:") == 0:
                parts = line.split("\t")
                mht.GVF_porthole_distance = float(parts[1])
            if line.find("Density liquid [kg/m3]:") == 0:
                parts = line.split("\t")
                mht.density_liquid = float(parts[1])

        # Rebuild into a Matlab style 'struct'
        mht.filename      = filepath.name[0:-4]
        mht.header        = str_header
        mht.time          = tmp_table['time']
        mht.wall_time     = tmp_table['wall_time']
        mht.Q_tunnel_setp = tmp_table['Q_tunnel_setp']
        mht.Q_tunnel      = tmp_table['Q_tunnel']
        mht.S_pump_setp   = tmp_table['S_pump_setp']
        mht.Q_bubbles     = tmp_table['Q_bubbles']
        mht.Pdiff_GVF     = tmp_table['Pdiff_GVF']
        mht.T_TC_01       = tmp_table['T_TC_01']
        mht.T_TC_02       = tmp_table['T_TC_02']
        mht.T_TC_03       = tmp_table['T_TC_03']
        mht.T_TC_04       = tmp_table['T_TC_04']
        mht.T_TC_05       = tmp_table['T_TC_05']
        mht.T_TC_06       = tmp_table['T_TC_06']
        mht.T_TC_07       = tmp_table['T_TC_07']
        mht.T_TC_08       = tmp_table['T_TC_08']
        mht.T_TC_09       = tmp_table['T_TC_09']
        mht.T_TC_10       = tmp_table['T_TC_10']
        mht.T_TC_11       = tmp_table['T_TC_11']
        mht.T_TC_12       = tmp_table['T_TC_12']
        mht.T_inlet       = tmp_table['T_inlet']
        mht.T_outlet      = tmp_table['T_outlet']
        mht.T_chill_setp  = tmp_table['T_chill_setp']
        mht.T_chill       = tmp_table['T_chill']
        mht.P_PSU_1       = tmp_table['P_PSU_1']
        mht.P_PSU_2       = tmp_table['P_PSU_2']
        mht.P_PSU_3       = tmp_table['P_PSU_3']

    return mht