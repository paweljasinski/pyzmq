from _zmq import zmq_version_info
_version_info = zmq_version_info()
if _version_info < (3,2,2):
    raise ImportError("PyZMQ IronPython backend requires zeromq >= 3.2.2,"
        " but found %i.%i.%i" % _version_info
    )

__all__ = ['zmq_version_info']
