# LMI ASCII

A Python client library for communicating with LMI Technologies Gocator sensors running GoPxL software via the Ethernet ASCII protocol.

## Features

- **Simple API** for connecting to and controlling LMI sensors
- **Job Management** - Load, verify, and manage sensor jobs
- **Measurement Control** - Start, stop, and trigger measurements
- **Data Retrieval** - Read tool data, metrics, and sensor information  
- **REST API Access** - Use the 'readprop' command to access sensor REST API
- **Context Manager** support for automatic connection management
- **Type Hints** for better IDE support and code safety
- **Comprehensive Logging** using Python's standard logging module

## Installation

```bash
pip install lmi-ascii
```

Or install from source:

```bash
git clone https://github.com/yourusername/lmi-ascii.git
cd lmi-ascii
pip install -e .
```

## Quick Start

```python
from lmi_ascii import ASCIIClient
import logging

# Configure logging (optional)
logging.basicConfig(level=logging.INFO)

# Connect to sensor
with ASCIIClient(host='192.168.1.10') as client:
    # Load a job
    client.load_job('MyInspectionJob')
    
    # Capture a dataset
    dataset = client.capture_dataset(
        timeout=10.0,
        measurement_number=1
    )
    
    # Access measurement results
    print(f"Status: {dataset.get('Status')}")
    print(f"Failed count: {dataset.get('FailedCount')}")
```

## Usage Examples

### Basic Connection

```python
from lmi_ascii import ASCIIClient

# Create client instance
client = ASCIIClient(
    host='192.168.1.10',
    port=8190,  # Default Ethernet ASCII port
    timeout=10.0
)

# Connect
if client.connect():
    print("Connected successfully!")
    
    # Your code here...
    
    # Disconnect
    client.disconnect()
```

### Using Context Manager (Recommended)

```python
from lmi_ascii import ASCIIClient

with ASCIIClient(host='192.168.1.10') as client:
    # Connection is automatic
    # Disconnection is automatic on exit
    
    job_name = client.read_loaded_job()
    print(f"Current job: {job_name}")
```

### Job Management

```python
with ASCIIClient(host='192.168.1.10') as client:
    # Load a job
    success = client.load_job('ProductionJob_v2')
    
    # Verify the correct job is loaded
    loaded_job = client.read_loaded_job()
    print(f"Loaded job: {loaded_job}")
```

### Measurement Control

```python
with ASCIIClient(host='192.168.1.10') as client:
    client.load_job('MyJob')
    
    # Start continuous measurement
    client.start_measurement()
    
    # ... do something ...
    
    # Stop measurement
    client.stop_measurement()
    
    # Or trigger a single measurement
    client.trigger_measurement()
```

### Reading Sensor Data

```python
with ASCIIClient(host='192.168.1.10') as client:
    client.load_job('MyJob')
    
    # Read sensor information
    sensor_info = client.read_sensor_info()
    print(f"Sensor: {sensor_info}")
    
    # Read all tools in current job
    tools = client.read_tools()
    print(f"Available tools: {tools}")
    
    # Read metrics from a specific tool
    tool_id = tools[0]  # First tool
    metrics = client.read_tool_metrics(tool_id)
    print(f"Tool metrics: {metrics}")
```

### Capturing Complete Datasets

```python
with ASCIIClient(host='192.168.1.10') as client:
    client.load_job('InspectionJob')
    
    # Capture a dataset with metadata
    dataset = client.capture_dataset(
        timeout=10.0,
        poll_interval=0.1,
        measurement_series=1,
        measurement_number=42,
        measurement_repeat=1
    )
    
    # Check overall status
    if dataset['Status'] == 'Passed':
        print("Inspection passed!")
    else:
        print(f"Inspection failed. {dataset['FailedCount']} failures detected.")
    
    # Access tool data
    for tool_name, tool_data in dataset.items():
        if isinstance(tool_data, dict) and 'Status' in tool_data:
            print(f"{tool_name}: {tool_data['Status']}")
```

### Using the REST API

```python
with ASCIIClient(host='192.168.1.10') as client:
    # Read any REST API resource
    tools_data = client.read_property('/tools')
    
    # Read specific tool metrics
    tool_metrics = client.read_property('/tools/Script-100/metrics')
    
    # Read output value
    output_value = client.read_property(
        '/tools/Script-100/metrics#/outputsByExtId/0/value'
    )
```

### Custom Logging

```python
import logging
from lmi_ascii import ASCIIClient

# Create custom logger
custom_logger = logging.getLogger('my_app.lmi')
custom_logger.setLevel(logging.DEBUG)

# Create client with custom logger
client = ASCIIClient(
    host='192.168.1.10',
    logger=custom_logger
)
```

## API Reference

### ASCIIClient Class

#### Constructor Parameters

- `timestamp_id` (int): External ID for timestamps (default: 0)
- `host` (str): IP address of the sensor (default: '127.0.0.1')
- `port` (int): Ethernet ASCII port (default: 8190)
- `delimiter` (str): Command parameter delimiter (default: ',')
- `termination` (str): Line termination characters (default: '\r\n')
- `timeout` (float): Socket timeout in seconds (default: 10.0)
- `logger` (logging.Logger): Custom logger instance (optional)

#### Main Methods

- **`connect()`** - Establish connection to sensor
- **`disconnect()`** - Close connection to sensor
- **`load_job(job_name, ensure=True)`** - Load a job on the sensor
- **`start_measurement()`** - Start continuous measurement
- **`stop_measurement()`** - Stop measurement
- **`trigger_measurement()`** - Trigger a single measurement
- **`capture_dataset(...)`** - Capture a complete measurement dataset
- **`read_loaded_job()`** - Get currently loaded job name
- **`read_property(resource_path)`** - Read REST API resource
- **`read_tools()`** - Get all tools in current job
- **`read_tool_metrics(tool_id)`** - Get metrics from a tool
- **`read_sensor_info()`** - Get sensor information
- **`send_command(command, parameter=None)`** - Send raw ASCII command

#### Properties

- **`connected`** (bool, read-only) - Connection status
- **`busy`** (bool, read-only) - Whether an operation is in progress
- **`status`** (str, read-only) - Current client status
- **`response`** (str, read-only) - Last sensor response
- **`success`** (bool, read-only) - Success status of last command

## Protocol Documentation

For detailed information about the Ethernet ASCII protocol, refer to:

- [LMI GoPxL Documentation](https://am.lmi3d.com/manuals/gopxl/)
- [Ethernet ASCII Protocol Reference](https://am.lmi3d.com/manuals/gopxl/gopxl-1.2/LMILaserLineProfiler/Default.htm#Protocols/ASCIIProtocol/EthernetCommunication/PollingCommands.htm)

## Requirements

- Python 3.10 or higher
- No external dependencies (uses only standard library)

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues and questions:
- GitHub Issues: https://github.com/yourusername/lmi-ascii/issues
- LMI Support: https://support.lmi3d.com/

## Changelog

### Version 1.0.0 (2026-06-30)

- Initial release
- Full Ethernet ASCII protocol support
- Context manager support
- Comprehensive logging
- Type hints throughout
- Complete dataset capture functionality
