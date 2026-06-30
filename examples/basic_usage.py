"""
Basic usage example for LMI ASCII client.

This example demonstrates how to connect to a sensor, load a job,
and capture measurement data.
"""

import logging
from lmi_ascii import ASCIIClient

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def main():
    # Sensor configuration
    SENSOR_IP = '192.168.1.10'  # Change to your sensor's IP address
    JOB_NAME = 'MyInspectionJob'  # Change to your job name
    
    print("="*60)
    print("LMI ASCII Client - Basic Usage Example")
    print("="*60)
    
    # Connect to sensor using context manager
    with ASCIIClient(host=SENSOR_IP, timeout=10.0) as client:
        
        # Check connection
        if not client.connected:
            print("Failed to connect to sensor!")
            return
        
        print(f"\n✓ Connected to sensor at {SENSOR_IP}")
        
        # Read sensor information
        sensor_info = client.read_sensor_info()
        if sensor_info:
            sensor = sensor_info.get('Sensor', {})
            print(f"  Model: {sensor.get('model', 'Unknown')}")
            print(f"  Serial: {sensor.get('serialNumber', 'Unknown')}")
        
        # Load a job
        print(f"\nLoading job: {JOB_NAME}")
        if client.load_job(JOB_NAME):
            print(f"✓ Job '{JOB_NAME}' loaded successfully")
        else:
            print(f"✗ Failed to load job '{JOB_NAME}'")
            return
        
        # Read available tools
        print("\nReading available tools...")
        tools = client.read_tools()
        if tools:
            print(f"✓ Found {len(tools)} tools:")
            for idx, tool_id in tools.items():
                print(f"  [{idx}] {tool_id}")
        
        # Capture a dataset
        print("\nCapturing measurement dataset...")
        dataset = client.capture_dataset(
            timeout=10.0,
            poll_interval=0.1,
            measurement_number=1
        )
        
        if dataset:
            print("✓ Dataset captured successfully!")
            print(f"  Status: {dataset.get('Status', 'Unknown')}")
            print(f"  Failed count: {dataset.get('FailedCount', 0)}")
            
            # Show execution info
            if 'Execution' in dataset:
                exec_data = dataset['Execution']
                print(f"  Datetime: {exec_data.get('Datetime', 'N/A')}")
                duration = exec_data.get('Duration', {})
                print(f"  Duration: {duration.get('Value', 'N/A')} {duration.get('Unit', '')}")
            
            # Show tool results
            print("\nTool Results:")
            for key, value in dataset.items():
                if isinstance(value, dict) and 'Status' in value:
                    status = value['Status']
                    symbol = "✓" if status == "Passed" else "✗"
                    print(f"  {symbol} {key}: {status}")
        else:
            print("✗ Failed to capture dataset")
    
    print("\n" + "="*60)
    print("Disconnected from sensor")
    print("="*60)


if __name__ == '__main__':
    main()
