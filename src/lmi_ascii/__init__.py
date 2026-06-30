"""
LMI ASCII - Ethernet ASCII Protocol Client for LMI Technologies Sensors

A Python client library for communicating with LMI Technologies Gocator 
sensors running GoPxL software via the Ethernet ASCII protocol.
"""

from .client import ASCIIClient
from .client import count_fails
from .client import shutdown_socket

from .exceptions import CommandError
from .exceptions import ConnectionError
from .exceptions import ASCIIClientError

__version__ = '0.1.0'
__author__ = 'LMI ASCII Contributors'
__all__ = [
    'ASCIIClient',
    'count_fails',
    'shutdown_socket',
    'ASCIIClientError',
    'ConnectionError',
    'CommandError',
]
