"""
Basic tests for LMI ASCII client.

Run with: pytest tests/
"""

import pytest
from lmi_ascii import count_fails
from lmi_ascii import ASCIIClient
from lmi_ascii import shutdown_socket
from lmi_ascii.exceptions import ConnectionError
from lmi_ascii.exceptions import ASCIIClientError


def test_client_initialization():
    """Test that client initializes with correct defaults."""
    client = ASCIIClient()
    
    assert client.host == '127.0.0.1'
    assert client.port == 8190
    assert client.timeout == 10.0
    assert client.delimiter == ','
    assert client.termination == '\r\n'
    assert not client.connected
    assert not client.busy
    assert client.status == 'disconnected'


def test_client_custom_parameters():
    """Test that client accepts custom parameters."""
    client = ASCIIClient(
        host='192.168.1.10',
        port=9999,
        timeout=20.0,
        delimiter=';',
        termination='\n'
    )
    
    assert client.host == '192.168.1.10'
    assert client.port == 9999
    assert client.timeout == 20.0
    assert client.delimiter == ';'
    assert client.termination == '\n'


def test_count_fails_empty_dict():
    """Test count_fails with empty dictionary."""
    assert count_fails({}) == 0


def test_count_fails_no_failures():
    """Test count_fails with no failures."""
    data = {
        'Tool1': {'Status': 'Passed'},
        'Tool2': {'Status': 'Passed'}
    }
    assert count_fails(data) == 0


def test_count_fails_with_failures():
    """Test count_fails with some failures."""
    data = {
        'Tool1': {'Status': 'Failed'},
        'Tool2': {'Status': 'Passed'},
        'Tool3': {'Status': 'Failed'}
    }
    assert count_fails(data) == 2


def test_count_fails_nested():
    """Test count_fails with nested dictionaries."""
    data = {
        'Group1': {
            'Tool1': {'Status': 'Failed'},
            'Tool2': {'Status': 'Passed'}
        },
        'Group2': {
            'Tool3': {'Status': 'Failed'}
        },
        'Status': 'Failed'
    }
    assert count_fails(data) == 3


def test_reset_flags():
    """Test that reset_flags resets all state."""
    client = ASCIIClient()
    client._busy = True
    client._cancel = True
    client._finished = True
    client._success = True
    client._response = 'test'
    client._status = 'success'
    
    client.reset_flags()
    
    assert not client._busy
    assert not client._cancel
    assert not client._finished
    assert not client._success
    assert client._response == ''
    assert client._status == 'idle'


def test_status_property_disconnected():
    """Test status property when disconnected."""
    client = ASCIIClient()
    assert client.status == 'disconnected'


def test_status_property_busy():
    """Test status property when busy."""
    client = ASCIIClient()
    client._connected = True
    client._socket = object()  # Mock socket
    client._busy = True
    assert client.status == 'busy'


def test_status_property_idle():
    """Test status property when idle."""
    client = ASCIIClient()
    client._connected = True
    client._socket = object()  # Mock socket
    client._status = 'idle'
    assert client.status == 'idle'


# Add more tests as needed for specific functionality
# These would typically require mocking the socket connection
