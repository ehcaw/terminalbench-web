#!/usr/bin/env python3
"""
Mock Services - Simulates microservices for testing
Created by: Dev Team
Last modified: 2024
"""

from flask import Flask, jsonify
import threading
import time
import random

# Auth Service (Port 8081)
def create_auth_service():
    app = Flask('auth-service')
    
    @app.route('/health')
    def health():
        return jsonify({
            "status": "healthy",
            "service": "auth",
            "timestamp": time.time()
        })
    
    return app

# Database Service (Port 8082)
def create_database_service():
    app = Flask('database-service')
    
    @app.route('/health')
    def health():
        # BUG: Always sleeps, making it slow and potentially timing out
        time.sleep(1.2)
        
        return jsonify({
            "status": "degraded",
            "service": "database",
            "latency_ms": 150,
            "timestamp": time.time()
        })
    
    return app

# Cache Service (Port 8083)
def create_cache_service():
    app = Flask('cache-service')
    
    @app.route('/health')
    def health():
        # BUG: Fails 50% of the time instead of 30%
        if random.random() < 0.5:
            return jsonify({"error": "Service unavailable"}), 500
        
        # BUG: Inconsistent response format - missing 'service' field sometimes
        if random.random() < 0.3:
            return jsonify({
                "status": "healthy",
                "timestamp": time.time()
            })
        
        return jsonify({
            "status": "healthy",
            "service": "cache",
            "timestamp": time.time()
        })
    
    return app

def run_service(app, port):
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == '__main__':
    # Create services
    auth_app = create_auth_service()
    db_app = create_database_service()
    cache_app = create_cache_service()
    
    # Correct port assignments
    auth_thread = threading.Thread(target=run_service, args=(auth_app, 8081))
    db_thread = threading.Thread(target=run_service, args=(db_app, 8082))
    cache_thread = threading.Thread(target=run_service, args=(cache_app, 8083))
    
    auth_thread.daemon = True
    db_thread.daemon = True
    cache_thread.daemon = True
    
    print("Starting mock services...")
    print("Auth service: http://localhost:8081/health")
    print("Database service: http://localhost:8082/health")
    print("Cache service: http://localhost:8083/health")
    
    auth_thread.start()
    db_thread.start()
    cache_thread.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down mock services...")
