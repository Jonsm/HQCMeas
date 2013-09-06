# -*- coding: utf-8 -*-
"""
"""
from traits.api import Str, Float
from traitsui.api import (View, Group, UItem, Label, HGroup,
                          LineCompleterEditor)
from time import sleep

from .base_tasks import SimpleTask
from .tools.task_decorator import make_stoppable, make_wait
from .tools.database_string_formatter import get_formatted_string

class PrintTask(SimpleTask):
    """Basic task which simply prints a message in stdout. Loopable.
    """

    loopable = True
    task_database_entries = ['message']
    message = Str('', preference = True)

    def __init__(self, *args, **kwargs):
        super(PrintTask, self).__init__(*args, **kwargs)
        self._define_task_view()

    @make_stoppable
    def process(self, *args, **kwargs):
        """
        """
        mess = get_formatted_string(self.message,
                                    self.task_path,
                                    self.task_database)
        self.write_in_database('message', mess)
        print mess

    def check(self, *args, **kwargs):
        """
        """
        mess = get_formatted_string(self.message,
                                    self.task_path,
                                    self.task_database)
        self.write_in_database('message', mess)
        return True

    def _update_database_entries(self):
        """
        """
        return self.task_database.list_accessible_entries(self.task_path)

    def _define_task_view(self):
        """
        """
        task_view = View(
                    Group(
                        UItem('task_name', style = 'readonly'),
                        HGroup(
                            Label('Message'),
                            UItem('message',
                                  editor = LineCompleterEditor(
                              entries_updater = self._update_database_entries)
                              ),
                            show_border = True,
                            ),
                        ),
                    )
        self.trait_view('task_view', task_view)

class SleepTask(SimpleTask):
    """
    """

    time = Float(preference = True)
    task_view = View(
                    Group(
                        UItem('task_name', style = 'readonly'),
                        HGroup(
                            Label('Time to sleep (s)'),
                            UItem('time'),
                            show_border = True,
                            ),
                        ),
                    )

    @make_stoppable
    @make_wait
    def process(self):
        """
        """
        sleep(self.time)

    def check(self, *args, **kwargs):
        """
        """
        return True