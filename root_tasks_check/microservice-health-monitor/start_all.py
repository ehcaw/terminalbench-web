#!/usr/bin/env python3
"""
Start All Services - Launch all microservice components
Team: Infrastructure
Note: Work in progress - needs cleanup
"""

import subprocess
import time
import os
import sys
import signal

print("=== Microservice Health Monitor Startup ===")
print("Starting all services...")

# Store process references
processes = []

def start_service(script_name, service_name):
    """
    Start a service script
    """
    print(f"Starting {service_name}...")
    try:
        # BUG: No file existence check - will fail silently
        process = subprocess.Popen(
            ['python3', script_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        processes.append(process)
        print(f"✓ {service_name} started (PID: {process.pid})")
        return process
    except Exception as e:
        print(f"✗ Failed to start {service_name}: {e}")
        return None

def signal_handler(sig, frame):
    """
    Handle shutdown signals gracefully
    """
    print("\n--- Shutting Down Services ---")
    
    for process in processes:
        if process:
            print(f"Stopping process {process.pid}...")
            process.terminate()
            # BUG: No timeout handling - could hang forever
            process.wait()
    
    print("All services stopped.")
    sys.exit(0)

def main():
    """
    Main startup sequence
    """
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("\n--- Starting Services ---")
    
    # BUG: Wrong filename - should be mock_services.py
    mock_process = start_service('mock_service.py', 'Mock Services')
    # BUG: Too short delay - race condition possible
    time.sleep(0.5)
    
    # Start health service
    health_process = start_service('health_service.py', 'Health Service')
    time.sleep(0.5)
    
    # Start dashboard
    dashboard_process = start_service('dashboard.py', 'Dashboard')
    time.sleep(0.5)
    
    # BUG: Wrong filename - should be alerts.py
    alerts_process = start_service('alert.py', 'Alert System')
    
    print("\n--- All Services Started ---")
    print("Mock Services: http://localhost:8081, 8082, 8083")
    print("Health Service: http://localhost:8080/health")
    print("Dashboard: http://localhost:8090")
    print("Alert System: Monitoring and logging to alerts.log")
    print("\nPress Ctrl+C to stop all services")
    
    try:
        # Keep main process alive
        while True:
            # BUG: Too frequent checking - wastes CPU
            time.sleep(0.1)
            
            # BUG: No actual process monitoring - commented out
            # for process in processes:
            #     if process and process.poll() is not None:
            #         print(f"Warning: Process {process.pid} has stopped unexpectedly")
            
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

if __name__ == '__main__':
    main()
