"""Analysis module for Databench."""

import os
import json
import random
import string
import fnmatch
import logging
import tornado.web
import tornado.websocket
from .datastore import Datastore

# utilities
try:
    from markdown import markdown
except ImportError:
    markdown = None

try:
    from docutils.core import publish_parts as rst
except ImportError:
    rst = None

from . import __version__ as DATABENCH_VERSION

log = logging.getLogger(__name__)


class Analysis(object):
    """Databench's analysis class.

    This contains the analysis code. Every browser connection corresponds to
    and instance of this class.

    **Initialize:** add an ``on_connect(self)`` or
    ``on_connect(self, request_args)`` method to your analysis class. The
    optional argument ``request_args`` contains a dictionary of parameters
    from the request url.

    **Incoming messages** are captured by specifying a class method starting
    with ``on_`` followed by the signal name. To capture the frontend signal
    ``run`` that is emitted with the JavaScript code

    .. code-block:: js

        // on the JavaScript frontend
        databench.emit('run', {my_param: 'helloworld'});

    use

    .. code-block:: python

        # here in Python
        def on_run(self, my_param):

    here. The entries of a dictionary will be used as keyword arguments in the
    function call; as in this example. If the emitted message is an array,
    the entries will be used as positional arguments in the function call.
    If the message is neither of type ``list`` nor ``dict`` (for example a
    plain ``string`` or ``float``), the function will be called with that
    as its first parameter.

    **Outgoing messages** are sent using ``emit(signal_name, message)``.
    For example, use

    .. code-block:: python

        self.emit('result', {'msg': 'done'})

    to send the signal ``result`` with the message ``{'msg': 'done'}`` to
    the frontend.

    """

    datastore_class = Datastore

    def __init__(self, id_=None):
        self.id_ = id_ if id_ else Analysis.__create_id()
        self.__datastore = Analysis.datastore_class(self.id_)

    def set_emit_fn(self, emit_fn):
        """Sets what the emit function for this analysis will be."""
        self.emit = emit_fn
        return self

    def add_data_change_cb(self, cb):
        self.__datastore.add_change_cb(cb)
        return self

    """Datastore."""

    @property
    def data(self):
        return self.__datastore

    """Events."""

    def on_connect(self):
        log.debug('on_connect called.')

    def on_disconnect(self):
        log.debug('on_disconnect called.')

    @staticmethod
    def __create_id():
        return ''.join(random.choice(string.ascii_letters + string.digits)
                       for _ in range(8))


class Meta(object):
    """
    Args:
        name (str): Name of this analysis. If ``signals`` is not specified,
            this also becomes the namespace for the WebSocket connection and
            has to match the frontend's :js:class:`Databench` ``name``.
        description (str): Usually the ``__doc__`` string of the analysis.
        analysis_class (:class:`databench.Analysis`): Object
            that should be instantiated for every new websocket connection.

    For standard use cases, you don't have to modify this class. However,
    If you want to serve more than the ``index.html`` page, say a
    ``details.html`` page, you can derive from this class and add this
    to the constructor

    .. code-block:: python

        self.blueprint.add_url_rule('/details.html', 'render_details',
                                    self.render_details)

    and add a new method to the class

    .. code-block:: python

        def render_details(self):
            return render_template(
                self.name+'/details.html',
                analysis_description=self.description
            )

    and create the file ``details.html`` similar to ``index.html``.

    """

    all_instances = []

    def __init__(
            self,
            name,
            description,
            analysis_class,
    ):
        Meta.all_instances.append(self)
        self.show_in_index = True
        self.name = name

        # find folder of all analyses
        analyses_path = os.path.join(os.getcwd(), 'analyses')
        if not os.path.exists(analyses_path):
            analyses_path = os.path.join(
                os.getcwd(), 'databench', 'analyses_packaged',
            )
        if not os.path.exists(analyses_path):
            log.info('Folder for {} not found.'.format(self.name))
        # find folder for this analysis
        analysis_path = os.path.join(analyses_path, self.name)

        self.info = {
            'logo_url': '/static/logo.svg',
            'title': 'Databench',
            'readme': None,
        }
        self.description = description
        self.analysis_class = analysis_class

        self.routes = [
            (r'/{}/static/(.*)'.format(self.name),
             tornado.web.StaticFileHandler,
             {'path': analysis_path}),

            (r'/{}/ws'.format(self.name),
             FrontendHandler,
             {'meta': self}),

            (r'/{}/(?P<template_name>.+\.html)'.format(self.name),
             RenderTemplate,
             {'template_path': analysis_path,
              'info': self.info}),

            (r'/{}/'.format(self.name),
             RenderTemplate,
             {'template_name': 'index.html',
              'template_path': analysis_path,
              'info': self.info}),
        ]

        # detect whether thumbnail.png is present
        if os.path.isfile(os.path.join(analysis_path, 'thumbnail.png')):
            self.thumbnail = 'thumbnail.png'

        # detect and render readme
        self.info['readme'] = self.readme(analysis_path)

        self.request_args = None

    def readme(self, analysis_path):
        readme_file = [os.path.join(analysis_path, n)
                       for n in os.listdir(analysis_path)
                       if fnmatch.fnmatch(n.lower(), 'readme.*')]
        readme_file = readme_file[0] if readme_file else None
        log.debug('Readme file: {}'.format(readme_file))
        if not readme_file:
            return None

        with open(readme_file, 'r') as f:
            r = f.read()

        # process readme
        if readme_file.lower().endswith('.md'):
            if markdown is not None:
                r = markdown(r)
            else:
                r = (
                    '<p>Install markdown with <b>pip install markdown</b>'
                    ' to render this readme file.</p>'
                ) + r
        if readme_file.lower().endswith('.rst'):
            if rst is not None:
                r = rst(r, writer_name='html')['html_body']
            else:
                r = (
                    '<p>Install rst rendering with <b>pip install docutils</b>'
                    ' to render this readme file.</p>'
                ) + r

        return r

    def run_action(self, analysis, fn_name, message='__nomessagetoken__'):
        """Executes an action in the analysis with the given message. It
        also handles the start and stop signals in case an action_id
        is given."""

        if analysis is None:
            return

        if not hasattr(analysis, fn_name):
            log.warning('Frontend wants to call {} which is not in the '
                        'Analysis class {}.'.format(fn_name, analysis))
            return

        # detect action_id
        action_id = None
        if isinstance(message, dict) and '__action_id' in message:
            action_id = message['__action_id']
            del message['__action_id']

        if action_id:
            analysis.emit('__action', {'id': action_id, 'status': 'start'})

        log.debug('calling {}'.format(fn_name))
        fn = getattr(analysis, fn_name)

        # Check whether this is a list (positional arguments)
        # or a dictionary (keyword arguments).
        if isinstance(message, list):
            fn(*message)
        elif isinstance(message, dict):
            fn(**message)
        elif message == '__nomessagetoken__':
            fn()
        else:
            fn(message)

        if action_id:
            analysis.emit('__action', {'id': action_id, 'status': 'end'})


class FrontendHandler(tornado.websocket.WebSocketHandler):

    def initialize(self, meta):
        self.meta = meta
        self.analysis = None

    def open(self):
        log.debug('WebSocket connection opened.')

    def on_close(self):
        log.debug('WebSocket connection closed.')
        self.meta.run_action(self.analysis, 'on_disconnect')

    def on_message(self, message):
        if message is None:
            log.debug('empty message received.')
            return

        message_data = json.loads(message)
        if '__connect' in message_data:
            if self.analysis is not None:
                log.error('Connection already has an analysis. Abort.')
                return

            analysis_id = message_data['__connect']
            log.debug('Instantiate analysis id {} ...'.format(analysis_id))
            self.analysis = self.meta.analysis_class(analysis_id)
            analysis_id = self.analysis.id_  # in case a new id was generated
            self.analysis.set_emit_fn(self.emit)
            log.info('Analysis {} instanciated.'.format(analysis_id))

            self.meta.run_action(self.analysis, 'on_connect')
            self.emit('__connect', {'analysis_id': analysis_id})
            log.info('Connected to analysis.')
            return

        if self.analysis is None:
            log.warning('no analysis connected. Abort.')
            return

        if 'signal' not in message_data or 'load' not in message_data:
            log.info('message not processed: '+message)
            return

        fn_name = 'on_'+message_data['signal']
        self.meta.run_action(self.analysis, fn_name, message_data['load'])

    def emit(self, signal, message):
        message = FrontendHandler.sanitize_message(message)
        try:
            self.write_message(json.dumps(
                {'signal': signal, 'load': message}
            ).encode('utf-8'))
        except tornado.websocket.WebSocketClosedError:
            pass
            # log.warning('WebSocket is closed. Cannot emit message: {}'
            #             ''.format(message))

    @staticmethod
    def sanitize_message(m):
        if isinstance(m, int) or isinstance(m, float):
            if m != m:
                m = 'NaN'
            elif isinstance(m, float) and m != m:
                m = 'NaN'
            elif m == float('inf'):
                m = 'inf'
            elif m == float('-inf'):
                m = '-inf'
        elif isinstance(m, list):
            for i, e in enumerate(m):
                m[i] = FrontendHandler.sanitize_message(e)
        elif isinstance(m, dict):
            for i in m:
                m[i] = FrontendHandler.sanitize_message(m[i])
        elif isinstance(m, (set, tuple)):
            m = list(m)
            for i, e in enumerate(m):
                m[i] = FrontendHandler.sanitize_message(e)
        elif hasattr(m, 'tolist'):  # for np.ndarray, np.generic
            m = m.tolist()
            for i, e in enumerate(m):
                m[i] = FrontendHandler.sanitize_message(e)
        return m


class RenderTemplate(tornado.web.RequestHandler):
    def initialize(self, template_name, template_path, info):
        self.template_loc = os.path.join(template_path, template_name)
        self.info = info

    def get(self):
        self.render(
            self.template_loc,
            info=self.info,
            databench_version=DATABENCH_VERSION,
        )
