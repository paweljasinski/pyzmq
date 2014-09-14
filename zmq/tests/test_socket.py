# -*- coding: utf8 -*-
# Copyright (C) PyZMQ Developers
# Distributed under the terms of the Modified BSD License.

import sys
import time
import errno
import warnings

import zmq
from zmq.tests import (
    BaseZMQTestCase, SkipTest, have_gevent, GreenTest, skip_pypy, skip_if, skip_ironpython, IRONPYTHON2
)
from zmq.utils.strtypes import bytes, unicode

try:
    from queue import Queue
except:
    from Queue import Queue


class TestSocket(BaseZMQTestCase):

    def test_create(self):
        ctx = self.Context()
        s = ctx.socket(zmq.PUB)
        # Superluminal protocol not yet implemented
        self.assertRaisesErrno(zmq.EPROTONOSUPPORT, s.bind, 'ftl://a')
        self.assertRaisesErrno(zmq.EPROTONOSUPPORT, s.connect, 'ftl://a')
        self.assertRaisesErrno(zmq.EINVAL, s.bind, 'tcp://')
        s.close()
        del ctx
    
    def test_dir(self):
        ctx = self.Context()
        s = ctx.socket(zmq.PUB)
        self.assertTrue('send' in dir(s))
        self.assertTrue('IDENTITY' in dir(s))
        self.assertTrue('AFFINITY' in dir(s))
        self.assertTrue('FD' in dir(s))
        s.close()
        ctx.term()

    def test_bind_unicode(self):
        s = self.socket(zmq.PUB)
        p = s.bind_to_random_port(unicode("tcp://*"))

    def test_connect_unicode(self):
        s = self.socket(zmq.PUB)
        s.connect(unicode("tcp://127.0.0.1:5555"))

    def test_bind_to_random_port(self):
        # Check that bind_to_random_port do not hide usefull exception
        ctx = self.Context()
        c = ctx.socket(zmq.PUB)
        # Invalid format
        try:
            c.bind_to_random_port('tcp:*')
        except zmq.ZMQError as e:
            self.assertEqual(e.errno, zmq.EINVAL)
        # Invalid protocol
        try:
            c.bind_to_random_port('rand://*')
        except zmq.ZMQError as e:
            self.assertEqual(e.errno, zmq.EPROTONOSUPPORT)

    def test_identity(self):
        s = self.context.socket(zmq.PULL)
        self.sockets.append(s)
        ident = b'identity\0\0'
        s.identity = ident
        self.assertEqual(s.get(zmq.IDENTITY), ident)

    def test_unicode_sockopts(self):
        """test setting/getting sockopts with unicode strings"""
        topic = "tést"
        if str is not unicode:
            topic = topic.decode('utf8')
        p,s = self.create_bound_pair(zmq.PUB, zmq.SUB)
        self.assertEqual(s.send_unicode, s.send_unicode)
        self.assertEqual(p.recv_unicode, p.recv_unicode)
        if not IRONPYTHON2:
            # ironpython version does not throw TypeError on unicode argument
            self.assertRaises(TypeError, s.setsockopt, zmq.SUBSCRIBE, topic)
            self.assertRaises(TypeError, s.setsockopt, zmq.IDENTITY, topic)
        s.setsockopt_unicode(zmq.IDENTITY, topic, 'utf16')
        if not IRONPYTHON2:
            # ironpython version does not throw TypeError on unicode argument
            self.assertRaises(TypeError, s.setsockopt, zmq.AFFINITY, topic)
        s.setsockopt_unicode(zmq.SUBSCRIBE, topic)
        self.assertRaises(TypeError, s.getsockopt_unicode, zmq.AFFINITY)
        self.assertRaisesErrno(zmq.EINVAL, s.getsockopt_unicode, zmq.SUBSCRIBE)
        identb = s.getsockopt(zmq.IDENTITY)
        identu = identb.decode('utf16')
        identu2 = s.getsockopt_unicode(zmq.IDENTITY, 'utf16')
        self.assertEqual(identu, identu2)
        time.sleep(0.5) # wait for connection/subscription
        p.send_unicode(topic,zmq.SNDMORE)
        p.send_unicode(topic*2, encoding='latin-1')
        self.assertEqual(topic, s.recv_unicode())
        self.assertEqual(topic*2, s.recv_unicode(encoding='latin-1'))
    
    def test_int_sockopts(self):
        "test integer sockopts"
        v = zmq.zmq_version_info()
        if v < (3,0):
            default_hwm = 0
        else:
            default_hwm = 1000
        p,s = self.create_bound_pair(zmq.PUB, zmq.SUB)
        p.setsockopt(zmq.LINGER, 0)
        self.assertEqual(p.getsockopt(zmq.LINGER), 0)
        p.setsockopt(zmq.LINGER, -1)
        self.assertEqual(p.getsockopt(zmq.LINGER), -1)
        self.assertEqual(p.hwm, default_hwm)
        p.hwm = 11
        self.assertEqual(p.hwm, 11)
        # p.setsockopt(zmq.EVENTS, zmq.POLLIN)
        self.assertEqual(p.getsockopt(zmq.EVENTS), zmq.POLLOUT)
        self.assertRaisesErrno(zmq.EINVAL, p.setsockopt,zmq.EVENTS, 2**7-1)
        self.assertEqual(p.getsockopt(zmq.TYPE), p.socket_type)
        self.assertEqual(p.getsockopt(zmq.TYPE), zmq.PUB)
        self.assertEqual(s.getsockopt(zmq.TYPE), s.socket_type)
        self.assertEqual(s.getsockopt(zmq.TYPE), zmq.SUB)
        
        # check for overflow / wrong type:
        errors = []
        backref = {}
        constants = zmq.constants
        for name in constants.__all__:
            value = getattr(constants, name)
            if isinstance(value, int):
                backref[value] = name
        for opt in zmq.constants.int_sockopts.union(zmq.constants.int64_sockopts):
            sopt = backref[opt]
            if sopt.startswith((
                'ROUTER', 'XPUB', 'TCP', 'FAIL',
                'REQ_', 'CURVE_', 'PROBE_ROUTER',
                'IPC_FILTER',
                )):
                # some sockopts are write-only
                continue
            try:
                n = p.getsockopt(opt)
            except zmq.ZMQError as e:
                errors.append("getsockopt(zmq.%s) raised '%s'."%(sopt, e))
            else:
                if n > 2**31:
                    errors.append("getsockopt(zmq.%s) returned a ridiculous value."
                                    " It is probably the wrong type."%sopt)
        if errors:
            self.fail('\n'.join([''] + errors))
    
    def test_bad_sockopts(self):
        """Test that appropriate errors are raised on bad socket options"""
        s = self.context.socket(zmq.PUB)
        self.sockets.append(s)
        s.setsockopt(zmq.LINGER, 0)
        # unrecognized int sockopts pass through to libzmq, and should raise EINVAL
        self.assertRaisesErrno(zmq.EINVAL, s.setsockopt, 9999, 5)
        self.assertRaisesErrno(zmq.EINVAL, s.getsockopt, 9999)
        # but only int sockopts are allowed through this way, otherwise raise a TypeError
        self.assertRaises(TypeError, s.setsockopt, 9999, b"5")
        # some sockopts are valid in general, but not on every socket:
        self.assertRaisesErrno(zmq.EINVAL, s.setsockopt, zmq.SUBSCRIBE, b'hi')
    
    def test_sockopt_roundtrip(self):
        "test set/getsockopt roundtrip."
        p = self.context.socket(zmq.PUB)
        self.sockets.append(p)
        self.assertEqual(p.getsockopt(zmq.LINGER), -1)
        p.setsockopt(zmq.LINGER, 11)
        self.assertEqual(p.getsockopt(zmq.LINGER), 11)
    
    def test_poll(self):
        """test Socket.poll()"""
        req, rep = self.create_bound_pair(zmq.REQ, zmq.REP)
        # default flag is POLLIN, nobody has anything to recv:
        self.assertEqual(req.poll(0), 0)
        self.assertEqual(rep.poll(0), 0)
        self.assertEqual(req.poll(0, zmq.POLLOUT), zmq.POLLOUT)
        self.assertEqual(rep.poll(0, zmq.POLLOUT), 0)
        self.assertEqual(req.poll(0, zmq.POLLOUT|zmq.POLLIN), zmq.POLLOUT)
        self.assertEqual(rep.poll(0, zmq.POLLOUT), 0)
        req.send('hi')
        self.assertEqual(req.poll(0), 0)
        self.assertEqual(rep.poll(1), zmq.POLLIN)
        self.assertEqual(req.poll(0, zmq.POLLOUT), 0)
        self.assertEqual(rep.poll(0, zmq.POLLOUT), 0)
        self.assertEqual(req.poll(0, zmq.POLLOUT|zmq.POLLIN), 0)
        self.assertEqual(rep.poll(0, zmq.POLLOUT), zmq.POLLIN)
    
    def test_send_unicode(self):
        "test sending unicode objects"
        a,b = self.create_bound_pair(zmq.PAIR, zmq.PAIR)
        self.sockets.extend([a,b])
        u = "çπ§"
        if str is not unicode:
            u = u.decode('utf8')
        if not IRONPYTHON2:
            # Ironpython2 accepts unicode and interpret as bytes
            self.assertRaises(TypeError, a.send, u,copy=False)
            self.assertRaises(TypeError, a.send, u,copy=True)
        a.send_unicode(u)
        s = b.recv()
        self.assertEqual(s,u.encode('utf8'))
        self.assertEqual(s.decode('utf8'),u)
        a.send_unicode(u,encoding='utf16')
        s = b.recv_unicode(encoding='utf16')
        self.assertEqual(s,u)
    
    @skip_pypy
    @skip_ironpython
    def test_tracker(self):
        "test the MessageTracker object for tracking when zmq is done with a buffer"
        addr = 'tcp://127.0.0.1'
        a = self.context.socket(zmq.PUB)
        port = a.bind_to_random_port(addr)
        a.close()
        iface = "%s:%i"%(addr,port)
        a = self.context.socket(zmq.PAIR)
        # a.setsockopt(zmq.IDENTITY, b"a")
        b = self.context.socket(zmq.PAIR)
        self.sockets.extend([a,b])
        a.connect(iface)
        time.sleep(0.1)
        p1 = a.send(b'something', copy=False, track=True)
        self.assertTrue(isinstance(p1, zmq.MessageTracker))
        self.assertFalse(p1.done)
        p2 = a.send_multipart([b'something', b'else'], copy=False, track=True)
        self.assert_(isinstance(p2, zmq.MessageTracker))
        self.assertEqual(p2.done, False)
        self.assertEqual(p1.done, False)

        b.bind(iface)
        msg = b.recv_multipart()
        for i in range(10):
            if p1.done:
                break
            time.sleep(0.1)
        self.assertEqual(p1.done, True)
        self.assertEqual(msg, [b'something'])
        msg = b.recv_multipart()
        for i in range(10):
            if p2.done:
                break
            time.sleep(0.1)
        self.assertEqual(p2.done, True)
        self.assertEqual(msg, [b'something', b'else'])
        m = zmq.Frame(b"again", track=True)
        self.assertEqual(m.tracker.done, False)
        p1 = a.send(m, copy=False)
        p2 = a.send(m, copy=False)
        self.assertEqual(m.tracker.done, False)
        self.assertEqual(p1.done, False)
        self.assertEqual(p2.done, False)
        msg = b.recv_multipart()
        self.assertEqual(m.tracker.done, False)
        self.assertEqual(msg, [b'again'])
        msg = b.recv_multipart()
        self.assertEqual(m.tracker.done, False)
        self.assertEqual(msg, [b'again'])
        self.assertEqual(p1.done, False)
        self.assertEqual(p2.done, False)
        pm = m.tracker
        del m
        for i in range(10):
            if p1.done:
                break
            time.sleep(0.1)
        self.assertEqual(p1.done, True)
        self.assertEqual(p2.done, True)
        m = zmq.Frame(b'something', track=False)
        self.assertRaises(ValueError, a.send, m, copy=False, track=True)
        

    def test_close(self):
        ctx = self.Context()
        s = ctx.socket(zmq.PUB)
        s.close()
        self.assertRaisesErrno(zmq.ENOTSOCK, s.bind, b'')
        self.assertRaisesErrno(zmq.ENOTSOCK, s.connect, b'')
        self.assertRaisesErrno(zmq.ENOTSOCK, s.setsockopt, zmq.SUBSCRIBE, b'')
        self.assertRaisesErrno(zmq.ENOTSOCK, s.send, b'asdf')
        self.assertRaisesErrno(zmq.ENOTSOCK, s.recv)
        del ctx
    
    def test_attr(self):
        """set setting/getting sockopts as attributes"""
        s = self.context.socket(zmq.DEALER)
        self.sockets.append(s)
        linger = 10
        s.linger = linger
        self.assertEqual(linger, s.linger)
        self.assertEqual(linger, s.getsockopt(zmq.LINGER))
        self.assertEqual(s.fd, s.getsockopt(zmq.FD))
    
    def test_bad_attr(self):
        s = self.context.socket(zmq.DEALER)
        self.sockets.append(s)
        try:
            s.apple='foo'
        except AttributeError:
            pass
        else:
            self.fail("bad setattr should have raised AttributeError")
        try:
            s.apple
        except AttributeError:
            pass
        else:
            self.fail("bad getattr should have raised AttributeError")

    def test_subclass(self):
        """subclasses can assign attributes"""
        class S(zmq.Socket):
            a = None
            def __init__(self, *a, **kw):
                self.a=-1
                super(S, self).__init__(*a, **kw)
        
        s = S(self.context, zmq.REP)
        self.sockets.append(s)
        self.assertEqual(s.a, -1)
        s.a=1
        self.assertEqual(s.a, 1)
        a=s.a
        self.assertEqual(a, 1)
    
    def test_recv_multipart(self):
        a,b = self.create_bound_pair()
        msg = b'hi'
        for i in range(3):
            a.send(msg)
        time.sleep(0.1)
        for i in range(3):
            self.assertEqual(b.recv_multipart(), [msg])
    
    def test_close_after_destroy(self):
        """s.close() after ctx.destroy() should be fine"""
        ctx = self.Context()
        s = ctx.socket(zmq.REP)
        ctx.destroy()
        # reaper is not instantaneous
        time.sleep(1e-2)
        s.close()
        self.assertTrue(s.closed)
    
    def test_poll(self):
        a,b = self.create_bound_pair()
        tic = time.time()
        evt = a.poll(50)
        self.assertEqual(evt, 0)
        evt = a.poll(50, zmq.POLLOUT)
        self.assertEqual(evt, zmq.POLLOUT)
        msg = b'hi'
        a.send(msg)
        evt = b.poll(50)
        self.assertEqual(evt, zmq.POLLIN)
        msg2 = self.recv(b)
        evt = b.poll(50)
        self.assertEqual(evt, 0)
        self.assertEqual(msg2, msg)
    
    def test_ipc_path_max_length(self):
        """IPC_PATH_MAX_LEN is a sensible value"""
        if zmq.IPC_PATH_MAX_LEN == 0:
            raise SkipTest("IPC_PATH_MAX_LEN undefined")
        
        msg = "Surprising value for IPC_PATH_MAX_LEN: %s" % zmq.IPC_PATH_MAX_LEN
        self.assertTrue(zmq.IPC_PATH_MAX_LEN > 30, msg)
        self.assertTrue(zmq.IPC_PATH_MAX_LEN < 1025, msg)

    @skip_ironpython # ipc not supported
    def test_ipc_path_max_length_msg(self):
        if zmq.IPC_PATH_MAX_LEN == 0:
            raise SkipTest("IPC_PATH_MAX_LEN undefined")
        
        s = self.context.socket(zmq.PUB)
        self.sockets.append(s)
        try:
            s.bind('ipc://{0}'.format('a' * (zmq.IPC_PATH_MAX_LEN + 1)))
        except zmq.ZMQError as e:
            self.assertTrue(str(zmq.IPC_PATH_MAX_LEN) in e.strerror)
    
    def test_hwm(self):
        zmq3 = zmq.zmq_version_info()[0] >= 3
        for stype in (zmq.PUB, zmq.ROUTER, zmq.SUB, zmq.REQ, zmq.DEALER):
            s = self.context.socket(stype)
            s.hwm = 100
            self.assertEqual(s.hwm, 100)
            if zmq3:
                try:
                    self.assertEqual(s.sndhwm, 100)
                except AttributeError:
                    pass
                try:
                    self.assertEqual(s.rcvhwm, 100)
                except AttributeError:
                    pass
            s.close()
    
    @skip_ironpython
    def test_shadow(self):
        p = self.socket(zmq.PUSH)
        p.bind("tcp://127.0.0.1:5555")
        p2 = zmq.Socket.shadow(p.underlying)
        self.assertEqual(p.underlying, p2.underlying)
        s = self.socket(zmq.PULL)
        s2 = zmq.Socket.shadow(s.underlying)
        self.assertNotEqual(s.underlying, p.underlying)
        self.assertEqual(s.underlying, s2.underlying)
        s2.connect("tcp://127.0.0.1:5555")
        sent = b'hi'
        p2.send(sent)
        rcvd = self.recv(s2)
        self.assertEqual(rcvd, sent)
    
    def test_shadow_pyczmq(self):
        try:
            from pyczmq import zctx, zsocket, zstr
        except Exception:
            raise SkipTest("Requires pyczmq")
        
        ctx = zctx.new()
        ca = zsocket.new(ctx, zmq.PUSH)
        cb = zsocket.new(ctx, zmq.PULL)
        a = zmq.Socket.shadow(ca)
        b = zmq.Socket.shadow(cb)
        a.bind("inproc://a")
        b.connect("inproc://a")
        a.send(b'hi')
        rcvd = self.recv(b)
        self.assertEqual(rcvd, b'hi')

    def test_with(self):
        with self.Context() as ctx:
            with ctx.socket(zmq.PUB) as socket:
                self.assertNotEqual(ctx, None)
                self.assertNotEqual(socket, None)
                socket.bind_to_random_port('tcp://127.0.0.1')
            assert socket.closed
        assert ctx.closed


if have_gevent:
    import gevent
    
    class TestSocketGreen(GreenTest, TestSocket):
        test_bad_attr = GreenTest.skip_green
        test_close_after_destroy = GreenTest.skip_green
        
        def test_timeout(self):
            a,b = self.create_bound_pair()
            g = gevent.spawn_later(0.5, lambda: a.send(b'hi'))
            timeout = gevent.Timeout(0.1)
            timeout.start()
            self.assertRaises(gevent.Timeout, b.recv)
            g.kill()
        
        @skip_if(not hasattr(zmq, 'RCVTIMEO'))
        def test_warn_set_timeo(self):
            s = self.context.socket(zmq.REQ)
            with warnings.catch_warnings(record=True) as w:
                s.rcvtimeo = 5
            s.close()
            self.assertEqual(len(w), 1)
            self.assertEqual(w[0].category, UserWarning)
            

        @skip_if(not hasattr(zmq, 'SNDTIMEO'))
        def test_warn_get_timeo(self):
            s = self.context.socket(zmq.REQ)
            with warnings.catch_warnings(record=True) as w:
                s.sndtimeo
            s.close()
            self.assertEqual(len(w), 1)
            self.assertEqual(w[0].category, UserWarning)
