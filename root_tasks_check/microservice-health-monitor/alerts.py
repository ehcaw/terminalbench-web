import time
import requests
import json
from datetime import datetime

def load_config():
    with open('config.json', 'r') as f:
        return json.load(f)

def check_service_health(name, port):
    try:
        response = requests.get(f'http://localhost:{port}/health', timeout=5)
        if response.status_code == 200:
            return 'healthy'
        else:
            return 'unhealthy'
    except:
        return 'unhealthy'

def log_alert(message):
    timestamp = datetime.now().isoformat()
    with open('alerts.log', 'a') as f:
        f.write(f'[{timestamp}] {message}\n')

def monitor_services():
    config = load_config()
    
    while True:
        # Use config port
        health_response = requests.get(f'http://localhost:{config["health_service_port"]}/health')
        
        for service in config['services']:
            status = check_service_health(service['name'], service['port'])
            # Bug: Also alerting on degraded services (should only alert on unhealthy)
            if status != 'healthy':
                log_alert(f'ALERT: Service {service["name"]} is {status}')
        
        time.sleep(10)  # Correct interval

if __name__ == '__main__':
    monitor_services()
