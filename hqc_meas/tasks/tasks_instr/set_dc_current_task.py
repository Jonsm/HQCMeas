# -*- coding: utf-8 -*-
# =============================================================================
# module : hqc_meas/tasks/task_instr/set_dc_voltage_task.py
# author : Matthieu Dartiailh & Long Nguyen & Nathanael Cottet
# license : MIT license
# =============================================================================
"""
"""
from atom.api import (Float, Str, set_default)

import time
import logging
from inspect import cleandoc

from hqc_meas.tasks.api import (InstrumentTask,
                                InterfaceableTaskMixin)


class SetDCCurrentTask(InterfaceableTaskMixin, InstrumentTask):
    """Set a DC current to the specified value.

    The user can choose to limit the rate by choosing an appropriate back step
    (larger step allowed), and a waiting time between each step.

    """
    #: Target value for the source (dynamically evaluated)
    target_value = Str().tag(pref=True)

    #: Largest allowed step when changing the output of the instr.
    back_step = Float().tag(pref=True)

    #: Largest allowed voltage
    safe_max = Float(0.0).tag(pref=True)

    #: Time to wait between changes of the output of the instr.
    delay = Float(0.01).tag(pref=True)

    loopable = True
    task_database_entries = set_default({'current': 0.01})

    driver_list = ['Yokogawa7651']

    def check(self, *args, **kwargs):
        """
        """
        test, traceback = super(SetDCCurrentTask, self).check(*args, **kwargs)
        if self.target_value:
            try:
                val = self.format_and_eval_string(self.target_value)
                self.write_in_database('current', val)
            except Exception as e:
                test = False
                traceback[self.task_path + '/' + self.task_name + '-mA'] = \
                    cleandoc('''Failed to eval the target value formula
                        {} : '''.format(self.target_value, e))

        return test, traceback

    def i_perform(self, value=None):
        """
        """
        if not self.driver:
            self.start_driver()
        if self.driver.owner != self.task_name:
            self.driver.owner = self.task_name            
            if hasattr(self.driver, 'function') and\
                    self.driver.function != 'CURR':
                log = logging.getLogger()
                mes = cleandoc('''Instrument assigned to task {} is not
                    configured to output a current'''.format(self.task_name))
                log.fatal(mes)
                self.root_task.should_stop.set()
                
        setter = lambda value: setattr(self.driver, 'current', value)
        current_value = getattr(self.driver, 'current')
        
        print 'Setting current'
        self.smooth_set(value, setter, current_value)

    def smooth_set(self, target_value, setter, current_value):
        """ Smoothly set the current.

        target_value : float
            Current to reach.

        setter : callable
            Function to set the current, should take as single argument the
            value.

        """
        if target_value is not None:
            value = target_value*10**-3
        else:
            value = self.format_and_eval_string(self.target_value)*10**-3

        if self.safe_max*10**-3 and self.safe_max*10**-3 < abs(value):
            raise ValueError(cleandoc('''Requested current {} exceeds safe max
                                      : '''.format(value)))

        last_value = current_value

        if abs(last_value - value) < 1e-12:
            self.write_in_database('current', value)
            return

        elif self.back_step == 0:
            self.write_in_database('current', value)
            setter(value)
            return

        else:
            if (value - last_value)/self.back_step > 0:
                step = self.back_step*10**-3
            else:
                step = -self.back_step*10**-3

        if abs(value-last_value) > abs(step):
            while not self.root_task.should_stop.is_set():
                # Avoid the accumulation of rounding errors
                last_value = round(last_value + step, 9)
                setter(last_value)
                if abs(value-last_value) > abs(step):
                    time.sleep(self.delay)
                else:
                    break

        if not self.root_task.should_stop.is_set():
            setter(value)
            self.write_in_database('current', value)
            return

        self.write_in_database('current', last_value)


KNOWN_PY_TASKS = [SetDCCurrentTask]