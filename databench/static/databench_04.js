(function e(t,n,r){function s(o,u){if(!n[o]){if(!t[o]){var a=typeof require=="function"&&require;if(!u&&a)return a(o,!0);if(i)return i(o,!0);var f=new Error("Cannot find module '"+o+"'");throw f.code="MODULE_NOT_FOUND",f}var l=n[o]={exports:{}};t[o][0].call(l.exports,function(e){var n=t[o][1][e];return s(n?n:e)},l,l.exports,e,t,n,r)}return n[o].exports}var i=typeof require=="function"&&require;for(var o=0;o<r.length;o++)s(r[o]);return s})({1:[function(require,module,exports){
'use strict';

Object.defineProperty(exports, "__esModule", {
    value: true
});

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

if (typeof WebSocket === 'undefined') {
    var WebSocket = require('websocket').w3cwebsocket;
}

var Connection = exports.Connection = function () {
    function Connection(error_cb) {
        var analysis_id = arguments.length <= 1 || arguments[1] === undefined ? null : arguments[1];
        var ws_url = arguments.length <= 2 || arguments[2] === undefined ? null : arguments[2];

        _classCallCheck(this, Connection);

        this.error_cb = error_cb;
        this.analysis_id = analysis_id;
        this.ws_url = ws_url ? ws_url : this.guess_ws_url();

        this.on_callbacks = {};
        this.onAction_callbacks = {};

        this.ws_reconnect_attempt = 0;
        this.ws_reconnect_delay = 100.0;

        this.socket = null;
        this.socket_check_open = null;
        this.ws_connect();
    }

    _createClass(Connection, [{
        key: 'guess_ws_url',
        value: function guess_ws_url() {
            var ws_protocol = 'ws';
            if (location.origin.startsWith('https://')) ws_protocol = 'wss';

            var path = location.pathname.substring(0, location.pathname.lastIndexOf('/'));
            return ws_protocol + '://' + document.domain + ':' + location.port + path + '/ws';
        }
    }, {
        key: 'ws_connect',
        value: function ws_connect() {
            this.socket = new WebSocket(this.ws_url);

            this.socket_check_open = setInterval(this.ws_check_open.bind(this), 2000);
            this.socket.onopen = this.ws_onopen.bind(this);
            this.socket.onclose = this.ws_onclose.bind(this);
            this.socket.onmessage = this.ws_onmessage.bind(this);
        }
    }, {
        key: 'ws_check_open',
        value: function ws_check_open() {
            if (this.socket.readyState == WebSocket.CONNECTING) {
                return;
            }
            if (this.socket.readyState != WebSocket.OPEN) {
                this.error_cb('Connection could not be opened. ' + 'Please <a href="javascript:location.reload(true);" ' + 'class="alert-link">reload</a> this page to try again.');
            }
            window.clearInterval(this.socket_check_open);
        }
    }, {
        key: 'ws_onopen',
        value: function ws_onopen() {
            this.ws_reconnect_attempt = 0;
            this.ws_reconnect_delay = 100.0;
            this.error_cb(); // clear errors
            this.socket.send(JSON.stringify({ '__connect': this.analysis_id }));
        }
    }, {
        key: 'ws_onclose',
        value: function ws_onclose() {
            window.clearInterval(this.socket_check_open);

            this.ws_reconnect_attempt += 1;
            this.ws_reconnect_delay *= 2;

            if (this.ws_reconnect_attempt > 3) {
                this.error_cb('Connection closed. ' + 'Please <a href="javascript:location.reload(true);" ' + 'class="alert-link">reload</a> this page to reconnect.');
                return;
            }

            var actual_delay = 0.7 * this.ws_reconnect_delay + 0.3 * Math.random() * this.ws_reconnect_delay;
            console.log('WebSocket reconnect attempt ' + this.ws_reconnect_attempt + ' in ' + actual_delay + 'ms.');
            setTimeout(this.ws_connect.bind(this), actual_delay);
        }
    }, {
        key: 'ws_onmessage',
        value: function ws_onmessage(event) {
            var message = JSON.parse(event.data);

            // connect response
            if (message.signal == '__connect') {
                this.analysis_id = message.load.analysis_id;
                console.log('Set analysis_id to ' + this.analysis_id);
            }

            // actions
            if (message.signal == '__action') {
                var id = message.load.id;
                this.onAction_callbacks[id].map(function (cb) {
                    return cb(message.load.status);
                });
            }

            // normal message
            if (message.signal in this.on_callbacks) {
                this.on_callbacks[message.signal].map(function (cb) {
                    return cb(message.load);
                });
            }
        }
    }, {
        key: 'on',
        value: function on(signalName, callback) {
            if (!(signalName in this.on_callbacks)) this.on_callbacks[signalName] = [];
            this.on_callbacks[signalName].push(callback);
        }
    }, {
        key: 'emit',
        value: function (_emit) {
            function emit(_x, _x2) {
                return _emit.apply(this, arguments);
            }

            emit.toString = function () {
                return _emit.toString();
            };

            return emit;
        }(function (signalName, message) {
            if (this.socket.readyState != 1) {
                setTimeout(function () {
                    return emit(signalName, message);
                }, 5);
                return;
            }
            this.socket.send(JSON.stringify({ 'signal': signalName, 'load': message }));
        })
    }, {
        key: 'onAction',
        value: function onAction(actionID, callback) {
            if (!(actionID in this.onAction_callbacks)) this.onAction_callbacks[actionID] = [];
            this.onAction_callbacks[actionID].push(callback);
        }
    }]);

    return Connection;
}();

},{"websocket":4}],2:[function(require,module,exports){
'use strict';

Object.defineProperty(exports, "__esModule", {
	value: true
});
exports.Connection = exports.ui = undefined;

var _ui = require('./ui');

var ui = _interopRequireWildcard(_ui);

var _connection = require('./connection');

function _interopRequireWildcard(obj) { if (obj && obj.__esModule) { return obj; } else { var newObj = {}; if (obj != null) { for (var key in obj) { if (Object.prototype.hasOwnProperty.call(obj, key)) newObj[key] = obj[key]; } } newObj.default = obj; return newObj; } }

// create a public interface
if (typeof window !== 'undefined') {
	window.Databench04 = { ui: ui, Connection: _connection.Connection };
}
exports.ui = ui;
exports.Connection = _connection.Connection;

},{"./connection":1,"./ui":3}],3:[function(require,module,exports){
'use strict';

Object.defineProperty(exports, "__esModule", {
    value: true
});

var _slicedToArray = function () { function sliceIterator(arr, i) { var _arr = []; var _n = true; var _d = false; var _e = undefined; try { for (var _i = arr[Symbol.iterator](), _s; !(_n = (_s = _i.next()).done); _n = true) { _arr.push(_s.value); if (i && _arr.length === i) break; } } catch (err) { _d = true; _e = err; } finally { try { if (!_n && _i["return"]) _i["return"](); } finally { if (_d) throw _e; } } return _arr; } return function (arr, i) { if (Array.isArray(arr)) { return arr; } else if (Symbol.iterator in Object(arr)) { return sliceIterator(arr, i); } else { throw new TypeError("Invalid attempt to destructure non-iterable instance"); } }; }();

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

function _toConsumableArray(arr) { if (Array.isArray(arr)) { for (var i = 0, arr2 = Array(arr.length); i < arr.length; i++) { arr2[i] = arr[i]; } return arr2; } else { return Array.from(arr); } }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

var Log = exports.Log = function () {
    function Log(node) {
        var _this = this;

        var limit = arguments.length <= 1 || arguments[1] === undefined ? 20 : arguments[1];
        var consoleFnName = arguments.length <= 2 || arguments[2] === undefined ? 'log' : arguments[2];

        _classCallCheck(this, Log);

        this.render = function () {
            while (_this._messages.length > _this.limit) {
                _this._messages.shift();
            }_this.node.innerText = _this._messages.map(function (m) {
                return m.join('');
            }).join('\n');
        };

        this.add = function (message) {
            var source = arguments.length <= 1 || arguments[1] === undefined ? 'unknown' : arguments[1];

            if (typeof message != "string") {
                message = JSON.stringify(message);
            }

            var padded_source = ' '.repeat(Math.max(0, 8 - source.length)) + source;
            _this._messages.push([padded_source + ': ' + message]);
            _this.render();
        };

        this.node = node;
        this.limit = limit;
        this.consoleFnName = consoleFnName;
        this._messages = [];

        // capture events from frontend
        var _consoleFnOriginal = console[consoleFnName];
        console[consoleFnName] = function (message) {
            _this.add(message, 'frontend');
            _consoleFnOriginal.apply(console, [message]);
        };
    }

    _createClass(Log, null, [{
        key: 'wire',
        value: function wire() {
            var id = arguments.length <= 0 || arguments[0] === undefined ? 'log' : arguments[0];
            var source = arguments.length <= 1 || arguments[1] === undefined ? 'backend' : arguments[1];
            var limit = arguments.length <= 2 || arguments[2] === undefined ? 20 : arguments[2];
            var consoleFnName = arguments.length <= 3 || arguments[3] === undefined ? 'log' : arguments[3];

            var node = document.getElementById(id);
            if (node == null) return;

            console.log('Wiring element id=' + id + ' to ' + source + '.');
            var l = new Log(node, limit, consoleFnName);
            return function (message) {
                return l.add(message, source);
            };
        }
    }]);

    return Log;
}();

;

var StatusLog = exports.StatusLog = function () {
    function StatusLog(node) {
        var _this2 = this;

        var formatter = arguments.length <= 1 || arguments[1] === undefined ? StatusLog.default_alert : arguments[1];

        _classCallCheck(this, StatusLog);

        this.render = function () {
            var formatted = [].concat(_toConsumableArray(_this2._messages)).map(function (_ref) {
                var _ref2 = _slicedToArray(_ref, 2);

                var m = _ref2[0];
                var c = _ref2[1];
                return _this2.formatter(m, c);
            });
            _this2.node.innerHTML = formatted.join('\n');
        };

        this.add = function (msg) {
            if (msg == null) {
                _this2._messages.clear();
                return;
            }
            if (typeof msg != "string") {
                msg = JSON.stringify(msg);
            }

            if (_this2._messages.has(msg)) {
                _this2._messages.set(msg, _this2._messages.get(msg) + 1);
            } else {
                _this2._messages.set(msg, 1);
            }
            _this2.render();
        };

        this.node = node;
        this.formatter = formatter;
        this._messages = new Map();
    }

    _createClass(StatusLog, null, [{
        key: 'default_alert',
        value: function default_alert(msg, c) {
            var c_format = c <= 1 ? '' : '<b>(' + c + ')</b> ';
            return '<div class="alert alert-danger">' + c_format + msg + '</div>';
        }
    }, {
        key: 'wire',
        value: function wire() {
            var id = arguments.length <= 0 || arguments[0] === undefined ? 'ws-alerts' : arguments[0];
            var formatter = arguments.length <= 1 || arguments[1] === undefined ? StatusLog.default_alert : arguments[1];

            var node = document.getElementById(id);
            if (node == null) return;

            console.log('Wiring element id=' + id + '.');
            var l = new StatusLog(node, formatter);
            return l.add;
        }
    }]);

    return StatusLog;
}();

;

},{}],4:[function(require,module,exports){
var _global = (function() { return this; })();
var nativeWebSocket = _global.WebSocket || _global.MozWebSocket;
var websocket_version = require('./version');


/**
 * Expose a W3C WebSocket class with just one or two arguments.
 */
function W3CWebSocket(uri, protocols) {
	var native_instance;

	if (protocols) {
		native_instance = new nativeWebSocket(uri, protocols);
	}
	else {
		native_instance = new nativeWebSocket(uri);
	}

	/**
	 * 'native_instance' is an instance of nativeWebSocket (the browser's WebSocket
	 * class). Since it is an Object it will be returned as it is when creating an
	 * instance of W3CWebSocket via 'new W3CWebSocket()'.
	 *
	 * ECMAScript 5: http://bclary.com/2004/11/07/#a-13.2.2
	 */
	return native_instance;
}


/**
 * Module exports.
 */
module.exports = {
    'w3cwebsocket' : nativeWebSocket ? W3CWebSocket : null,
    'version'      : websocket_version
};

},{"./version":5}],5:[function(require,module,exports){
module.exports = require('../package.json').version;

},{"../package.json":6}],6:[function(require,module,exports){
module.exports={
  "_args": [
    [
      "websocket",
      "/Users/zween/tech/databench"
    ]
  ],
  "_from": "websocket@latest",
  "_id": "websocket@1.0.22",
  "_inCache": true,
  "_installable": true,
  "_location": "/websocket",
  "_nodeVersion": "3.3.1",
  "_npmUser": {
    "email": "brian@worlize.com",
    "name": "theturtle32"
  },
  "_npmVersion": "2.14.3",
  "_phantomChildren": {},
  "_requested": {
    "name": "websocket",
    "raw": "websocket",
    "rawSpec": "",
    "scope": null,
    "spec": "latest",
    "type": "tag"
  },
  "_requiredBy": [
    "/"
  ],
  "_resolved": "https://registry.npmjs.org/websocket/-/websocket-1.0.22.tgz",
  "_shasum": "8c33e3449f879aaf518297c9744cebf812b9e3d8",
  "_shrinkwrap": null,
  "_spec": "websocket",
  "_where": "/Users/zween/tech/databench",
  "author": {
    "email": "brian@worlize.com",
    "name": "Brian McKelvey",
    "url": "https://www.worlize.com/"
  },
  "browser": "lib/browser.js",
  "bugs": {
    "url": "https://github.com/theturtle32/WebSocket-Node/issues"
  },
  "config": {
    "verbose": false
  },
  "contributors": [
    {
      "name": "Iñaki Baz Castillo",
      "email": "ibc@aliax.net",
      "url": "http://dev.sipdoc.net"
    }
  ],
  "dependencies": {
    "debug": "~2.2.0",
    "nan": "~2.0.5",
    "typedarray-to-buffer": "~3.0.3",
    "yaeti": "~0.0.4"
  },
  "description": "Websocket Client & Server Library implementing the WebSocket protocol as specified in RFC 6455.",
  "devDependencies": {
    "buffer-equal": "^0.0.1",
    "faucet": "^0.0.1",
    "gulp": "git+https://github.com/gulpjs/gulp.git#4.0",
    "gulp-jshint": "^1.11.2",
    "jshint-stylish": "^1.0.2",
    "tape": "^4.0.1"
  },
  "directories": {
    "lib": "./lib"
  },
  "dist": {
    "shasum": "8c33e3449f879aaf518297c9744cebf812b9e3d8",
    "tarball": "http://registry.npmjs.org/websocket/-/websocket-1.0.22.tgz"
  },
  "engines": {
    "node": ">=0.8.0"
  },
  "gitHead": "19108bbfd7d94a5cd02dbff3495eafee9e901ca4",
  "homepage": "https://github.com/theturtle32/WebSocket-Node",
  "keywords": [
    "RFC-6455",
    "client",
    "comet",
    "networking",
    "push",
    "realtime",
    "server",
    "socket",
    "websocket",
    "websockets"
  ],
  "license": "Apache-2.0",
  "main": "index",
  "maintainers": [
    {
      "name": "theturtle32",
      "email": "brian@worlize.com"
    }
  ],
  "name": "websocket",
  "optionalDependencies": {},
  "readme": "ERROR: No README data found!",
  "repository": {
    "type": "git",
    "url": "git+https://github.com/theturtle32/WebSocket-Node.git"
  },
  "scripts": {
    "gulp": "gulp",
    "install": "(node-gyp rebuild 2> builderror.log) || (exit 0)",
    "test": "faucet test/unit"
  },
  "version": "1.0.22"
}

},{}]},{},[2])


//# sourceMappingURL=databench_04.js.map
