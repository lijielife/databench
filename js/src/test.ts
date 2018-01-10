/**
 * Test documentation.
 */

import { expect } from 'chai';
import * as Databench from '.';


describe('Echo Tests', () => {
  let c = Databench.connect('ws://localhost:5000/parameters/ws');
  beforeEach(() => { c.disconnect(); c = Databench.connect('ws://localhost:5000/parameters/ws'); });
  after(() => c.disconnect());

  it('creates a WebSocket connection', () => {
    expect(typeof c).to.equal('object');
  });

  it('sends an action without message', (done) => {
    c.on('test_action_ack', () => done());
    c.emit('test_action');
  });

  it('echos an object', done => {
    c.on('test_fn', data => {
      expect(data).to.deep.equal([1, 2]);
      done();
    });
    c.emit('test_fn', [1, 2]);
  });

  it('echos an empty string', done => {
    c.on('test_fn', dataEmpty => {
      expect(dataEmpty).to.deep.equal(['', 100]);
      done();
    });
    c.emit('test_fn', '');
  });

  it('echos a null parameter', done => {
    c.on('test_fn', dataNull => {
      expect(dataNull).to.deep.equal([null, 100]);
      done();
    });
    c.emit('test_fn', null);
  });
});

describe('Command Line and Request Arguments', () => {
  describe('empty request args', () => {
    const c = new Databench.Connection('ws://localhost:5000/requestargs/ws');
    after(() => c.disconnect());

    it('valid empty request args', done => {
      c.on('echo_request_args', request_args => {
        expect(request_args).to.deep.equal({});
        done();
      });
      c.connect();
    });
  });

  describe('simple request args', () => {
    const c = new Databench.Connection('ws://localhost:5000/requestargs/ws', '?data=requestargtest');
    after(() => c.disconnect());

    it('can access request args', done => {
      c.on('echo_request_args', request_args => {
        expect(request_args).to.deep.equal({ data: ['requestargtest'] });
        done();
      });
      c.connect();
    });
  });

  describe('simple cli args', () => {
    const c = new Databench.Connection('ws://localhost:5000/cliargs/ws');
    after(() => c.disconnect());

    it('can access cli args', done => {
      c.on({ data: 'cli_args' }, args => {
        expect(args).to.deep.equal(['--some-test-flag']);
        done();
      });
      c.connect();
    });
  });
});

describe('Cycle Connection', () => {
  const c = Databench.connect('ws://localhost:5000/requestargs/ws');
  after(() => c.disconnect());

  it('reconnects after disconnect', done => {
    c.disconnect();
    c.on('echo_request_args', () => done());
    c.connect();
  });
});

describe('Analysis Test', () => {
  let c: Databench.Connection = new Databench.Connection();
  beforeEach(() => { c.disconnect(); c = new Databench.Connection(); });
  after(() => c.disconnect());

  it('can open a connection without connecting', done => {
    c.preEmit('test', message => done());
    c.emit('test');
  });

  it('can emulate an empty backend response', done => {
    c.on('received', message => done());
    c.preEmit('test', message => c.trigger('received'));
    c.emit('test');
  });

  it('can emulate a string backend response', () => {
    c.on('received', message => {
      expect(message).to.equal('test message');
    });
    c.preEmit('test', message => c.trigger('received', 'test message'));
    c.emit('test');
  });
});
