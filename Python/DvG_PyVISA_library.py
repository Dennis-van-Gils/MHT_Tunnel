#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dennis van Gils
30-01-2018
"""

import visa

# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------

def open_resource_safely(rm, address, name=""):
    """
    Tries to open the visa (GPIB/serial/USB) device at the given address.
    Subsequently tries to clear the device. When the device concerns a GPIB
    instrument the identity of the device is queried and stored. When
    successfull returns the visa device instance, otherwise returns None.

    Args:
        rm      -- instance of visa.ResourceManager
        address -- address of the visa device to be opened
        idn     -- the identity of the device in case of a GPIB instrument
                   ("*IDN?")
        name    -- extra attribute that will be added to the returned device
                   instance, usefull for printing the name of the device onto
                   screen

    Return:
        The visa device instance, when succesful. Otherwise None.

    06-01-2017, Dennis van Gils
    """

    try:
        device = rm.open_resource(address)
        device.clear()
        if device.__class__.__name__ == "GPIBInstrument":
            device.idn = device.query("*IDN?")
        device.name = name
        return device
    except visa.VisaIOError:
        print("ERROR: Device is offline at address %s" % address)
        print("Check instrument and cable")
        return None
    except:
        raise

# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------

def find_visa_device_by_name(rm, str_name):
    """
    Scans over all VISA devices and search for those whose model name contains
    the string as passed by 'str_name'. Returns a tuple of two lists containing
    resp. the VISA device adresses and the VISA device names of the found
    matches.

    Args:
        rm       -- instance of visa.ResourceManager
        str_name -- part of the VISA name attribute string to search for

    Return:
        tuple(device_adresses[], device_names[])

    Usage:
        (device_adresses, device_names) = find_visa_device_by_name(rm,
                                                                   "Arduino")
    """

    visa_devices = rm.list_resources()
    matching_device_addresses = []
    matching_device_names = []

    print("Scanning all VISA devices...")
    for i_device in range(len(visa_devices)):
        try:
            device = rm.open_resource(visa_devices[i_device])
        except:
            print("  Failed to open " + visa_devices[i_device])
            continue
        try:
            name = device.get_visa_attribute(
                    visa.constants.VI_ATTR_INTF_INST_NAME)
            print("  " + name)
            device.close()
            if name.find(str_name) >= 0:
                matching_device_addresses.append(visa_devices[i_device])
                matching_device_names.append(name)
        except:
            device.close()

    print("")
    return (matching_device_addresses, matching_device_names)

# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------

def resolve_Arduino_1_2(rm, Arduino_device_adresses, Arduino_device_names,
                        baud_rate=9600):
    """
    Open serial connection to each Arduino address and determine which one is
    Arduino_#1 and which one is Arduino_#2. Returns the VISA device instances
    to the respective Arduinos as a tuple, ordered (Arduino_#1, Arduino_#2).
    """

    Ard1 = []
    Ard2 = []

    for i_Arduino in range(len(Arduino_device_adresses)):
        this_address = Arduino_device_adresses[i_Arduino]
        try:
            tmp = rm.open_resource(this_address, baud_rate=baud_rate)
        except:
            print("ERROR: Failed to open " + this_address)
            continue

        tmp.write_termination = "\n"
        tmp.read_termination = "\n"
        tmp.timeout = 2000

        try:
            query_ans = tmp.query("id?")
        except:
            print("ERROR: Failed to get the ID response of " + this_address)
            continue

        if query_ans.find("Arduino_#1") >= 0:
            Ard1 = tmp
            Ard1.name = "Ard1"
            print("Found Arduino_#1 at " + Arduino_device_names[i_Arduino])
            #print("Operating at baud rate: " + Ard1.query("baud?"))

        elif query_ans.find("Arduino_#2") >= 0:
            Ard2 = tmp
            Ard2.name = "Ard2"
            print("Found Arduino_#2 at " + Arduino_device_names[i_Arduino])
            #print("Operating at baud rate: " + Ard2.query("baud?"))

    if Ard1 == []:
        print("\nCRITICAL ERROR: Could not find Arduino_#1")
    if Ard2 == []:
        print("\nCRITICAL ERROR: Could not find Arduino_#2")

    return (Ard1, Ard2)