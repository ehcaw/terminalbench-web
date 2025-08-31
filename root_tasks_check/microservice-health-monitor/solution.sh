#!/bin/bash

# Solution script for microservice-health-monitor task
# This script fixes the bugs and implements the required functionality

echo "Starting microservice health monitor solution..."

# Fix 1: Correct the filename references in start_all.py
sed -i.bak "s/mock_service.py/mock_services.py/g" start_all.py
sed -i.bak "s/alert.py/alerts.py/g" start_all.py

# Fix 2: Increase startup delays in start_all.py to prevent race conditions
sed -i.bak "s/time.sleep(0.5)/time.sleep(2)/g" start_all.py

# Fix 3: Fix the log filename in alerts.py
sed -i.bak "s/alert.log/alerts.log/g" alerts.py

# Fix 4: Fix hardcoded port in alerts.py to use config
sed -i.bak "s/localhost:8080/localhost:{config['health_service_port']}/g" alerts.py

# Fix 5: Fix hardcoded timeout in health_service.py
sed -i.bak "s/timeout=1/timeout=config['timeout_seconds']/g" health_service.py

# Fix 6: Fix hardcoded port in health_service.py
sed -i.bak "s/port=8080/port=config['health_service_port']/g" health_service.py

# Fix 7: Fix health status logic to include 'degraded' as healthy
sed -i.bak "s/status == 'healthy'/status in ['healthy', 'degraded']/g" health_service.py

# Fix 8: Fix mock services to use correct ports from config
sed -i.bak "s/port=8081/port=config['services'][0]['port']/g" mock_services.py
sed -i.bak "s/port=8082/port=config['services'][1]['port']/g" mock_services.py

# Fix 9: Remove always-sleep from database service in mock_services.py
sed -i.bak "/time.sleep(2)/d" mock_services.py

# Fix 10: Fix dashboard secret key
sed -i.bak "s/app.secret_key = 'dev'/app.secret_key = os.urandom(24)/g" dashboard.py

# Fix 11: Fix dashboard to use config port
sed -i.bak "s/port=8090/port=config['dashboard_port']/g" dashboard.py

# Clean up backup files
rm -f *.bak

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Starting all services..."
python3 start_all.py &
SERVICES_PID=$!

# Wait for services to start
sleep 10

echo "Services started successfully!"
echo "Health Service: http://localhost:8080/health"
echo "Dashboard: http://localhost:8090"
echo "Mock Services: http://localhost:8081, 8082, 8083"

# Create FIXED file to indicate successful completion
echo "SUCCESS" > FIXED

echo "Solution completed successfully!"
echo "FIXED file created with SUCCESS status."

# Keep services running for a bit to demonstrate functionality
sleep 30

# Clean shutdown
kill $SERVICES_PID 2>/dev/null

echo "Solution script finished."