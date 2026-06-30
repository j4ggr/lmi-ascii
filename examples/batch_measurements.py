"""
Batch measurement example for LMI ASCII client.

This example demonstrates how to capture multiple measurements
in a loop and save the results.
"""

import logging
import json
from pathlib import Path
from datetime import datetime
from lmi_ascii import ASCIIClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def save_dataset(dataset: dict, output_dir: Path, measurement_number: int):
    """Save a dataset to a JSON file."""
    if not dataset:
        return None
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"measurement_{measurement_number:04d}_{timestamp}.json"
    filepath = output_dir / filename
    
    # Save to JSON
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)
    
    return filepath


def run_batch_measurements(
    client: ASCIIClient,
    job_name: str,
    num_measurements: int,
    output_dir: Path,
    series_number: int = 1
):
    """Capture multiple measurements and save results."""
    
    print(f"\n{'='*60}")
    print(f"Starting batch measurement")
    print(f"  Job: {job_name}")
    print(f"  Count: {num_measurements}")
    print(f"  Series: {series_number}")
    print(f"  Output: {output_dir}")
    print(f"{'='*60}\n")
    
    # Load job
    if not client.load_job(job_name):
        print(f"✗ Failed to load job '{job_name}'")
        return
    
    print(f"✓ Job '{job_name}' loaded successfully\n")
    
    # Statistics tracking
    results = {
        'passed': 0,
        'failed': 0,
        'errors': 0
    }
    
    # Capture measurements
    for i in range(1, num_measurements + 1):
        print(f"[{i}/{num_measurements}] Capturing measurement...")
        
        try:
            # Capture dataset
            dataset = client.capture_dataset(
                timeout=10.0,
                poll_interval=0.1,
                measurement_series=series_number,
                measurement_number=i,
                measurement_repeat=1
            )
            
            if not dataset:
                print(f"  ✗ Failed to capture measurement {i}")
                results['errors'] += 1
                continue
            
            # Check status
            status = dataset.get('Status', 'Unknown')
            failed_count = dataset.get('FailedCount', 0)
            
            if status == 'Passed':
                results['passed'] += 1
                print(f"  ✓ Passed")
            else:
                results['failed'] += 1
                print(f"  ✗ Failed ({failed_count} failures)")
            
            # Save to file
            filepath = save_dataset(dataset, output_dir, i)
            if filepath:
                print(f"  → Saved to {filepath.name}")
            
        except KeyboardInterrupt:
            print("\n\nBatch interrupted by user")
            break
        except Exception as e:
            print(f"  ✗ Error: {e}")
            results['errors'] += 1
        
        print()  # Blank line between measurements
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Batch Measurement Summary")
    print(f"{'='*60}")
    print(f"  Total: {num_measurements}")
    print(f"  Passed: {results['passed']} ({results['passed']/num_measurements*100:.1f}%)")
    print(f"  Failed: {results['failed']} ({results['failed']/num_measurements*100:.1f}%)")
    print(f"  Errors: {results['errors']} ({results['errors']/num_measurements*100:.1f}%)")
    print(f"{'='*60}\n")


def main():
    # Configuration
    SENSOR_IP = '192.168.1.10'  # Change to your sensor's IP
    JOB_NAME = 'MyInspectionJob'  # Change to your job name
    NUM_MEASUREMENTS = 10  # Number of measurements to capture
    SERIES_NUMBER = 1  # Series/batch identifier
    OUTPUT_DIR = Path('./measurements')  # Output directory
    
    print("="*60)
    print("LMI ASCII Client - Batch Measurement Example")
    print("="*60)
    
    # Connect and run batch
    with ASCIIClient(host=SENSOR_IP, timeout=15.0) as client:
        
        if not client.connected:
            print("✗ Failed to connect to sensor!")
            return
        
        print(f"✓ Connected to sensor at {SENSOR_IP}")
        
        # Run batch measurements
        run_batch_measurements(
            client=client,
            job_name=JOB_NAME,
            num_measurements=NUM_MEASUREMENTS,
            output_dir=OUTPUT_DIR,
            series_number=SERIES_NUMBER
        )
    
    print("Disconnected from sensor")


if __name__ == '__main__':
    main()
