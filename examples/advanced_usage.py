"""
Advanced usage example for LMI ASCII client.

This example demonstrates advanced features like:
- Continuous measurement
- Reading tool metrics directly
- Using the REST API
- Custom logging
"""

import logging
import time
from lmi_ascii import ASCIIClient

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def demonstrate_continuous_measurement(client: ASCIIClient, duration: float = 5.0):
    """Start measurement, wait, then stop."""
    print("\n--- Continuous Measurement Demo ---")
    
    if client.start_measurement():
        print(f"✓ Measurement started")
        print(f"  Waiting {duration} seconds...")
        
        time.sleep(duration)
        
        if client.stop_measurement():
            print("✓ Measurement stopped")
    else:
        print("✗ Failed to start measurement")


def demonstrate_tool_inspection(client: ASCIIClient):
    """Read and display detailed tool information."""
    print("\n--- Tool Inspection Demo ---")
    
    tools = client.read_tools()
    if not tools:
        print("No tools found")
        return
    
    # Inspect first tool in detail
    first_tool_id = tools[0]
    print(f"\nInspecting tool: {first_tool_id}")
    
    # Read tool info
    info = client.read_tool_infos(first_tool_id)
    print(f"\nTool Information:")
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    # Read tool metrics
    metrics = client.read_tool_metrics(first_tool_id)
    print(f"\nTool Metrics:")
    for metric_name, metric_data in metrics.items():
        if isinstance(metric_data, dict):
            print(f"  {metric_name}:")
            for k, v in metric_data.items():
                print(f"    {k}: {v}")
        else:
            print(f"  {metric_name}: {metric_data}")
    
    # Read tool outputs
    outputs = client.read_tool_outputs(first_tool_id)
    print(f"\nTool Outputs:")
    for output_name, output_params in outputs.items():
        print(f"  {output_name}:")
        for param, value in output_params.items():
            print(f"    {param}: {value}")


def demonstrate_rest_api(client: ASCIIClient):
    """Use the REST API to read various properties."""
    print("\n--- REST API Demo ---")
    
    # Read all tools using REST API
    tools_response = client.read_property('/tools')
    if tools_response:
        embedded = tools_response.get('_embedded', {})
        items = embedded.get('item', [])
        print(f"\nFound {len(items)} tools via REST API:")
        for item in items:
            tool_type = item.get('toolType', 'Unknown')
            display_name = item.get('displayName', 'N/A')
            print(f"  - {display_name} ({tool_type})")
    
    # Read scanner metrics
    scanner_path = '/scan/engines/LMIFringeSnapshot/scanners/scanner-0/metrics'
    scanner_metrics = client.read_property(scanner_path)
    if scanner_metrics:
        print(f"\nScanner Metrics:")
        print(f"  Scan count: {scanner_metrics.get('scanCount', 'N/A')}")
        print(f"  Frame rate: {scanner_metrics.get('frameRate', 'N/A')}")


def demonstrate_status_monitoring(client: ASCIIClient):
    """Monitor client status during operations."""
    print("\n--- Status Monitoring Demo ---")
    
    print(f"Initial status: {client.status}")
    print(f"Connected: {client.connected}")
    print(f"Busy: {client.busy}")
    
    # Trigger a measurement and monitor status
    print("\nTriggering measurement...")
    client.trigger_measurement()
    print(f"Status after trigger: {client.status}")
    print(f"Success: {client.success}")
    print(f"Response: {client.response.strip()}")


def main():
    # Sensor configuration
    SENSOR_IP = '192.168.1.10'  # Change to your sensor's IP
    JOB_NAME = 'MyInspectionJob'  # Change to your job name
    
    print("="*60)
    print("LMI ASCII Client - Advanced Usage Example")
    print("="*60)
    
    # Create client with custom timeout
    with ASCIIClient(host=SENSOR_IP, timeout=15.0) as client:
        
        if not client.connected:
            print("Failed to connect to sensor!")
            return
        
        print(f"✓ Connected to sensor at {SENSOR_IP}")
        
        # Load job
        if not client.load_job(JOB_NAME):
            print(f"Failed to load job '{JOB_NAME}'")
            return
        
        print(f"✓ Job '{JOB_NAME}' loaded")
        
        # Run demonstrations
        try:
            demonstrate_status_monitoring(client)
            demonstrate_tool_inspection(client)
            demonstrate_rest_api(client)
            demonstrate_continuous_measurement(client, duration=3.0)
            
        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print("Demo completed")
    print("="*60)


if __name__ == '__main__':
    main()
