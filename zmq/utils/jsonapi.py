"""Priority based json library imports.

Always serializes to bytes instead of unicode for zeromq compatibility
on Python 2 and 3.

Use ``jsonapi.loads()`` and ``jsonapi.dumps()`` for guaranteed symmetry.

Priority: ``simplejson`` > ``jsonlib2`` > stdlib ``json``

``jsonapi.loads/dumps`` provide kwarg-compatibility with stdlib json.

``jsonapi.jsonmod`` will be the module of the actual underlying implementation.
"""

# Copyright (C) PyZMQ Developers
# Distributed under the terms of the Modified BSD License.

from zmq.utils.strtypes import bytes, unicode, IRONPYTHON2
import sys

jsonmod = None

priority = ['simplejson', 'jsonlib2', 'json']
for mod in priority:
    try:
        jsonmod = __import__(mod)
    except ImportError:
        pass
    else:
        break

if not IRONPYTHON2:
    def _squash_unicode(s):
        if isinstance(s, unicode):
            s = s.encode('utf8')
        return s
else:
    def _squash_unicode(s):
        # ironpython 2.x
        # just repackage as bytes
        return bytes(s, 'iso-8859-1')

def dumps(o, **kwargs):
    """Serialize object to JSON bytes (utf-8).
    
    See jsonapi.jsonmod.dumps for details on kwargs.
    """
    
    if 'separators' not in kwargs:
        kwargs['separators'] = (',', ':')
    
    return _squash_unicode(jsonmod.dumps(o, **kwargs))

def loads(s, **kwargs):
    """Load object from JSON bytes (utf-8).
    
    See jsonapi.jsonmod.loads for details on kwargs.
    """
    
    if str is unicode and isinstance(s, bytes):
        s = s.decode('utf8')
    
    return jsonmod.loads(s, **kwargs)

__all__ = ['jsonmod', 'dumps', 'loads']

