#!/usr/bin/env python3
"""
Health Service - Monitors microservice health status
Author: Development Team
Version: 1.0
"""

import flask
from flask import Flask, jsonify
import requests
import json
import time
from datetime import datetime

app = Flask(__name__)

# Load configuration
with open('config.json', 'r') as f:
    config = json.load(f)

def check_service_health(service):
    """
    Check health of a single service
    Returns service status dict
    """
    start_time = time.time()
    try:
        # BUG: Using wrong timeout - should use config['timeout_seconds'] but uses hardcoded 1
        response = requests.get(f"http://localhost:{service['port']}/health", timeout=1)
        response_time_ms = int((time.time() - start_time) * 1000)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "name": service["name"],
                "status": data.get("status", "unknown"),
                "response_time_ms": response_time_ms,
                "last_check": datetime.now().isoformat()
            }
        else:
            return {
                "name": service["name"],
                "status": "down",
                "response_time_ms": response_time_ms,
                "last_check": datetime.now().isoformat()
            }
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        return {
            "name": service["name"],
            "status": "down",
            "response_time_ms": response_time_ms,
            "last_check": datetime.now().isoformat()
        }

@app.route('/health')
def health_check():
    """
    Main health check endpoint
    Returns aggregated health status
    """
    service_results = []
    healthy_count = 0
    
    for service in config['services']:
        result = check_service_health(service)
        service_results.append({
            "name": result["name"],
            "status": result["status"],
            "response_time_ms": result["response_time_ms"],
            "last_check": result["last_check"]
        })
        
        if result["status"] in ["healthy", "degraded"]:
            healthy_count += 1
    
    # Determine overall status
    total_services = len(config['services'])
    if healthy_count == total_services:
        overall_status = "healthy"
        status_code = 200
    elif healthy_count > 0:
        overall_status = "degraded"
        status_code = 503  # Bug: Should be 200 for degraded
    else:
        overall_status = "unhealthy"
        status_code = 503
    
    response_data = {
        "overall_status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "services": service_results,
        "total_services": total_services,
        "healthy_services": healthy_count
    }
    
    return jsonify(response_data), status_code

@app.route('/status')
def status():
    """Alternative status endpoint - not in requirements"""
    return jsonify({"message": "Health service is running"})

if __name__ == '__main__':
    # BUG: Using hardcoded port instead of config
    print(f"Starting health service on port 8080")
    app.run(host='0.0.0.0', port=8080, debug=True)
