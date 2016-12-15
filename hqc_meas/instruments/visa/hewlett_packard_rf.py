# -*- coding: utf-8 -*-
#==============================================================================
# module : HP8276A.py
# author : Nathanael Cottet
# license : MIT license
#==============================================================================
"""
This module defines drivers for old fashioned Hewlett Packard Synthesized 
                                        Signal Generators using VISA library.

:Contains:
    HewlettPackard8276A

"""

from ..driver_tools import (InstrIOError, instrument_property,
                            secure_communication)
from ..visa_tools import VisaInstrument
from visa import VisaTypeError
from textwrap import fill
from inspect import cleandoc
import re


class HewlettPackard8276A(VisaInstrument):
    """
    Generic driver for  Hewlett Packard 8276A
    Synthesized Signal Generators, using the VISA library.

    This driver does not give access to all the functionnality of the
    instrument but you can extend it if needed. See the documentation of
    the driver_tools module for more details about writing instruments
    drivers.

    Parameters
    ----------
    see the `VisaInstrument` parameters

    Attributes
    ----------
    frequency_unit : str
        Frequency unit used by the driver. The default unit is 'GHz'. Other
        valid units are : 'MHz', 'KHz', 'Hz'
    frequency : float, instrument_property
        Fixed frequency of the output signal.
    power : float, instrument_property
        Fixed power of the output signal.
    output : bool, instrument_property
        State of the output 'ON'(True)/'OFF'(False).

    Notes
    -----
    This driver has been written for the HP8276A Synthsize Signal Generator  but might work
    for other models using the same HP-IB commands.

    """
    def __init__(self, connection_info, caching_allowed=True,
                 caching_permissions={}, auto_open=True):

        super(HewlettPackard8276A, self).__init__(connection_info,
                                                        caching_allowed,
                                                        caching_permissions,
                                                        auto_open)
        self.frequency_unit = 'GHz'

    @instrument_property
    @secure_communication()
    def frequency(self):
        """No frequency getter for this instrument
        """
        

    @frequency.setter
    @secure_communication()
    def frequency(self, value):
        """Frequency setter method
        """
        self.write('REN')
        unit = self.frequency_unit
        if unit == 'GHz':
            value = value*10**6
        elif unit == 'MHz':
            value = value*10**3
        elif unit == 'KHz':
            value = value
        ref = 10**7
        Nzeros = 0
        c = value
        while c < ref:
            Nzeros = Nzeros + 1
            c = c * 10
        self.write('P'+'0'*Nzeros+str(int(value))+'Z0')

    @instrument_property
    @secure_communication()
    def power(self):
        """No power getter for this instrument
        """

    @power.setter
    @secure_communication()
    def power(self, value):
        """Power setter method
        """
        self.write('REN')
        if value > 3 or value < - 120:
            mess = fill(cleandoc('''Instrument cannot set the 
                        requested power''').format(value), 80)
            raise VisaTypeError(mess)
        if value > 0:
            self.write('K0L'+str(int(3-value)))
        else:
            power_range = int(-value) / 10
            vernier = int(-value) % 10 + 3
            if power_range == -100:
                power_range = ':'
            elif power_range == -110:
                power_range = ';'
            if vernier > 9:
                vernier = (':',';','<')[vernier - 10]
            self.write('K'+str(power_range)+'L'+str(vernier))

    @instrument_property
    @secure_communication()
    def output(self):
        """No output getter for this instrument
        """

    @output.setter
    @secure_communication()
    def output(self, value):
        """Output setter method
        """
        self.write('REN')
        on = re.compile('on', re.IGNORECASE)
        off = re.compile('off', re.IGNORECASE)
        if on.match(value) or value == 1:
            self.write('O1')
        elif off.match(value) or value == 0:
            self.write('O0')
        else:
            mess = fill(cleandoc('''The invalid value {} was sent to
                        switch_on_off method''').format(value), 80)
            raise VisaTypeError(mess)

DRIVERS = {'HewlettPackard8276A': HewlettPackard8276A}
