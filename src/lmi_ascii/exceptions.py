"""Custom exceptions for LMI ASCII client."""


class ASCIIClientError(Exception):
    """Base exception for all LMI ASCII client errors."""
    pass


class ConnectionError(ASCIIClientError):
    """Raised when connection to the sensor fails or is not established."""
    pass


class CommandError(ASCIIClientError):
    """Raised when a command fails to execute on the sensor."""
    pass


class TimeoutError(ASCIIClientError):
    """Raised when an operation times out."""
    pass
