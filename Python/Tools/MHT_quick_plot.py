#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MHT_quick_plot.py

Plot timeseries of recorded run for quick inspection and saves image to disk

Dennis van Gils
10-10-2018
"""

import sys
import os
import numpy as np

import tkinter
from tkinter import filedialog

import matplotlib as mpl
import matplotlib.pyplot as plt

from MHT_read_file import MHT_read_file

# Characters
CHAR_PM    = u"\u00B1"
CHAR_DEG   = u"\u00B0"

# Colors
cm = np.array([[199, 0  , 191],
               [0  , 128, 255],
               [0  , 255, 255],
               [20 , 200, 20 ],
               [255, 255, 0  ],
               [255, 0  , 0  ]])/255

# ------------------------------------------------------------------------------
#   MHT_quick_plot
# ------------------------------------------------------------------------------

def MHT_quick_plot(mht, filename):
    """
    Args:
        mht (MHT_read_file.MHT): MHT data structure
    """

    # --------------------------------------------------------------------------
    #   Prepare figure
    # --------------------------------------------------------------------------

    mpl.style.use('dark_background')
    mpl.rcParams['font.size'] = 12
    #mpl.rcParams['font.weight'] = "bold"
    mpl.rcParams['axes.titlesize'] = 14
    mpl.rcParams['axes.labelsize'] = 14
    mpl.rcParams["axes.titleweight"] = "bold"
    #mpl.rcParams["axes.labelweight"] = "bold"
    mpl.rcParams['lines.linewidth'] = 2
    mpl.rcParams['grid.color'] = "0.25"

    fig1 = plt.figure(figsize=(16, 10), dpi=90)
    fig1.canvas.set_window_title("%s" % mht.filename)

    ax1 = fig1.add_subplot(3, 2, 1)
    ax4 = fig1.add_subplot(3, 2, 2, sharex=ax1)
    ax2 = fig1.add_subplot(3, 2, 3, sharex=ax1)
    ax5 = fig1.add_subplot(3, 2, 4, sharex=ax1)
    ax3 = fig1.add_subplot(3, 2, 5, sharex=ax1)
    ax6 = fig1.add_subplot(3, 2, 6, sharex=ax1)

    # --------------------------------------------------------------------------
    #   Plot
    # --------------------------------------------------------------------------

    # Short-hand
    t = mht.time

    T_TCs = ([mht.T_TC_01, mht.T_TC_02, mht.T_TC_03, mht.T_TC_04,
              mht.T_TC_05, mht.T_TC_06, mht.T_TC_07, mht.T_TC_08,
              mht.T_TC_09, mht.T_TC_10, mht.T_TC_11, mht.T_TC_12])

    # -------------------------------------------------------------
    #   Heater temperatures
    # -------------------------------------------------------------

    for i in range(12):
        if i < 6:
            color = cm[i]
            width = 2
        else:
            color = cm[11 - i]
            width = 4
        ax1.plot(t, T_TCs[i], '-', color=color, linewidth=width,
                 label=("#%02i" % (i+1)))

    ax1.set_title("%s\nHeater temperatures (%s2.2 K)" %
                  (mht.filename, CHAR_PM))
    ax1.set_xlabel("time (s)")
    ax1.set_ylabel("temperature (%sC)" % CHAR_DEG)
    ax1.grid(True)

    # -------------------------------------------------------------
    #   Tunnel temperatures
    # -------------------------------------------------------------

    ax2.plot(t, mht.T_outlet, color=cm[5], label="outlet")
    ax2.plot(t, mht.T_inlet, color=cm[1], label="inlet")

    if not np.all(np.isnan(mht.T_ambient)):
        ax2.plot(t, mht.T_ambient, color=[1, 1, 1], label="ambient")

    ax2.set_title("Tunnel temperatures (%s0.03 K)" % CHAR_PM)
    ax2.set_xlabel("time (s)")
    ax2.set_ylabel("temperature (%sC)" % CHAR_DEG)
    ax2.grid(True)

    # -------------------------------------------------------------
    #   Chiller temperatures
    # -------------------------------------------------------------

    ax3.plot(t, mht.T_chill_setp, '-', color=cm[4], lineWidth=4,
             label="setp.")
    ax3.plot(t, mht.T_chill, color=cm[2], label="chiller")

    ax3.set_title("Chiller temperatures (%s0.1 K)" % CHAR_PM)
    ax3.set_xlabel("time (s)")
    ax3.set_ylabel("temperature (%sC)" % CHAR_DEG)
    ax3.grid(True)

    # -------------------------------------------------------------
    #   Tunnel speed
    # -------------------------------------------------------------

    v_flow = mht.Q_tunnel / mht.area_meas_section / 36.0  # [cm/s]

    area_meas_section = "%.3f" % mht.area_meas_section
    if mht.area_meas_section == 0.012:
        area_meas_section = "0.3 x 0.04"
    elif mht.area_meas_section == 0.018:
        area_meas_section = "0.3 x 0.06"
    elif mht.area_meas_section == 0.024:
        area_meas_section = "0.3 x 0.08"

    color = cm[5]
    ax4.plot(t, v_flow, color=color, label="v_flow")
    ax4.set_title("Meas. section: %s m\u00B2\nTunnel flow" % area_meas_section)
    ax4.set_xlabel("time (s)")
    ax4.set_ylabel("flow speed (cm/s)", color=color)
    ax4.tick_params(axis='y', labelcolor=color)
    ax4.grid(True)

    color = cm[1]
    ax4b = ax4.twinx()
    ax4b.plot(t, mht.S_pump_setp, '-',  color=color,
              label="S_pump_setp")
    ax4b.set_ylabel("set pump speed (%)", color=color)
    ax4b.tick_params(axis='y', labelcolor=color)

    # -------------------------------------------------------------
    #   PSU power
    # -------------------------------------------------------------

    if not np.isnan(mht.P_PSU_1.sum()):
        ax5.plot(t, mht.P_PSU_1, color=cm[5], label="#1")

    if not np.isnan(mht.P_PSU_2.sum()):
        ax5.plot(t, mht.P_PSU_2, color=cm[3], label="#2")

    if not np.isnan(mht.P_PSU_3.sum()):
        ax5.plot(t, mht.P_PSU_3, color=cm[1], label="#3")

    ax5.set_title("PSU power (%s0.3 W)" % CHAR_PM)
    ax5.set_xlabel("time (s)")
    ax5.set_ylabel("power (W)")
    ax5.grid(True)

    # -------------------------------------------------------------
    #   Gas volume fraction (GVF)
    # -------------------------------------------------------------

    GVF_pct = (mht.Pdiff_GVF * 1e2 / mht.gravity /
               mht.GVF_porthole_distance / mht.density_liquid *
               100)

    color = cm[5]
    ax6.plot(t, GVF_pct, color=color, label="GVF_pct")
    ax6.set_title("Bubble injection")
    ax6.set_xlabel("time (s)")
    ax6.set_ylabel("gas vol. fraction (%s0.5 %%)" % CHAR_PM, color=color)
    ax6.tick_params(axis='y', labelcolor=color)
    ax6.grid(True)

    color = cm[1]
    ax6b = ax6.twinx()
    ax6b.plot(t, mht.Q_bubbles, '-',  color=color, label="Q_bubbles")
    ax6b.set_ylabel("air flow rate (ln/min)", color=color)
    ax6b.tick_params(axis='y', labelcolor=color)

    # --------------------------------------------------------------------------
    #   Final make-up
    # --------------------------------------------------------------------------
    ax_w = 0.34
    ax_h = 0.23

    ax1.set_position ([0.07, 0.707, ax_w, ax_h])
    ax2.set_position ([0.07, 0.387, ax_w, ax_h])
    ax3.set_position ([0.07, 0.067, ax_w, ax_h])
    ax4.set_position ([0.57, 0.707, ax_w, ax_h])
    ax4b.set_position([0.57, 0.707, ax_w, ax_h])
    ax5.set_position ([0.57, 0.387, ax_w, ax_h])
    ax6.set_position ([0.57, 0.067, ax_w, ax_h])
    ax6b.set_position([0.57, 0.067, ax_w, ax_h])

    for ax in [ax1, ax2, ax3, ax5]:
        ax.legend(loc='upper left', bbox_to_anchor=(1, 1.035))

    # --------------------------------------------------------------------------
    #   Save figure
    # --------------------------------------------------------------------------

    img_format = "png"
    parts = os.path.splitext(filename)
    fn_save = "%s.%s" % (parts[0], img_format)
    plt.savefig(fn_save, dpi=90, orientation='portrait', papertype='A4',
                format=img_format, transparent=False, frameon=False)
    print("Saved image: %s" % fn_save)

# ------------------------------------------------------------------------------
#   Main
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    # Check for optional input arguments
    filename_supplied = False
    for arg in sys.argv[1:]:
        filename = arg
        filename_supplied = True

    root = tkinter.Tk()
    root.withdraw()     # Disable root window

    if not filename_supplied:
        filename = filedialog.askopenfilename(
                    initialdir=os.getcwd(),
                    title="Select data file",
                    filetypes=(("text files", "*.txt"),
                               ("all files", "*.*")))
    if filename == '':
        sys.exit(0)

    root.destroy()      # Close file dialog

    print("Reading file: %s" % filename)
    mht = MHT_read_file(filename)

    """
    print("\n[HEADER]")
    for line in mht.header:
        print("  %s" % line)
    """

    MHT_quick_plot(mht, filename)
    plt.show()