# -*- coding: utf-8 -*-
"""
"""

from threading import Thread

def make_stoppable(function_to_decorate):
    """
    """
    def decorator(*args, **kwargs):
        if args[0].root_task.should_stop.is_set():
            return

        function_to_decorate(*args, **kwargs)
        decorator.__name__ = function_to_decorate.__name__
        decorator.__doc__ = function_to_decorate.__doc__

    return decorator


def make_parallel(process):
    """This decorator should be used when there is no need to wait for the
    process method to return to start the next task,ie the process method
    decorated don't use any data succeptible to be corrupted by the next task.
    """
    def wrapper(*args, **kwargs):

        object = args[0]
        thread = Thread(group = None,
                        target = process,
                        args = args,
                        kwargs = kwargs)
        threads = object.task_database.get_value('root', 'threads')
        threads.append(thread)

        return thread.start()

    return wrapper

def make_wait(process):
    """This decorator should be used when the process method need to access
    data in the database or need to be sure that physical quantities reached
    their expected values.
    """
    def wrapper(*args, **kwargs):

        object = args[0]
        threads = object.task_database.get_value('root', 'threads')
        for thread in threads:
            thread.join()
        return process(*args, **kwargs)

    return wrapper