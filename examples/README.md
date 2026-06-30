# Examples

This directory contains example scripts demonstrating various use cases of the LMI ASCII client library.

## Prerequisites

Before running these examples, make sure you have:

1. Installed the lmi-ascii package:
   ```bash
   pip install lmi-ascii
   ```

2. A Gocator sensor running GoPxL software accessible on your network

3. Updated the configuration variables in each script:
   - `SENSOR_IP`: Your sensor's IP address
   - `JOB_NAME`: Name of a job loaded on your sensor

## Examples

### basic_usage.py

Demonstrates fundamental operations:
- Connecting to a sensor
- Loading a job
- Reading sensor information
- Reading available tools
- Capturing a single measurement dataset

**Run:**
```bash
python examples/basic_usage.py
```

### advanced_usage.py

Shows advanced features:
- Continuous measurement (start/stop)
- Detailed tool inspection
- Reading tool metrics and outputs
- Using the REST API directly
- Status monitoring

**Run:**
```bash
python examples/advanced_usage.py
```

### batch_measurements.py

Demonstrates production-style batch processing:
- Capturing multiple measurements in a loop
- Saving results to JSON files
- Tracking statistics (pass/fail rates)
- Proper error handling

**Run:**
```bash
python examples/batch_measurements.py
```

## Customization

Each example can be customized by modifying the configuration variables at the top of the file:

```python
SENSOR_IP = '192.168.1.10'  # Your sensor IP
JOB_NAME = 'MyInspectionJob'  # Your job name
# ... other settings
```

## Output

- **basic_usage.py**: Console output showing connection status and measurement results
- **advanced_usage.py**: Detailed console output with tool information and REST API responses
- **batch_measurements.py**: Creates a `measurements/` directory with JSON files for each captured dataset

## Troubleshooting

### Connection Issues

If you can't connect to the sensor:

1. Verify the sensor IP address is correct
2. Check that the sensor is powered on and connected to the network
3. Ensure GoPxL is running on the sensor
4. Verify Ethernet ASCII protocol is enabled (port 8190)
5. Check firewall settings

### Job Loading Issues

If you can't load a job:

1. Verify the job name is correct (case-sensitive)
2. Check that the job exists on the sensor
3. Ensure the job is valid and can be loaded manually via the GoPxL web interface

### Measurement Failures

If measurements fail:

1. Check sensor alignment
2. Verify the target is in the sensor's field of view
3. Review job configuration and tool settings
4. Check sensor logs via the GoPxL web interface

## Additional Resources

- [LMI ASCII Documentation](../README.md)
- [GoPxL User Manual](https://am.lmi3d.com/manuals/gopxl/)
- [LMI Support](https://support.lmi3d.com/)
