#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MHT_quick_plot_missing.py

Plot timeseries of recorded run for quick inspection and saves image to disk.

Will scan all data textfiles in the current folder and only those that are
missing a plot figure will be processed.

Dennis van Gils
29-06-2018
"""

import os
import re

import MHT_read_file
import MHT_quick_plot

# ------------------------------------------------------------------------------
#   Main
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    my_path = os.getcwd()
    file_list = ([f for f in os.listdir(my_path)
                 if os.path.isfile(os.path.join(my_path, f))])

    for filename in file_list:
        # Look for files matching: ######_###### [+any extra chars] .txt
        p = re.compile('\d{6}_\d{6}(.*?)\.(txt|TXT)$')
        if p.match(filename):
            # Found a matching file
            # Now check if the same filename exists ending with .png
            filename_png = filename[0:-4] + ".png"

            if not os.path.isfile(filename_png):
                # Figure does not yet exists. Create.
                print("Reading file: %s" % filename)
                mht = MHT_read_file.MHT_read_file(filename)
                MHT_quick_plot.MHT_quick_plot(mht, filename)