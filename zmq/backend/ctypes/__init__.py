"""ctypes based IronPython backend"""

#-----------------------------------------------------------------------------
#  Copyright (C) 2013-2014 Felipe Cruz, Pawel Jasinski
#
#  This file is part of pyzmq
#
#  Distributed under the terms of the New BSD License.  The full license is in
#  the file COPYING.BSD, distributed as part of this software.
#-----------------------------------------------------------------------------

#
# Note:
#
# Ironpython ctypes implementation is not 100% cpython equivalent.
# There are bugs or things which are not implemented.
#
# In particular this implementation contains workarounds for
# the following issues.
#
# 1. memmove has problem with size=0
#    https://ironpython.codeplex.com/workitem/34892
# 2. byref does not work well with parameter checking
#    https://ironpython.codeplex.com/workitem/32048
#    https://ironpython.codeplex.com/workitem/32657
#

from zmq.backend.ctypes import (constants, error, message, context, socket,
                                _poll, devices, utils)

__all__ = []
for submod in (constants, error, message, context, socket,
               _poll, devices, utils):
    __all__.extend(submod.__all__)

from .constants import *
from .error import *
from .message import *
from .context import *
from .socket import *
from .devices import *
from ._poll import *
from ._version import zmq_version_info
from .utils import *
