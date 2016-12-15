# -*- coding: utf-8 -*-
# =============================================================================
# module : hqc_meas/tasks/task_instr/AWG_start_task.py
# author : Nathanael Cottet
# license : MIT license
# =============================================================================
"""
"""
from hqc_meas.tasks.api import (InstrumentTask)
from inspect import cleandoc
from atom.api import (Str)

class AWGStartTask(InstrumentTask):
    """Start or stop the AWG pulse sequence loop after setting the trigger as required. 
    Need to be called after Phase Alazar task (for turning on) or after 
    Phase Alazar Task is over (for turning off).
    """

    driver_list = ['AWG5014B']
    
    on_off = Str().tag(pref=True)

    def check(self, *args, **kwargs):
        """
        Check that the user entered 0 or 1 and nothing else
        """
        test, traceback = super(AWGStartTask, self).check(*args, **kwargs)
                                                             
        if self.on_off != '0' and self.on_off != '1':
            test = False
            traceback[self.task_path + '/' + self.task_name] = \
                                    cleandoc('''Enter 0 for OFF, 1 for ON''')
        
        return test, traceback

    def perform(self):
        """
        Simply turning on or off the AWG
        """
        if not self.driver:
            self.start_driver()
        running_state = self.driver.running
        if self.on_off == '0':
            if running_state != '2 : Intrument is running':
                print 'WARNING: AWG already stopped or waiting for a trigger'
            self.driver.running = 'STOP'
        
        if self.on_off == '1':
            if running_state != '0 : Instrument has stopped':
                print 'WARNING: AWG already running'           
            self.driver.running = 'RUN'
        
       
KNOWN_PY_TASKS = [AWGStartTask]