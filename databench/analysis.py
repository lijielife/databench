"""Analysis module for Databench."""

import os
import json
import time
import gevent
import logging
import subprocess
import geventwebsocket
import zmq.green as zmq
from flask import Blueprint, render_template


class Analysis(object):
    """Databench's analysis class.

    This contains the analysis code. Every browser connection corresponds to
    and instance of this class.

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

    here.

    **Outgoing messages** are sent using ``emit(signal_name, message)``.
    For example, use

    .. code-block:: python

        self.emit('result', {'msg': 'done'})

    to send the signal ``result`` with the message ``{'msg': 'done'}`` to
    the frontend.

    """

    def __init__(self):
        pass

    def set_emit_fn(self, emit_fn):
        """Sets what the emit function for this analysis will be."""
        self.emit = emit_fn

    """Events."""

    def onall(self, message_data):
        logging.debug('onall called.')

    def on_connect(self):
        logging.debug('on_connect called.')

    def on_disconnect(self):
        logging.debug('on_disconnect called.')


class Meta(object):
    """
    Args:
        name (str): Name of this analysis. If ``signals`` is not specified,
            this also becomes the namespace for the WebSocket connection and
            has to match the frontend's :js:class:`Databench` ``name``.
        import_name (str): Usually the file name ``__name__`` where this
            analysis is instantiated.
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
            import_name,
            description,
            analysis_class,
    ):
        Meta.all_instances.append(self)
        self.show_in_index = True

        self.name = name
        self.import_name = import_name
        self.description = description
        self.analysis_class = analysis_class

        analyses_path = 'analyses'
        if not os.path.exists(os.getcwd()+'/'+analyses_path):
            analyses_path = 'analyses_packaged'

        # detect whether thumbnail.png is present
        if os.path.isfile(os.getcwd()+'/'+analyses_path+'/' +
                          self.name+'/thumbnail.png'):
            self.thumbnail = 'thumbnail.png'

        self.blueprint = Blueprint(
            name,
            import_name,
            template_folder=os.getcwd()+'/'+analyses_path,
            static_folder=os.getcwd()+'/'+analyses_path+'/'+self.name,
            static_url_path='/static',
        )
        self.blueprint.add_url_rule('/', 'render_index', self.render_index)

        self.sockets = None

    def render_index(self):
        """Renders the main analysis frontend template."""
        return render_template(
            self.name+'/index.html',
            analysis_description=self.description
        )

    def wire_sockets(self, sockets, url_prefix=''):
        self.sockets = sockets
        self.sockets.add_url_rule(url_prefix+'/ws', 'ws_serve', self.ws_serve)

    def instantiate_analysis_class(self):
        return self.analysis_class()

    def ws_serve(self, ws):
        """Handle a new websocket connection."""
        logging.debug('ws_serve()')

        def emit(signal, message):
            try:
                ws.send(json.dumps({'signal': signal, 'message': message}))
            except geventwebsocket.WebSocketError, e:
                logging.info('websocket closed. could not send: '+signal +
                             ' -- '+str(message))

        def emitAction(action_id, status):
            try:
                ws.send(json.dumps({'action_id': action_id, 'status': status}))
            except geventwebsocket.WebSocketError, e:
                logging.info('websocket could not send action: '+action_id +
                             ' -- '+str(status))

        analysis_instance = self.instantiate_analysis_class()
        logging.debug("analysis instantiated")
        analysis_instance.set_emit_fn(emit)
        greenlets = []
        greenlets.append(gevent.Greenlet.spawn(
            analysis_instance.on_connect
        ))

        def process_message(message):
            if message is None:
                logging.debug('empty message received.')
                return

            message_data = json.loads(message)
            analysis_instance.onall(message_data)
            if 'signal' in message_data and 'message' in message_data:
                fn_name = 'on_'+message_data['signal']
                if hasattr(self.analysis_class, fn_name):
                    logging.debug('calling '+fn_name)

                    # detect whether an action_id should be registered
                    action_id = None
                    if '__action_id' in message_data['message']:
                        action_id = message_data['message']['__action_id']
                        del message_data['message']['__action_id']

                    # wrap the action
                    def spawn_action():
                        action_id_local = action_id
                        if action_id_local:
                            emitAction(action_id_local, 'start')

                        # Check whether this is a list (positional arguments)
                        # or a dictionary (keyword arguments).
                        if isinstance(message_data['message'], list):
                            getattr(analysis_instance, fn_name)(
                                *message_data['message']
                            )
                        elif isinstance(message_data['message'], dict):
                            getattr(analysis_instance, fn_name)(
                                **message_data['message']
                            )
                        else:
                            getattr(analysis_instance, fn_name)(
                                message_data['message']
                            )

                        if action_id_local:
                            emitAction(action_id_local, 'end')

                    # every 'on_' is processed in a separate greenlet
                    greenlets.append(gevent.Greenlet.spawn(spawn_action))
                else:
                    logging.warning('frontend wants to call '
                                    'on_'+message_data['signal']+' which is '
                                    'not in the Analysis class.')
            else:
                logging.info('message not processed: '+message)

        while True:
            try:
                message = ws.receive()
                logging.debug('received message: '+str(message))
                process_message(message)
            except geventwebsocket.WebSocketError, e:
                break

        # disconnected
        logging.debug("disconnecting analysis instance")
        gevent.killall(greenlets)
        analysis_instance.on_disconnect()


class AnalysisZMQ(Analysis):

    def __init__(self, namespace, analysis_id, zmq_publish):
        self.namespace = namespace
        self.analysis_id = analysis_id
        self.zmq_publish = zmq_publish

    def onall(self, message_data):
        msg = {
            '__analysis_id': self.analysis_id,
            '__databench_namespace': self.namespace,
            'message': message_data,
        }
        self.zmq_publish.send_json(msg)
        logging.debug('onall called with: '+str(msg))

    def on_connect(self):
        msg = {
            '__analysis_id': self.analysis_id,
            '__databench_namespace': self.namespace,
            'message': {'signal': 'connect', 'message': {}},
        }
        self.zmq_publish.send_json(msg)
        logging.debug('on_connect called')

    def on_disconnect(self):
        msg = {
            '__analysis_id': self.analysis_id,
            '__databench_namespace': self.namespace,
            'message': {'signal': 'disconnect', 'message': {}},
        }
        self.zmq_publish.send_json(msg)
        logging.debug('on_disconnect called')


class MetaZMQ(Meta):
    """A Meta class that pipes all messages to ZMQ and back.

    The entire ZMQ interface of Databench is defined here and in
    :class`AnalysisZMQ`.

    """

    def __init__(
            self,
            name,
            import_name,
            description,

            executable,
            zmq_publish,
            port_subscribe=None,
    ):
        Meta.__init__(self, name, import_name, description, AnalysisZMQ)

        self.zmq_publish = zmq_publish

        self.zmq_analysis_id = 0
        self.zmq_analyses = {}
        self.zmq_confirmed = False

        # check whether we have to determine port_subscribe ourselves first
        if port_subscribe is None:
            socket = zmq.Context().socket(zmq.PUB)
            port_subscribe = socket.bind_to_random_port(
                'tcp://127.0.0.1',
                min_port=3000, max_port=9000,
            )
            socket.unbind('tcp://127.0.0.1:'+str(port_subscribe))
            logging.debug('determined: port_subscribe='+str(port_subscribe))

        # zmq subscription to listen for messages from backend
        logging.debug('main listening on port: '+str(port_subscribe))
        self.zmq_sub = zmq.Context().socket(zmq.SUB)
        self.zmq_sub.connect('tcp://127.0.0.1:'+str(port_subscribe))
        self.zmq_sub.setsockopt(zmq.SUBSCRIBE, '')

        # @copy_current_request_context
        def zmq_listener():
            while True:
                msg = self.zmq_sub.recv_json()
                self.zmq_confirmed = True
                logging.debug('main ('+') received '
                              'msg: '+str(msg))
                if '__analysis_id' in msg and \
                   msg['__analysis_id'] in self.zmq_analyses:
                    analysis = self.zmq_analyses[msg['__analysis_id']]
                    del msg['__analysis_id']

                    if 'message' in msg and \
                       'signal' in msg['message'] and \
                       'message' in msg['message']:
                        analysis.emit(msg['message']['signal'],
                                      msg['message']['message'])
                    else:
                        logging.debug('dont understand this message: ' +
                                      str(msg))
                else:
                    logging.debug('__analysis_id not in message or '
                                  'AnalysisZMQ with that id not found.')
        self.zmq_listener = gevent.Greenlet.spawn(zmq_listener)

        # launch the language kernel process
        self.kernel_process = subprocess.Popen(executable, shell=False)

        # init language kernel
        def sending_init():
            while not self.zmq_confirmed:
                logging.debug('init kernel '+self.name+' to publish on '
                              'port '+str(port_subscribe))
                self.zmq_publish.send_json({
                    '__databench_namespace': self.name,
                    'publish_on_port': port_subscribe,
                })
                time.sleep(0.1)
        gevent.Greenlet.spawn(sending_init)

    def __del__(self):
        self.kernel_process.terminate()
        self.kernel_process.kill()

    def instantiate_analysis_class(self):
        self.zmq_analysis_id += 1
        i = self.analysis_class(self.name,
                                self.zmq_analysis_id,
                                self.zmq_publish)
        self.zmq_analyses[self.zmq_analysis_id] = i
        return i