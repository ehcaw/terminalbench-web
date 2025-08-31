#!/usr/bin/env python3
"""
Health Dashboard - Web interface for monitoring services
Developed by: Team Alpha
Status: In Development
"""

from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify, Response
import requests
import json
from datetime import datetime

app = Flask(__name__)
# BUG: Weak secret key that's easily guessable
app.secret_key = 'secret'

def load_config():
    """Load configuration from config.json"""
    with open('config.json', 'r') as f:
        return json.load(f)

# Load configuration
config = load_config()

# HTML Templates
LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Health Monitor - Login</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }
        .login-container { max-width: 400px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="text"], input[type="password"] { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        .btn { background-color: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; width: 100%; }
        .btn:hover { background-color: #0056b3; }
        .error { color: red; margin-top: 10px; }
        h2 { text-align: center; color: #333; }
    </style>
</head>
<body>
    <div class="login-container">
        <h2>Health Monitor Login</h2>
        <form method="POST">
            <div class="form-group">
                <label for="username">Username:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit" class="btn">Login</button>
            {% if error %}
                <div class="error">{{ error }}</div>
            {% endif %}
        </form>
    </div>
</body>
</html>
'''

DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Health Monitor Dashboard</title>
    <meta http-equiv="refresh" content="5">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        .header { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .services-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .service-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .status-healthy { border-left: 5px solid #28a745; }
        .status-degraded { border-left: 5px solid #ffc107; }
        .status-down { border-left: 5px solid #dc3545; }
        .status-unknown { border-left: 5px solid #6c757d; }
        .service-name { font-size: 18px; font-weight: bold; margin-bottom: 10px; }
        .service-status { font-size: 16px; margin-bottom: 5px; }
        .service-time { font-size: 12px; color: #666; }
        .overall-status { font-size: 24px; font-weight: bold; text-align: center; }
        .logout { float: right; }
        .logout a { color: #007bff; text-decoration: none; }
        .logout a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="header">
        <div class="logout">
            <a href="{{ url_for('logout') }}">Logout</a>
        </div>
        <h1>Microservice Health Monitor</h1>
        <div class="overall-status">Overall Status: {{ overall_status }}</div>
        <p>Last Updated: {{ timestamp }}</p>
        <p>Services: {{ healthy_services }}/{{ total_services }} healthy</p>
    </div>
    
    <div class="services-grid">
        {% for service in services %}
        <div class="service-card status-{{ service.status }}">
            <div class="service-name">{{ service.name|title }}</div>
            <div class="service-status">Status: {{ service.status|title }}</div>
            <div class="service-time">Last Check: {{ service.last_check }}</div>
        </div>
        {% endfor %}
    </div>
</body>
</html>
'''



@app.route('/')
def dashboard():
    # Check authentication
    auth = request.authorization
    config = load_config()
    
    if not auth or auth.username != config['auth']['username'] or auth.password != config['auth']['password']:
        return Response('Authentication required', 401, {'WWW-Authenticate': 'Basic realm="Dashboard"'})
    
    try:
        # Get health data from health service
        health_response = requests.get(f'http://localhost:{config["health_service_port"]}/health')
        health_data = health_response.json()
        
        return render_template_string(DASHBOARD_TEMPLATE, health_data=health_data)
    except Exception as e:
        return f'Error fetching health data: {str(e)}', 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # BUG: Hardcoded credentials instead of using config
        if username == 'admin' and password == 'monitor123':
            # BUG: Wrong session key - should be 'logged_in' but uses 'user'
            session['user'] = username
            return redirect(url_for('dashboard'))
        else:
            return render_template_string(LOGIN_TEMPLATE, error="Invalid credentials")
    
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    # BUG: Wrong session key to clear
    session.pop('user', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    # BUG: Using hardcoded port instead of config
    app.run(host='0.0.0.0', port=8090, debug=True)
