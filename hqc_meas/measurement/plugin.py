# -*- coding: utf-8 -*-
#==============================================================================
# module : measure_plugin.py
# author : Matthieu Dartiailh
# license : MIT license
#==============================================================================
import logging
from collections import defaultdict
from inspect import cleandoc
from atom.api import (Typed, Unicode, Dict, ContainerList, List, Instance,
                      Tuple, ForwardTyped)
from time import sleep
from importlib import import_module
import enaml

from hqc_meas.utils.has_pref_plugin import HasPrefPlugin
from .engines.base_engine import BaseEngine, Engine
from .monitors.base_monitor import Monitor
from .headers.base_header import Header
from .checks.base_check import Check
from .editors.base_editor import Editor
from .measure import Measure


INVALID_MEASURE_STATUS = ['EDITING', 'SKIPPED', 'FAILED', 'COMPLETED',
                          'INTERRUPTED']

ENGINES_POINT = u'hqc_meas.measure.engines'

MONITORS_POINT = u'hqc_meas.measure.monitors'

HEADERS_POINT = u'hqc_meas.measure.headers'

CHECKS_POINT = u'hqc_meas.measure.checks'

EDITORS_POINT = u'hqc_meas.measure.editors'


def _workspace():
    from .workspace import MeasureSpace
    return MeasureSpace


class MeasurePlugin(HasPrefPlugin):
    """
    """
    #--- Public API -----------------------------------------------------------
    # Have to be here otherwise lose tons of infos when closing workspace

    # List of (module_path, manifest_name) which should be regitered on
    # startup.
    manifests = List(Tuple()).tag(pref=True)

    # Reference to the workspace if any.
    workspace = ForwardTyped(_workspace)

    # Currently edited measure.
    edited_measure = Typed(Measure)

    # Currently enqueued measures.
    enqueued_measures = ContainerList(Typed(Measure))

    # Currently run measure or last measure run.
    running_measure = Typed(Measure)

    # Dict holding the contributed Engine declarations.
    engines = Dict(Unicode(), Typed(Engine))

    # Currently selected engine represented by its id.
    selected_engine = Unicode().tag(pref=True)

    # Instance of the currently used engine.
    engine_instance = Instance(BaseEngine)

    # Dict holding the contributed Monitor declarations.
    monitors = Dict(Unicode(), Typed(Monitor))

    # Default monitors to use for new measures.
    default_monitors = List(Unicode()).tag(pref=True)

    # Dict holding the contributed Header declarations.
    headers = Dict(Unicode(), Typed(Header))

    # Default headers to use for new measures.
    default_headers = List(Unicode()).tag(pref=True)

    # Dict holding the contributed Check declarations.
    checks = Dict(Unicode(), Typed(Check))

    # Default checks to use for new measures.
    default_checks = List(Unicode()).tag(pref=True)

    # Dict holding the contributed Editor declarations
    editors = Dict(Unicode(), Typed(Editor))

    # Internal flags.
    flags = ContainerList()

    def start(self):
        """
        """
        super(MeasurePlugin, self).start()

        # Register contributed plugin.
        for path, manifest_name in self.manifests:
            self._register_manifest(path, manifest_name)

        # Refresh contribution and start observers.
        self._refresh_engines()
        self._refresh_monitors()
        self._refresh_headers()
        self._refresh_checks()
        self._refresh_editors()
        self._bind_observers()
        self._update_selected_engine({'value': self.selected_engine})

    def stop(self):
        """
        """
        # Unbind the observers.
        self._unbind_observers()

        # Unregister the plugin registered at start-up.
        for manifest_id in self._manifest_ids:
            self.workbench.unregister(manifest_id)

        # Clear ressources.
        self.engines.clear()
        self.monitors.clear()
        self.headers.clear()
        self.checks.clear()
        self.editors.clear()

    def start_measure(self, measure):
        """ Start a new measure.

        """
        self.flags.append('processing')

        logger = logging.getLogger(__name__)

        # Discard old monitors if there is any remaining.
        if self.running_measure:
            for monitor in self.running_measure.monitors.values():
                monitor.stop()

        measure.enter_running_state()
        self.running_measure = measure

        # Requesting profiles.
        profs = measure.store.get('profiles', set())
        core = self.workbench.get_plugin('enaml.workbench.core')

        com = u'hqc_meas.instr_manager.profiles_request'
        profiles, missing = core.invoke_command(com,
                                                {'profiles': list(profs)},
                                                self)
        if profs and not profiles:
            mes = cleandoc('''The instrument profiles requested for the
                           measurement {} are not available, the measurement
                           cannot be performed.'''.format(measure.name))
            logger.info(mes)

            # Simulate a message coming from the engine.
            done = {'value': ('SKIPPED', 'Failed to get requested profiles')}

            # Break a potential high statck as this function will not exit
            # if a new measure is started.
            enaml.application.deferred_call(self._listen_to_engine, done)
            return

        if profs:
            logger.info(cleandoc('''The use of the instrument profiles has been
                                granted by the manager.'''))

        measure.root_task.run_time.update({'profiles': profiles})

        # Run internal test to check communication.
        res, errors = measure.run_checks(self.workbench, True, True)
        if not res:
            mes = cleandoc('''The measure failed to pass the built-in tests,
                           this is likely related to a connection error to an
                           instrument.
                           '''.format(measure.name))
            logger.warn(mes)

            # Simulate a message coming from the engine.
            done = {'value': ('FAILED', 'Failed to pass the built in tests')}

            # Break a potential high statck as this function will not exit
            # if a new measure is started.
            enaml.application.deferred_call(self._listen_to_engine, done)
            return

        # Collect headers.
        measure.collect_headers(self.workbench)

        # Start the engine if it has not already been done.
        if not self.engine_instance:
            decl = self.engines[self.selected_engine]
            self.engine_instance = decl.factory(decl, self.workbench)

            # Connect signal handler to engine.
            self.engine_instance.observe('done', self._listen_to_engine)

        engine = self.engine_instance

        # Call engine prepare to run method.
        entries = measure.collect_entries_to_observe()
        engine.prepare_to_run(measure.name, measure.root_task, entries)

        measure.status = 'RUNNING'
        measure.infos = 'The measure is running'

        # Get a ref to the main window.
        ui_plugin = self.workbench.get_plugin('enaml.workbench.ui')
        # Connect new monitors, and start them.
        for monitor in measure.monitors.values():
            engine.observe('news', monitor.process_news)
            monitor.start(ui_plugin.window)

        logger.info('''Starting measure {}.'''.format(measure.name))
        # Ask the engine to start the measure.
        engine.run()

    def stop_measure(self):
        """ Stop the currently active measure.

        """
        self.flags.append('stop_attempt')
        self.engine_instance.stop()

    def stop_processing(self):
        """ Stop processing the enqueued measure.

        """
        self.flags.append('stop_attempt')
        self.flags.append('stop_processing')
        if 'processing' in self.flags:
            self.flags.remove('processing')
        self.engine_instance.exit()

    def force_stop_measure(self):
        """ Force the engine to stop performing the current measure.

        """
        self.engine_instance.force_stop()

    def force_stop_processing(self):
        """ Force the engine to exit and stop processing measures.

        """
        self.flags.append('stop_processing')
        if 'processing' in self.flags:
            self.flags.remove('processing')
        self.engine_instance.force_exit()

    def find_next_measure(self):
        """ Find the next runnable measure in the queue.

        Returns
        -------
        measure : Measure
            First valid measurement in the queue or None if there is no
            available measure.

        """
        enqueued_measures = self.enqueued_measures
        i = 0
        measure = None
        # Look for a measure not being currently edited. (Can happen if the
        # user is editing the second measure when the first measure ends).
        while i < len(enqueued_measures):
            measure = enqueued_measures[i]
            if measure.status in INVALID_MEASURE_STATUS:
                i += 1
                measure = None
            else:
                break

        return measure

    #--- Private API ----------------------------------------------------------

    # Manifests ids of the plugin registered at start up.
    _manifest_ids = List(Unicode())

    # Dict storing which extension declared which editor.
    _editor_extensions = Typed(defaultdict, (list,))

    # Dict storing which extension declared which engine.
    _engine_extensions = Typed(defaultdict, (list,))

    # Dict storing which extension declared which header.
    _header_extensions = Typed(defaultdict, (list,))

    # Dict storing which extension declared which check.
    _check_extensions = Typed(defaultdict, (list,))

    # Dict storing which extension declared which monitor.
    _monitor_extensions = Typed(defaultdict, (list,))

    def _listen_to_engine(self, change):
        """ Observer for the engine notifications.

        """
        status, infos = change['value']
        self.running_measure.status = status
        self.running_measure.infos = infos

        # Disconnect monitors.
        engine = self.engine_instance
        if engine:
            engine.unobserve('news')

        # If we are supposed to stop, stop.
        if engine and'stop_processing' in self.flags:
            self.stop_processing()
            i = 0
            while engine and engine.active:
                sleep(0.5)
                i += 1
                if i > 10:
                    self.force_stop_processing()
            self.flags = []

        # Otherwise find the next measure, if there is none stop the engine.
        else:
            meas = self.find_next_measure()
            if meas is not None:
                self.flags = []
                self.start_measure(meas)
            else:
                if engine:
                    self.stop_processing()
                    i = 0
                    while engine.active:
                        sleep(0.5)
                        i += 1
                        if i > 10:
                            self.force_stop_processing()
                self.flags = []

    def _register_manifest(self, path, manifest_name):
        """ Register a manifest given its module name and its name.

        NB : the path should be a dot separated string referring to a package
        in sys.path. It should be an absolute path.
        """
        try:
            with enaml.imports():
                module = import_module(path)
            manifest = getattr(module, manifest_name)
            plugin = manifest()
            self.workbench.register(plugin)
            self._manifest_ids.append(plugin.id)

        except Exception:
            logger = logging.getLogger(__name__)
            logger.error('Failed to register manifest: {}'.format(path))

    def _refresh_engines(self):
        """ Refresh the list of known engines.

        """
        workbench = self.workbench
        point = workbench.get_extension_point(ENGINES_POINT)
        extensions = point.extensions
        if not extensions:
            self.engines.clear()
            self._engine_extensions.clear()
            if self.selected_engine:
                logger = logging.getLogger(__name__)
                msg = cleandoc('''Previously selected engine is not available
                                anymore : {}'''.format(self.selected_engine))
                logger.warn(msg)
                self.selected_engine = ''
            return

        # Get the engines declarations for all extensions.
        new_extensions = defaultdict(list)
        old_extensions = self._engine_extensions
        for extension in extensions:
            if extensions in old_extensions:
                engines = old_extensions[extension]
            else:
                engines = self._load_engines(extension)
            new_extensions[extension].extend(engines)

        # Create mapping between engine id and declaration.
        engines = {}
        for extension in extensions:
            for engine in new_extensions[extension]:
                if engine.id in engines:
                    msg = "engine '%s' is already registered"
                    raise ValueError(msg % engine.id)
                if engine.factory is None:
                    msg = "engine '%s' does not declare a factory"
                    raise ValueError(msg % engine.id)
                engines[engine.id] = engine

        # Check whether the selected engine still exists.
        if self.selected_engine and self.selected_engine not in engines:
            logger = logging.getLogger(__name__)
            msg = cleandoc('''Previously selected engine is not available
                            anymore : {}'''.format(self.selected_engine))
            logger.warn(msg)
            self.selected_engine = ''

        self.engines = engines

    def _load_engines(self, extension):
        """ Load the Engine object for the given extension.

        Parameters
        ----------
        extension : Extension
            The extension object of interest.

        Returns
        -------
        engines : list(Engine)
            The Engine object declared by the extension.

        """
        workbench = self.workbench
        engines = extension.get_children(Engine)
        if extension.factory is not None and not engines:
            for engine in extension.factory(workbench):
                if not isinstance(engine, Engine):
                    msg = "extension '%s' created non-Engine."
                    args = (extension.qualified_id)
                    raise TypeError(msg % args)
                engines.append(engine)

        return engines

    def _update_selected_engine(self, change):
        """ Observer ensuring that the selected engine is informed when it is
        selected and deselected.

        """
        if 'oldvalue' in change:
            old = change['oldvalue']
            if old in self.engines:
                engine = self.engines[old]
                engine.post_deselection(engine, self.workbench)

        new = change['value']
        if new and new in self.engines:
            engine = self.engines[new]
            engine.post_selection(engine, self.workbench)

    def _refresh_monitors(self):
        """ Refresh the list of known monitors.

        """
        workbench = self.workbench
        point = workbench.get_extension_point(MONITORS_POINT)
        extensions = point.extensions
        if not extensions:
            self.monitors.clear()
            self._monitor_extensions.clear()
            return

        # Get the monitors declarations for all extensions.
        new_extensions = defaultdict(list)
        old_extensions = self._monitor_extensions
        for extension in extensions:
            if extensions in old_extensions:
                monitors = old_extensions[extension]
            else:
                monitors = self._load_monitors(extension)
            new_extensions[extension].extend(monitors)

        # Create mapping between monitor id and declaration.
        monitors = {}
        for extension in extensions:
            for monitor in new_extensions[extension]:
                if monitor.id in monitors:
                    msg = "monitor '%s' is already registered"
                    raise ValueError(msg % monitor.id)
                if monitor.factory is None:
                    msg = "monitor '%s' does not declare a factory"
                    raise ValueError(msg % monitor.id)
                monitors[monitor.id] = monitor

        self.monitors = monitors

    def _load_monitors(self, extension):
        """ Load the Monitor object for the given extension.

        Parameters
        ----------
        extension : Extension
            The extension object of interest.

        Returns
        -------
        monitor : list(Monitor)
            The list of Monitor declared by the extension.

        """
        workbench = self.workbench
        monitors = extension.get_children(Monitor)
        if extension.factory is not None and not monitors:
            for monitor in extension.factory(workbench):
                if not isinstance(monitor, Monitor):
                    msg = "extension '%s' created non-Monitor."
                    args = (extension.qualified_id)
                    raise TypeError(msg % args)
                monitors.append(monitor)

        return monitors

    def _refresh_headers(self):
        """ Refresh the list of known headers.

        """
        workbench = self.workbench
        point = workbench.get_extension_point(HEADERS_POINT)
        extensions = point.extensions
        if not extensions:
            self.headers.clear()
            self._header_extensions.clear()
            return

        # Get the headers declarations for all extensions.
        new_extensions = defaultdict(list)
        old_extensions = self._header_extensions
        for extension in extensions:
            if extensions in old_extensions:
                headers = old_extensions[extension]
            else:
                headers = self._load_headers(extension)
            new_extensions[extension].extend(headers)

        # Create mapping between header id and declaration.
        headers = {}
        for extension in extensions:
            for header in new_extensions[extension]:
                if header.id in headers:
                    msg = "header '%s' is already registered"
                    raise ValueError(msg % header.id)
                if header.build_header is None:
                    msg = "header '%s' does not declare a build_header"
                    raise ValueError(msg % header.id)
                headers[header.id] = header

        self.headers = headers

    def _load_headers(self, extension):
        """ Load the Header object for the given extension.

        Parameters
        ----------
        extension : Extension
            The extension object of interest.

        Returns
        -------
        header : list(Header)
            The list of Header declared by the extension.

        """
        workbench = self.workbench
        headers = extension.get_children(Header)
        if extension.factory is not None and not headers:
            for header in extension.factory(workbench):
                if not isinstance(header, Header):
                    msg = "extension '%s' created non-Header."
                    args = (extension.qualified_id)
                    raise TypeError(msg % args)
                headers.append(header)

        return headers

    def _refresh_checks(self):
        """ Refresh the list of known checks.

        """
        workbench = self.workbench
        point = workbench.get_extension_point(CHECKS_POINT)
        extensions = point.extensions
        if not extensions:
            self.checks.clear()
            self._check_extensions.clear()
            return

        # Get the checks declarations for all extensions.
        new_extensions = defaultdict(list)
        old_extensions = self._check_extensions
        for extension in extensions:
            if extensions in old_extensions:
                checks = old_extensions[extension]
            else:
                checks = self._load_checks(extension)
            new_extensions[extension].extend(checks)

        # Create mapping between check id and declaration.
        checks = {}
        for extension in extensions:
            for check in new_extensions[extension]:
                if check.id in checks:
                    msg = "check '%s' is already registered"
                    raise ValueError(msg % check.id)
                if check.perform_check is None:
                    msg = "check '%s' does not declare a perform_check"
                    raise ValueError(msg % check.id)
                checks[check.id] = check

        self.checks = checks

    def _load_checks(self, extension):
        """ Load the Check object for the given extension.

        Parameters
        ----------
        extension : Extension
            The extension object of interest.

        Returns
        -------
        check : list(Check)
            The list of Check declared by the extension.

        """
        workbench = self.workbench
        checks = extension.get_children(Check)
        if extension.factory is not None and not checks:
            for check in extension.factory(workbench):
                if not isinstance(check, Check):
                    msg = "extension '%s' created non-Check."
                    args = (extension.qualified_id)
                    raise TypeError(msg % args)
                checks.append(check)

        return checks

    def _refresh_editors(self):
        """ Refresh the list of known editors.

        """
        workbench = self.workbench
        point = workbench.get_extension_point(EDITORS_POINT)
        extensions = point.extensions
        if not extensions:
            self.editors.clear()
            self._editor_extensions.clear()
            return

        # Get the editors declarations for all extensions.
        new_extensions = defaultdict(list)
        old_extensions = self._editor_extensions
        for extension in extensions:
            if extensions in old_extensions:
                editors = old_extensions[extension]
            else:
                editors = self._load_editors(extension)
            new_extensions[extension].extend(editors)

        # Create mapping between editor id and declaration.
        editors = {}
        for extension in extensions:
            for editor in new_extensions[extension]:
                if editor.id in editors:
                    msg = "editor '%s' is already registered"
                    raise ValueError(msg % editor.id)
                if editor.factory is None:
                    msg = "editor '%s' does not declare a factory"
                    raise ValueError(msg % editor.id)
                editors[editor.id] = editor

        self.editors = editors

    def _load_editors(self, extension):
        """ Load the Check object for the given extension.

        Parameters
        ----------
        extension : Extension
            The extension object of interest.

        Returns
        -------
        editor : list(Editor)
            The list of Editor declared by the extension.

        """
        workbench = self.workbench
        editors = extension.get_children(Editor)
        if extension.factory is not None and not editors:
            for editor in extension.factory(workbench):
                if not isinstance(editor, Editor):
                    msg = "extension '%s' created non-Editor."
                    args = (extension.qualified_id)
                    raise TypeError(msg % args)
                editors.append(editor)

        return editors

    def _bind_observers(self):
        """ Setup the observers for the plugin.

        """
        workbench = self.workbench

        point = workbench.get_extension_point(ENGINES_POINT)
        point.observe('extensions', self._update_engines)

        point = workbench.get_extension_point(MONITORS_POINT)
        point.observe('extensions', self._update_monitors)

        point = workbench.get_extension_point(HEADERS_POINT)
        point.observe('extensions', self._update_headers)

        point = workbench.get_extension_point(CHECKS_POINT)
        point.observe('extensions', self._update_checks)

        point = workbench.get_extension_point(EDITORS_POINT)
        point.observe('extensions', self._update_editors)

        # Start this observer only now as I don't want it to run when the
        # preferences updates the selected_engine as no engine is known yet
        # (but I want to register auto-registering manifests before refreshing)
        self.observe('selected_engine', self._update_selected_engine)

    def _unbind_observers(self):
        """ Remove the observers for the plugin.

        """
        workbench = self.workbench

        point = workbench.get_extension_point(ENGINES_POINT)
        point.unobserve('extensions', self._update_engines)

        point = workbench.get_extension_point(MONITORS_POINT)
        point.unobserve('extensions', self._update_monitors)

        point = workbench.get_extension_point(HEADERS_POINT)
        point.unobserve('extensions', self._update_headers)

        point = workbench.get_extension_point(CHECKS_POINT)
        point.unobserve('extensions', self._update_checks)

        point = workbench.get_extension_point(EDITORS_POINT)
        point.unobserve('extensions', self._update_editors)

    def _update_engines(self, change):
        """
        """
        self._refresh_engines()

    def _update_monitors(self, change):
        """
        """
        self._refresh_monitors()

    def _update_headers(self, change):
        """
        """
        self._refresh_headers()

    def _update_checks(self, change):
        """
        """
        self._refresh_checks()

    def _update_editors(self, change):
        """
        """
        self._refresh_editors()
