"""
Ethernet ASCII Protocol Client for LMI Technologies Sensors.

This module provides functionality to communicate with LMI Technologies 
Gocator sensors running GoPxL software via the Ethernet ASCII protocol 
for job loading and measurement operations.
"""
import time
import json
import socket
import logging
import functools

from datetime import datetime

from typing import Any
from typing import Self
from typing import Dict
from typing import Tuple
from typing import Callable


# Dataset field names for emphasized columns
# These are used as dictionary keys in the dataset output
STATUS_FIELD = 'Status'
FAILED_COUNT_FIELD = 'FailedCount'


__all__ = [
    'shutdown_socket',
    'ASCIIClient',
    'count_fails',
]


# Configure module logger
logger = logging.getLogger(__name__)


def _managed_operation(func: Callable) -> Callable:
    """Decorator for ASCIIClient methods that manage the busy/finished flags.

    Wraps a method with the standard flag lifecycle:
    - Returns immediately (without resetting state) if already busy.
    - Calls ``reset_flags()`` and sets ``_busy = True`` before the call.
    - Always sets ``_busy = False`` and ``_finished = True`` in a 
      ``finally`` block, regardless of success or exception.

    Intended for long-running, exclusive operations such as 
    :meth:`~ASCIIClient.load_job` and 
    :meth:`~ASCIIClient.capture_dataset`.
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if self._busy:
            logger.warning(
                f'{self.__class__.__name__} is busy; ignoring {func.__name__} request')
            return None
        self.reset_flags()
        self._busy = True
        try:
            return func(self, *args, **kwargs)
        finally:
            self._busy = False
            self._finished = True
            self._status = 'success' if self._success else 'error'
    return wrapper


def shutdown_socket(connection: socket.socket) -> None:
    """Utility function to shutdown and close a socket connection.
    
    This function attempts to gracefully shutdown the socket connection 
    and close it, ensuring that resources are released properly.
    
    Parameters
    ----------
    connection : socket.socket
        The socket connection to be shutdown and closed.
    """
    try:
        connection.shutdown(socket.SHUT_RDWR)
    except Exception as e:
        logger.warning(f'Error during socket shutdown: {e}')
    finally:
        connection.close()


def count_fails(data: Dict) -> int:
    """Count the number of failed measurements in the dataset.
    
    This function recursively traverses the dataset dictionary to 
    count the number of failed measurements. It looks for keys that 
    end with the status field name and checks if their value is 
    'Failed'. It returns the total count of failed measurements.
    
    Parameters
    ----------
    data : Dict
        The dataset dictionary to be traversed for counting failed 
        measurements.
    
    Returns
    -------
    int
        The total count of failed measurements in the dataset.
    """
    count = 0
    for key, value in data.items():
        if key.endswith(STATUS_FIELD):
            if value == 'Failed':
                count += 1
        if isinstance(value, dict):
            count += count_fails(value)
    return count


class ASCIIClient:
    """Client for communicating with LMI Technologies sensors via Ethernet ASCII.
    
    This class provides methods to connect to an LMI sensor (running GoPxL), send
    commands, and retrieve responses. It supports loading jobs, starting
    and stopping measurements, and retrieving results. The client uses a
    socket connection to communicate with the sensor and includes error
    handling and logging for robust operation.
        
    Parameters
    ----------
    timestamp_id : int, optional
        External ID for timestamps, must be enabled for each job to 
        recognize when a new measurement is available. This is necessary 
        for the :method:`capture_dataset` method to function correctly. 
        Default is 0.
    host : str, optional
        IP address of the sensor or emulator. Default is '127.0.0.1'
    port : int, optional
        Port for Ethernet ASCII communication. Default is 8190.
    delimiter : str, optional
        Delimiter for command parameters. Default is ','.
    termination : str, optional
        Line termination characters. Default is '\r\n'.
    timeout : float, optional
        Socket timeout in seconds. Default is 10.0.
    logger : logging.Logger, optional
        Custom logger instance. If not provided, uses the module logger.
    **kwargs
        Additional keyword arguments are ignored but can be used for 
        future extensions or to pass through parameters from
        configuration.

    Examples
    --------
    >>> from lmi_ascii import ASCIIClient
    >>> with ASCIIClient(host='192.168.1.10') as client:
    ...     client.load_job('MyJob')
    ...     client.start_measurement()
    ...     data = client.capture_dataset()

    Source
    ------
    - LMI GoPxL Ethernet ASCII Communication Protocol
      https://am.lmi3d.com/manuals/gopxl/gopxl-1.2/LMILaserLineProfiler/Default.htm#Protocols/ASCIIProtocol/EthernetCommunication/PollingCommands.htm

    """

    STAMP_DIVISOR = 1_024
    """Divisor for converting sensor timestamp units to seconds. 
    Gocator timestamps are provided in units of 1/1024 seconds."""

    _METRIC_VALUES: Tuple[str, ...] = (
        'value', 'lastDecision', 'passCount', 'failCount', 'invalidCount')
    """Keys in the sensor measurement outputs that are relevant for 
    display and evaluation. These fields are extracted from each tool's 
    measurement outputs and included in the dataset."""

    def __init__(
            self,
            timestamp_id: int = 0,
            host: str = '127.0.0.1',
            port: int = 8190, 
            delimiter: str = ',',
            termination: str = '\r\n',
            timeout: float = 10.0,
            logger: logging.Logger | None = None,
            **kwargs
            ) -> None:

        self.timestamp_id = timestamp_id
        self.host = host
        self.port = port
        self.delimiter = delimiter
        self.termination = termination
        self.timeout = timeout
        self.progress = 0.0
        self._socket = None
        self._connected = False
        self._busy = False
        self._execution_data = {}
        self._timetick = 0.0
        self._initial_scan_count = 0
        self._status = 'idle'
        self._cancel = False
        self._finished = False
        self._response = ''
        self._success = False
        self._logger = logger or globals()['logger']

    @property
    def connected(self) -> bool:
        """Indicates whether the client is currently connected to the sensor (read-only)."""
        return self._connected and self._socket is not None

    @property
    def busy(self) -> bool:
        """Indicates whether the client is currently processing a request (read-only).
        
        While ``True``, no further requests (e.g. :meth:`capture_dataset`) should be started."""
        return self._busy

    @property
    def cancel(self) -> bool:
        """Indicates whether the current operation should be cancelled."""
        return self._cancel
    
    @cancel.setter
    def cancel(self, value: bool) -> None:
        """Set the cancel flag to request cancellation of the current operation."""
        self._cancel = value

    @property
    def finished(self) -> bool:
        """Indicates whether the current operation has finished (read-only).
        
        This is set to ``True`` when the operation completes, regardless
        of success or cancellation."""
        return self._finished

    @property
    def response(self) -> str:
        """Get the most recent response from the sensor (read-only)."""
        return self._response

    @property
    def success(self) -> bool:
        """Get the success status of the most recent command (read-only)."""
        return self._success

    @property
    def timetick(self) -> float:
        """Get the timetick in seconds of the last frame of last measurement.
        
        A timetick from a sensor is a 64-bit positive integer that is guaranteed 
        to increase monotonically starting from zero. It is guaranteed to be unique 
        for every scan from a given sensor group. The timetick is used to track the 
        timing of measurements. Here it is stored as a float representing seconds 
        for easier interpretation."""
        return self._timetick

    @property
    def initial_scan_count(self) -> int:
        """Get the initial scan count at the start of a measurement (read-only).
        
        This property returns the scan count from the sensor at the moment when 
        a measurement was started. It is used to track the number of scans captured 
        during a measurement session."""
        return self._initial_scan_count

    @property
    def status(self) -> str:
        """Current client status (read-only).
        
        Returns one of:
        - ``'disconnected'`` — no active socket connection
        - ``'busy'`` — a managed operation is running
        - ``'idle'`` — connected, no operation has run yet or flags were reset
        - ``'success'`` — last managed operation completed successfully
        - ``'error'`` — last managed operation failed
        - ``'cancelled'`` — last managed operation was cancelled
        """
        if not self.connected:
            return 'disconnected'
        if self._busy:
            return 'busy'
        return self._status

    def reset_flags(self) -> None:
        """Reset the busy, cancel, and finished flags to their default states."""
        self._busy = False
        self._cancel = False
        self._finished = False
        self._response = ''
        self._success = False
        self._status = 'idle'

    def connect(self) -> bool:
        """Establish connection to the sensor.

        This method attempts to create a socket connection to the sensor 
        using the specified host and port. It sets the socket timeout and 
        updates the connection status.
        
        Returns
        -------
        bool
            True if connection successful, False otherwise
        """
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.settimeout(self.timeout)
            self._socket.connect((self.host, self.port))
            self._connected = True
            self._logger.info(f'Connected to sensor at {self.host}:{self.port}')
        except Exception as e:
            self._logger.error(f'Failed to connect to sensor: {e}')
        finally:
            return self.connected
    
    def disconnect(self) -> None:
        """Disconnect from the sensor.
        
        This method closes the socket connection to the sensor and updates 
        the connection status.
        """
        try:
            if self._socket is not None:
                shutdown_socket(self._socket)
            self._logger.info('Disconnected from sensor')
        except Exception as e:
            self._logger.warning(f'Error during disconnect: {e}')
        finally:
            self._socket = None
            self._connected = False
    
    def send_command(
            self,
            command: str,
            parameter: str | int | None = None,
            trace: bool = True
            )-> Tuple[str, bool]:
        """Send a command to the sensor and get response.

        This method constructs a command message based on the provided 
        command and optional parameter, sends it to the sensor, and returns 
        the response. It includes error handling for connection issues and 
        logs the communication process.
        
        Parameters
        ----------
        command : str
            Command to send (e.g., 'loadjob', 'start', 'stop', 'readprop').
        parameter : str | int, optional
            Parameter for the command (e.g., job name for loadjob or ID).
            Defaults to None.
        trace : bool, optional
            If True, enables trace logging for the command. Defaults to True
        
        Returns
        -------
        str
            Response from sensor.
        bool
            True if response indicates success, False otherwise.
            
        Raises
        ------
        ConnectionError
            If not connected to the sensor.
        """
        if not self.connected or not self._socket:
            raise ConnectionError('Not connected to sensor')
        
        if parameter is not None:
            message = f'{command}{self.delimiter}{parameter}{self.termination}'
        else:
            message = f'{command}{self.termination}'
        
        try:
            self._socket.sendall(message.encode('utf-8'))
            if trace:
                self._logger.debug(f'Sent command: {message!r}')
            
            buffer = b""
            terminator = self.termination.encode('utf-8')
            while chunk := self._socket.recv(1024):
                buffer += chunk
                if terminator in buffer:
                    break
            
            self._response = buffer.decode('utf-8')
            self._success = self._response.strip().startswith('OK')
            if not self._success:
                self._logger.error(
                    f'Failed to execute command {command}: {self._response}')
            return self._response, self._success
            
        except Exception as e:
            self._logger.error(f'Error sending command: {e}')
            raise
    
    @_managed_operation
    def load_job(self, job_name: str, ensure: bool = True) -> bool:
        """Load a job on the sensor.

        This method sends a command to load a specified job on the sensor. 
        It returns `True` if the job was loaded successfully, and `False` otherwise.
        
        Parameters
        ----------
        job_name : str
            Name of the job to load.
        ensure : bool, optional
            If True, ensure the correct job is loaded after loading (default: True).
        
        Returns
        -------
        bool
            True if job loaded successfully, False otherwise.
        """
        return self._load_job(job_name, ensure)

    def _load_job(self, job_name: str, ensure: bool = True) -> bool:
        """Internal implementation of job loading (no flag management).
        
        Called by :meth:`load_job` (decorated) and :meth:`ensure_job_loaded` 
        (which runs inside an already-managed operation and must not re-enter 
        the decorator).
        """
        try:
            self.send_command('loadjob', job_name)
            if self.success and ensure:
                self._success = self.ensure_job_loaded(job_name)
        except Exception as e:
            self._logger.error(f'Error loading job {job_name}: {e}')
        finally:
            return self.success
    
    def ensure_job_loaded(self, job_name: str) -> bool:
        """Ensure the correct job is loaded on the sensor.

        This method checks if the specified job is currently loaded on the
        sensor. If it is not, it attempts to load the job. It returns `True` 
        if the correct job is loaded after the operation, and `False` otherwise.

        Parameters
        ----------
        job_name : str
            Name of the job to ensure is loaded.

        Returns
        -------
        bool
            True if the correct job is loaded, False otherwise.
        """
        try:
            actual_job = self.read_loaded_job()
            if actual_job == job_name:
                self._logger.info(
                    f'Correct job {job_name!r} is already loaded.')
                return True
            else:
                self._logger.warning(
                    f'Loaded job {actual_job!r} does not match expected '
                    f'job {job_name!r}. Attempting to load correct job.')
                return self._load_job(job_name, ensure=False)
        except Exception as e:
            self._logger.error(f'Error ensuring job {job_name} is loaded: {e}')
            return False
    
    def start_measurement(self) -> bool:
        """Start measurement on the sensor.

        This method sends a command to start measurement on the sensor. 
        The measurements will go on until stopped or until the job is unloaded. 
        It returns `True` if the measurement was started successfully, and 
        `False` otherwise.

        Returns
        -------
        bool
            True if measurement started successfully, False otherwise.
        """
        self._success = False
        try:
            self.send_command('start')
            assert self.success, f'Failed to start measurement: {self.response}'

            self._timetick = 0.0
            self._initial_scan_count = self.read_scan_count()
        except Exception as e:
            self._logger.error(f'Error starting measurement: {e}')
        finally:
            return self.success

    def trigger_measurement(self) -> bool:
        """Trigger a single measurement on the sensor.

        This method sends a command to trigger a single measurement on the 
        sensor. The measurement will be performed once and then stop automatically. 
        It returns `True` if the measurement was triggered successfully, and 
        `False` otherwise.
        
        Captures execution timestamp metadata that will be included in the 
        next dataset.

        Returns
        -------
        bool
            True if measurement triggered successfully, False otherwise.
        """
        success = False
        try:
            response, success = self.send_command('trigger')
        except Exception as e:
            self._logger.error(f'Error triggering measurement: {e}')
        finally:
            return success
    
    def stop_measurement(self) -> bool:
        """Stop measurement on the sensor.
        
        This method sends a command to stop measurement on the sensor. 
        It returns `True` if the measurement was stopped successfully, and 
        `False` otherwise.

        Returns
        -------
        bool
            True if measurement stopped successfully, False otherwise.
        """
        success = False
        try:
            response, success = self.send_command('stop')
        except Exception as e:
            self._logger.error(f'Error stopping measurement: {e}')
        finally:
            return success
    
    def read_loaded_job(self) -> str | None:
        """Read the currently loaded job name.

        This method sends a command to retrieve the name of the currently 
        loaded job on the sensor. It parses the response and returns the 
        job name if successful, or `None` otherwise.
        
        Returns
        -------
        str | None
            Name of currently loaded job, or None if unable to retrieve.
        """
        job_name = None
        try:
            response, success = self.send_command(
                'readprop', '/jobs#/loadedJob')
            assert success, f'Failed to read loaded job: {response}'

            parts = response.split(self.delimiter, 2)
            assert len(parts) >= 2, 'Invalid response format'

            job_name = parts[1].strip().strip('"')
        except AssertionError as e:
            self._logger.warning(str(e))
        except Exception as e:
            self._logger.error(f'Error getting loaded job: {e}')
        finally:
            return job_name

    def read_timetick(self) -> float:
        """Get the current measurement timetick directly from scanner metrics.
        
        This method retrieves the timetick of the most recent measurement from 
        the sensor by sending a command to read the appropriate property. It 
        parses the response to extract the timetick and returns it as a float 
        representing seconds. If there is an error in communication, parsing, 
        or if the sensor is not connected, it returns -1.0.

        Returns
        -------
        float
            Timetick of the last measurement in seconds, or -1.0 if unable to retrieve.
        
        Notes
        -----
        The raw timetick is a 64-bit positive integer that is guaranteed to increase 
        monotonically starting from zero. The conversion to seconds is done by 
        multiplying the raw value by 1E-6 and dividing by the STAMP_DIVISOR (1024) 
        to convert from the sensor's timestamp units to seconds."""
        timetick = -1.0
        try:
            assert self.connected, (
                'Sensor not connected or socket not available')
            
            response, success = self.send_command(
                'time', self.timestamp_id, False)
            assert success, f'Failed to read timetick: {response}'
            
            parts = response.split(self.delimiter)
            assert len(parts) >= 2, 'No timetick data in response'
            
            timetick = (
                1E-6 * float(parts[1].strip().rstrip('\r\n, ')) 
                / self.STAMP_DIVISOR)
        except AssertionError as e:
            self._logger.warning(str(e))
        except (ValueError, Exception) as e:
            self._logger.error(f'Error reading timestamp: {e}')
        finally:
            return timetick

    def read_scan_count(self) -> int:
        """Get the current scan count directly from scanner metrics.
        
        This method retrieves the current scan count from the sensor by 
        sending a command to read the appropriate property. It parses the 
        response to extract the scan count and returns it as an integer. 
        If there is an error in communication, parsing, or if the sensor is 
        not connected, it returns -1."""
        n_scans = -1
        try:
            assert self.connected and self._socket, (
                'Sensor not connected or socket not available')
            
            response, success = self.send_command(
                'readprop',
                '/scan/engines/LMIFringeSnapshot/scanners/scanner-0/metrics#/scanCount',
                False)
            
            assert success, f'Failed to read scan count: {response}'
            
            parts = response.split(self.delimiter, 1)
            assert len(parts) >= 2, 'No scan count data in response'
            
            n_scans = int(parts[1].strip().rstrip('\r\n, '))
        except AssertionError as e:
            self._logger.warning(str(e))
        except (ValueError, Exception) as e:
            self._logger.error(f'Error reading scan count: {e}')
        finally:
            return n_scans
    
    def read_property(self, resource_path: str) -> Dict[str, Any]:
        """Read a property from the sensor using REST API.

        This method uses the 'readprop' command to retrieve REST API resources 
        from the sensor. It returns the JSON response as a dictionary if successful, 
        or an empty dict otherwise.

        Parameters
        ----------
        resource_path : str
            REST API resource path (case sensitive).
            Examples: '/tools', '/tools/Script-100/metrics',
            '/tools/Script-100/metrics#/outputsByExtId/0/value'

        Returns
        -------
        dict[str, Any]
            JSON response as a dictionary, or empty dict if unable to retrieve.
        """
        data = {}
        try:
            response, success = self.send_command('readprop', resource_path)
            assert success, (
                f'Failed to read property {resource_path}: {response}')
            
            parts = response.split(self.delimiter, 1)
            assert len(parts) >= 2, 'No JSON data in response'
            
            json_str = parts[1].rstrip('\r\n, ')
            data = json.loads(json_str)
        except AssertionError as e:
            self._logger.warning(str(e))
        except json.JSONDecodeError as e:
            self._logger.error(f'Failed to parse JSON response: {e}')
        except Exception as e:
            self._logger.error(f'Error reading property {resource_path}: {e}')
        finally:
            return data
        
    def read_scanner_info(self) -> Dict[str, Any]:
        """Read scanner information.

        This method retrieves detailed information about the scanner
        configuration and status, such as model, serial number, firmware
        version, and other relevant properties. It uses the 'readprop'
        command to access the appropriate resource and returns the
        information as a dictionary.

        Returns
        -------
        dict[str, Any]
            Dictionary containing scanner information. Returns empty dict if 
            unable to retrieve.
        """
        info = {}
        try:
            response = self.read_property(
                '/scan/engines/LMIFringeSnapshot/scanners/scanner-0/metrics')
            assert isinstance(response, dict), 'Invalid response format'
            self._logger.debug('Retrieved scanner information')
            info = {'Scanner': response}
        except AssertionError as e:
            self._logger.warning(str(e))
        except Exception as e:
            self._logger.error(f'Error reading scanner information: {e}')
        finally:
            return info
        
    def read_sensor_info(self) -> Dict[str, Any]:
        """Read sensor information.

        This method retrieves general information about the sensor, such as 
        model, serial number, firmware version, etc. It uses the 'readprop' 
        command to access the '/scan/visibleSensors' resource and returns the 
        information as a dictionary.

        Returns
        -------
        dict[str, Any]
            Dictionary containing sensor information. Returns empty dict if 
            unable to retrieve.
        """
        info = {}
        try:
            response = self.read_property('/scan/visibleSensors')
            assert response and 'sensors' in response, (
                'No sensors data in response')
            self._logger.debug('Retrieved sensor information')
            info = {'Sensor': response['sensors'][0]}
        except AssertionError as e:
            self._logger.warning(str(e))
        except Exception as e:
            self._logger.error(f'Error reading sensor information: {e}')
        finally:
            return info

    def read_tools(self) -> Dict[int, str]:
        """Read all available tools in the currently loaded job.

        This method retrieves the list of all tools available in the 
        currently loaded job. It returns a dictionary with tool order 
        indices as keys and tool IDs as values.

        Each tool ID can be used to retrieve specific measurements and
        metrics for that tool. The method handles parsing the response
        from the sensor and extracting the relevant information.

        Returns
        -------
        Dict[int, str]
            Dictionary of tools with their order index as keys and their 
            IDs as values. Returns empty dict if unable to retrieve or if no
            tools found.
        """
        tools = {}
        try:
            response = self.read_property('/tools')
            assert response, 'No response received'
            
            embedded = response.get('_embedded', {})
            items = embedded.get('item', [])
            for item in items:
                href = item.get('_links', {}).get('self', {}).get('href', '')
                tool_id = href.replace('/tools/', '')
                index = item.get('ordIndex', None)
                if tool_id and index is not None:
                    tools[index] = tool_id
            self._logger.debug(f'Found {len(tools)} tools')
        except AssertionError as e:
            self._logger.warning(str(e))
        except Exception as e:
            self._logger.error(f'Error parsing tools: {e}')
        finally:
            return tools

    def read_tool_infos(self, tool_id: str) -> Dict[str, Any]:
        """Read tool informations.

        This method retrieves additional metadata about a specific tool,
        such as displayName, id, and other configuration properties. It 
        uses the 'readprop' command to access the tool's base properties 
        without metrics.

        Parameters
        ----------
        tool_id : str
            Tool identifier same as returned by read_tools() 
            method, e.g. 'SurfaceBoundingBox-62'

        Returns
        -------
        dict[str, Any]
            Dictionary containing tool properties such as displayName, 
            id, isBatchable, etc. Returns empty dict if unable to retrieve.
        """
        info = {}
        try:
            response = self.read_property(f'/tools/{tool_id}')
            assert response and isinstance(response, dict), (
                f'Invalid response for tool {tool_id}')
            
            self._logger.debug(f'Retrieved properties for tool {tool_id}')
            def desire_info(k: str, v: Any) -> bool:
                return (
                    not isinstance(v, dict)
                    and 'batch' not in k.lower()
                    and k.lower() not in ['id', 'toolType',])
            info = {k: i for k, i in response.items() if desire_info(k, i)}
        except AssertionError as e:
            self._logger.warning(str(e))
        except Exception as e:
            self._logger.error(f'Error reading tool properties for {tool_id}: {e}')
        finally:
            return info

    def read_tool_metrics(self, tool_id: str) -> Dict[str, Any]:
        """Read current measurement metrics from a specific tool.

        This method retrieves the current measurement outputs from a tool. 
        It uses the 'readprop' command to access the tool's metrics and extract 
        the relevant measurement data. The method returns a dictionary with 
        measurement names as keys and their values and decisions as values. 
        It includes error handling to ensure that it returns an empty dictionary 
        if unable to retrieve the measurements or if the data is not in the 
        expected format.

        Parameters
        ----------
        tool_id : str
            Tool identifier same as returned by read_tools() 
            method, e.g. 'SurfaceBoundingBox-62'

        Returns
        -------
        dict[str, Any]
            Dictionary with measurement names as keys and measurement
            data as values. Returns empty dict if unable to retrieve.
        """
        metrics = {}
        try:
            response = self.read_property(f'/tools/{tool_id}/metrics')
            assert response and isinstance(response, dict), (
                f'Invalid response for tool metrics {tool_id}')
            
            outputs = response.get('outputsByExtId', {})
            assert isinstance(outputs, dict), (
                f'Invalid outputs for tool metrics {tool_id}')
            
            for name, output in outputs.items():
                if (isinstance(output, dict)
                        and output.get('type', '').lower() == 'measurement'
                        and 'value' in output):
                    status = (
                        'Passed' if output.get('lastDecision', 1) else 'Failed')
                    metrics[name] = {
                        STATUS_FIELD: status,
                        **{k: output.get(k, None) for k in self._METRIC_VALUES}}
            if metrics and 'toolStats' in response:
                metrics['runTime'] = {
                    'Value': response['toolStats'].get('runTime', None) / 1E6,
                    'Unit': 's'}

            self._logger.debug(
                f'Retrieved {len(metrics)} measurements from {tool_id}')
        except AssertionError as e:
            self._logger.warning(str(e))
        except Exception as e:
            self._logger.error(
                f'Error getting measurements from {tool_id}: {e}')
        finally:
            return metrics
        
    def read_tool_outputs(self, tool_id: str) -> Dict[str, Dict[str, Any]]:
        """Read current measurement outputs from a specific tool.

        This method retrieves the current measurement outputs from a tool. 
        It uses the 'readprop' command to access the tool's outputs and extract 
        the relevant data. The method returns a dictionary with output names as 
        keys and their parameters as values. It includes error handling to ensure 
        that it returns an empty dictionary if unable to retrieve the outputs or 
        if the data is not in the expected format.

        Parameters
        ----------
        tool_id : str
            Tool identifier same as returned by read_tools() 
            method, e.g. 'SurfaceBoundingBox-62'

        Returns
        -------
        Dict[str, Any]
            Dictionary with output names as keys and their parameters
            as values. Returns empty dict if unable to retrieve.
        """
        outputs = {}
        try:
            response = self.read_property(f'/tools/{tool_id}/outputs')
            assert response and isinstance(response, dict), (
                f'Invalid response for tool outputs {tool_id}')
            
            items = response.get('_embedded', {}).get('item', {})
            for output_id in items.keys():
                output = self.read_property(
                    f'/tools/{tool_id}/outputs/{output_id}')
                if not isinstance(output, dict):
                    self._logger.warning(
                        f'Invalid output format for {tool_id} output {output_id}')
                    continue
                outputs[output.get('displayName', output_id)] = (
                    {'decisionMax': None, 'decisionMin': None}
                    | output.get('parameters', {}))
            
            self._logger.debug(
                f'Retrieved {len(outputs)} outputs for {tool_id}')
        except AssertionError as e:
            self._logger.warning(str(e))
        except Exception as e:
            self._logger.error(
                f'Error getting raw outputs from {tool_id}: {e}')
        finally:
            return outputs

    def read_tool_data(self) -> Dict[str, Any]:
        """Read all data from sensor for all tools in the current job.

        This method retrieves metrics and infos from all tools in the 
        currently loaded job and returns them in a structured format, such 
        as a nested dictionary, with tool IDs as keys and their measurement 
        data and infos as values.
        
        It iterates through all available tools, retrieves their metrics
        and infos, and compiles the data into a comprehensive dictionary. 
        The method includes error handling to ensure that it returns an empty 
        dictionary if unable to retrieve the information or if no tools are found.

        Returns
        -------
        Dict[str, Any]
            Nested dictionary with tool IDs as keys and their 
            measurement data and infos as values. Returns empty dict if 
            unable to retrieve.
        """
        data = {}
        try:
            tools = self.read_tools()
            assert tools, 'No tools found in current job'
            
            for tool_id in tools.values():
                metrics = self.read_tool_metrics(tool_id)
                if not metrics:
                    continue

                outputs = self.read_tool_outputs(tool_id)
                for key, values in outputs.items():
                    metrics[key] = metrics.get(key, {}) | values

                infos = self.read_tool_infos(tool_id)
                name = infos.pop('displayName', tool_id)
                data[name] = {
                    FAILED_COUNT_FIELD: count_fails(metrics),
                    **infos,
                    **metrics}
            self._logger.info(
                f'Retrieved data from {len(data)} tools')
        except AssertionError as e:
            self._logger.warning(str(e))
        except Exception as e:
            self._logger.error(f'Error getting all data: {e}')
        finally:
            return data
        
    def _create_dataset(
            self,
            duration: float,
            timetick: float) -> Dict[str, Any]:
        """Create a dataset by reading scanner info, sensor info, and tool data.

        This method retrieves the current scanner information, sensor 
        information, and tool data from the sensor and combines them into a 
        single dataset dictionary. The execution metadata is expected to be 
        already captured and stored in :attr:`_execution_data` before calling 
        this method. The resulting dataset includes all relevant information 
        about the measurement and the tools used.

        Parameters
        ----------
        duration : float
            Duration of the measurement in seconds.
        timetick : float
            Timetick of the measurement in seconds.

        Returns
        -------
        Dict[str, Any]
            Combined dataset with execution metadata, scanner info, sensor 
            info, and tool data. Returns empty dict if unable to retrieve.
        """
        dataset = {}
        try:
            self._timetick = timetick
            self._execution_data['Execution']['Duration']['Value'] = (
                duration)
            dataset = (
                self._execution_data.copy()
                | self.read_scanner_info()
                | self.read_sensor_info()
                | self.read_tool_data())
            failed_count = count_fails(dataset)
            status = 'Failed' if failed_count > 0 else 'Passed'
            dataset = {
                STATUS_FIELD: status,
                FAILED_COUNT_FIELD: failed_count,
                **dataset,}
            self._logger.info(
                f'Dataset captured successfully within {duration:.3f} seconds')
        except Exception as e:
            self._logger.error(f'Error creating dataset: {e}')
        finally:
            return dataset

    @_managed_operation
    def capture_dataset(
            self,
            timeout: float = 10.0,
            poll_interval: float = 0.1,
            measurement_series: int | None = None,
            measurement_number: int | None = None,
            measurement_repeat: int | None = None,
            ) -> Dict[str, Any]:
        """Generate a new dataset by triggering measurement and waiting for completion.

        Workflow: Reads initial scan count, triggers measurement (which 
        captures execution metadata), polls the scanner every `poll_interval` 
        seconds until scan count increases or timeout occurs, then reads scanner 
        info, sensor info, and tool data. Returns combined dataset with execution 
        metadata at the front. Metadata is cleared after successful read or on error.

        Parameters
        ----------
        timeout : float, optional
            Maximum time to wait for scan completion in seconds (default: 10.0).
        poll_interval : float, optional
            Time between scan count checks in seconds (default: 0.1).
        measurement_series : int | None, optional
            Optional series number to include in execution metadata.
        measurement_number : int | None, optional
            Optional measurement number to include in execution metadata.
        measurement_repeat : int | None, optional
            Optional repeat count to include in execution metadata.

        Returns
        -------
        Dict[str, Any]
            Complete dataset including 'Execution' metadata, 'Scanner' 
            info, 'Sensor' info, and tool data. Returns empty dict if 
            measurement fails or times out.
        
        Notes
        -----
        Current implementation polls scan count to detect measurement 
        completion, which is a workaround. The measurement duration 
        calculation is also a hack. No better solution is currently 
        known to reliably detect when a triggered measurement completes 
        and retrieve its exact duration.
        
        """
        dataset = {}
        self._logger.debug(
            f'Starting dataset capture; {measurement_series=}, {measurement_number=}, '
            f'{measurement_repeat=}, {timeout=}, {poll_interval=}')
        try:
            self._capture_execution_data(
                measurement_series=measurement_series,
                measurement_number=measurement_number,
                measurement_repeat=measurement_repeat)
            prev_scan_count = max(self.initial_scan_count, self.read_scan_count())
            start = time.time()
            if not self.trigger_measurement():
                raise RuntimeError('Failed to trigger measurement')
            
            self._logger.info(
                f'Waiting for scan to reach new timetick'
                f' (initial was {self.timetick:.4f} s)')
            while time.time() - start < timeout:
                assert not self.cancel, 'Dataset capture cancelled'
                
                time.sleep(poll_interval) # avoid hammering the sensor with requests
                current_timetick = self.read_timetick()
                current_scan_count = self.read_scan_count()
                duration = time.time() - start

                if current_scan_count > prev_scan_count:
                    dataset = self._create_dataset(
                        duration=duration, timetick=current_timetick)
                    break
            else:
                current_timetick = self.read_timetick()
                current_scan_count = self.read_scan_count()
                if (current_timetick > self.timetick 
                        or current_scan_count > prev_scan_count):
                    dataset = self._create_dataset(
                        duration=timeout, timetick=current_timetick)
                else:
                    raise TimeoutError(
                        f'Timeout waiting for scan completion after {timeout}s')
        
        except AssertionError as e:
            self._status = 'cancelled'
            self._logger.warning(str(e))
        except Exception as e:
            self._logger.error(f'Error capturing dataset: {e}')
        finally:
            self._cancel = False
            self._execution_data = {}
            return dataset

    def _capture_execution_data(
            self,
            measurement_series: int | None = None,
            measurement_number: int | None = None,
            measurement_repeat: int | None = None,
            ) -> None:
        """Capture execution data.
        
        This method captures the execution timestamp and initializes the
        execution metadata that will be included in the next dataset. It
        reads the currently loaded job and stores it along with the current 
        scan count. The duration is initialized to 0 and will be updated when 
        the measurement completes. This method is called when triggering a 
        measurement to ensure that the execution metadata is accurately captured 
        for that specific measurement.

        Parameters
        ----------
        measurement_series : int | None, optional
            Optional series number to include in execution metadata.
            Defaults to None.
        measurement_number : int | None, optional
            Optional measurement number to include in execution 
            metadata. Defaults to None.
        measurement_repeat : int | None, optional
            Optional measurement repeat count to include in execution 
            metadata. Defaults to None.
        """
        now = datetime.now()
        self._execution_data = {
            'Execution': {
                'Date': now.strftime('%Y-%m-%d'),
                'Time': now.strftime('%H:%M:%S.%f')[:-3],
                'Datetime': now.isoformat(),
                'Job': self.read_loaded_job(),
                'MeasurementSeries': measurement_series,
                'MeasurementNr': measurement_number,
                'MeasurementRepeat': measurement_repeat,
                'Duration': {
                    'Value': None,
                    'Unit': 's',},
                'Stamp': {
                    'Value': self.timetick,
                    'Unit': 's',},}}
    
    def __call__(self, method: str, **kwargs: Any) -> Any:
        """Call a method by name with keyword arguments.

        This method allows dynamic calling of ASCIIClient methods by name. 
        It checks if the specified method exists and is callable, then calls 
        it with the provided keyword arguments. If the method does not exist 
        or is not callable, it raises an AttributeError.
        
        Parameters
        ----------
        method : str
            Name of the method to call.
        **kwargs
            Keyword arguments to pass to the method.
            
        Returns
        -------
        Any
            Return value of the called method.
            
        Raises
        ------
        AttributeError
            If the method does not exist or is not callable.
        """

        if not hasattr(self, method) or not callable(getattr(self, method)):
            raise AttributeError(f'Method {method} not found in {self.__class__.__name__}')
        
        func = getattr(self, method)
        return func(**kwargs)

    def __enter__(self) -> Self:
        """Context manager entry.
        
        This method allows the ASCIIClient to be used as a context manager, 
        automatically connecting on entry and stopping measurement and disconnecting 
        on exit."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit.

        This method allows the ASCIIClient to be used as a context manager, 
        automatically stopping measurement and disconnecting on exit."""
        self.stop_measurement()
        self.disconnect()
