# -*- coding: utf-8 -*-
"""
Created on Wed Sep 19 18:52:40 2018

@author: local.la
"""

import sys
import visa
import time

visa.log_to_screen()
rm = visa.ResourceManager()
psu = rm.open_resource("USB0::0x0957::0x8707::US15M3727P::INSTR", timeout=4000)

while True:
    psu.query("err?")   # Some stuff to do
    psu.query("*idn?")  # Some stuff to do
    tick = time.time()
    print ((psu.stb & 0b100) == 0b100)
    done_in = time.time() - tick
    print("Done in %.3f" % done_in)
    if (done_in) > 1:
        sys.stdout.flush()
        sys.exit(0)