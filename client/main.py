from fastapi import FastAPI, Request, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os
import requests
import secrets
import json
from urllib.parse import urlencode
import pathlib
from datetime import datetime

# Create templates directory structure
base_dir = pathlib.Path(__file__).parent.resolve()
templates_dir = base_dir / "templates"
templates_dir.mkdir(exist_ok=True)

# Initialize FastAPI app
app = FastAPI(title="OAuth 2.0 Client Application")

# OAuth 2.0 configuration
AUTH_SERVER_BASE_URL = "http://localhost:5000"
CLIENT_ID = "client123"
CLIENT_SECRET = "secret123"
REDIRECT_URI = "http://localhost:5001/callback"
AUTHORIZATION_ENDPOINT = f"{AUTH_SERVER_BASE_URL}/authorize"
TOKEN_ENDPOINT = f"{AUTH_SERVER_BASE_URL}/token"
USERINFO_ENDPOINT = f"{AUTH_SERVER_BASE_URL}/userinfo"

# State management (in a real app, this would be persisted in a database or session)
STATES = {}
TOKENS = {}

# OAuth flow tracking
FLOW_LOGS = {}

# Function to log OAuth flow steps
def log_oauth_flow(session_id, step, details=None):
    if session_id not in FLOW_LOGS:
        FLOW_LOGS[session_id] = []
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = {
        "step": step,
        "timestamp": timestamp,
        "details": details or {}
    }
    FLOW_LOGS[session_id].append(log_entry)
    print(f"OAuth Flow [{session_id}]: {step} at {timestamp}")
    
    # Keep only the last 20 entries
    if len(FLOW_LOGS[session_id]) > 20:
        FLOW_LOGS[session_id] = FLOW_LOGS[session_id][-20:]
    
    return log_entry

# Templates
templates = Jinja2Templates(directory=str(templates_dir))

# Create home.html template
home_template_path = templates_dir / "home.html"
with open(home_template_path, "w") as f:
    f.write("""
<!DOCTYPE html>
<html>
<head>
    <title>OAuth 2.0 Client</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
        }
        .container {
            border: 1px solid #ddd;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        }
        h1, h2, h3 {
            color: #333;
        }
        .btn {
            background-color: #4CAF50;
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
            margin-top: 20px;
        }
        .info {
            margin-top: 20px;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 4px;
        }
        .user-info {
            margin-top: 20px;
            padding: 15px;
            background-color: #e9f7ef;
            border-radius: 4px;
        }
        pre {
            background-color: #f6f8fa;
            padding: 10px;
            border-radius: 5px;
            overflow-x: auto;
        }
        .flow-container {
            display: flex;
            margin-top: 20px;
        }
        .flow-steps {
            flex: 1;
            min-width: 200px;
            margin-right: 20px;
        }
        .flow-details {
            flex: 2;
        }
        .flow-step {
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 4px;
            background-color: #f1f8ff;
            position: relative;
        }
        .flow-step.completed {
            background-color: #e9f7ef;
            border-left: 4px solid #4CAF50;
        }
        .flow-step.current {
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
        }
        .flow-step.pending {
            background-color: #f8f9fa;
            border-left: 4px solid #6c757d;
            opacity: 0.7;
        }
        .step-number {
            display: inline-block;
            width: 25px;
            height: 25px;
            line-height: 25px;
            text-align: center;
            border-radius: 50%;
            background-color: #6c757d;
            color: white;
            margin-right: 10px;
        }
        .step-number.completed {
            background-color: #4CAF50;
        }
        .step-number.current {
            background-color: #ffc107;
            color: #333;
        }
        .flow-log {
            margin-top: 20px;
            max-height: 400px;
            overflow-y: auto;
        }
        .log-entry {
            padding: 10px;
            border-bottom: 1px solid #eee;
        }
        .log-entry:last-child {
            border-bottom: none;
        }
        .log-time {
            color: #6c757d;
            font-size: 0.9em;
            margin-right: 10px;
        }
        .two-columns {
            display: flex;
            gap: 20px;
        }
        .column {
            flex: 1;
        }
        .refresh-btn {
            background-color: #007bff;
            font-size: 0.9em;
            padding: 5px 10px;
            margin-left: 10px;
        }
    </style>
    <script>
        // Auto-refresh the flow logs every 3 seconds
        function setupAutoRefresh() {
            if (document.getElementById('flow-log')) {
                setInterval(() => {
                    fetch('/flow-status')
                        .then(response => response.json())
                        .then(data => {
                            const logContainer = document.getElementById('flow-log');
                            if (logContainer && data.logs && data.logs.length > 0) {
                                logContainer.innerHTML = '';
                                
                                data.logs.forEach(entry => {
                                    const logEntry = document.createElement('div');
                                    logEntry.className = 'log-entry';
                                    
                                    const timeSpan = document.createElement('span');
                                    timeSpan.className = 'log-time';
                                    timeSpan.textContent = entry.timestamp;
                                    
                                    logEntry.appendChild(timeSpan);
                                    logEntry.appendChild(document.createTextNode(entry.step));
                                    
                                    if (Object.keys(entry.details).length > 0) {
                                        const details = document.createElement('pre');
                                        details.textContent = JSON.stringify(entry.details, null, 2);
                                        logEntry.appendChild(details);
                                    }
                                    
                                    logContainer.appendChild(logEntry);
                                });
                                
                                // Update step indicators
                                updateStepIndicators(data.current_step);
                            }
                        });
                }, 3000);
            }
        }
        
        function updateStepIndicators(currentStep) {
            const steps = document.querySelectorAll('.flow-step');
            steps.forEach((step, index) => {
                const stepNum = step.getAttribute('data-step');
                const numElement = step.querySelector('.step-number');
                
                if (stepNum < currentStep) {
                    step.className = 'flow-step completed';
                    if (numElement) numElement.className = 'step-number completed';
                } else if (stepNum == currentStep) {
                    step.className = 'flow-step current';
                    if (numElement) numElement.className = 'step-number current';
                } else {
                    step.className = 'flow-step pending';
                    if (numElement) numElement.className = 'step-number';
                }
            });
        }
        
        function refreshFlow() {
            fetch('/flow-status')
                .then(response => response.json())
                .then(data => {
                    const logContainer = document.getElementById('flow-log');
                    if (logContainer) {
                        logContainer.innerHTML = '';
                        
                        if (data.logs && data.logs.length > 0) {
                            data.logs.forEach(entry => {
                                const logEntry = document.createElement('div');
                                logEntry.className = 'log-entry';
                                
                                const timeSpan = document.createElement('span');
                                timeSpan.className = 'log-time';
                                timeSpan.textContent = entry.timestamp;
                                
                                logEntry.appendChild(timeSpan);
                                logEntry.appendChild(document.createTextNode(entry.step));
                                
                                if (Object.keys(entry.details).length > 0) {
                                    const details = document.createElement('pre');
                                    details.textContent = JSON.stringify(entry.details, null, 2);
                                    logEntry.appendChild(details);
                                }
                                
                                logContainer.appendChild(logEntry);
                            });
                        } else {
                            logContainer.innerHTML = '<div class="log-entry">No OAuth flow logs yet. Start by clicking the Login button.</div>';
                        }
                        
                        // Update step indicators
                        updateStepIndicators(data.current_step);
                    }
                });
        }
        
        window.onload = function() {
            setupAutoRefresh();
            // Initial refresh
            refreshFlow();
        };
    </script>
</head>
<body>
    <div class="container">
        <h1>OAuth 2.0 Interactive Demo</h1>
        
        <div class="two-columns">
            <div class="column">
                {% if user %}
                    <div class="user-info">
                        <h2>You are logged in!</h2>
                        <p>Username: {{ user.username }}</p>
                        <p>Email: {{ user.email }}</p>
                        
                        {% if user.metadata %}
                        <div class="metadata">
                            <h3>User Metadata:</h3>
                            <ul>
                                {% if user.metadata.firstname %}
                                    <li><strong>First Name:</strong> {{ user.metadata.firstname }}</li>
                                {% endif %}
                                {% if user.metadata.lastname %}
                                    <li><strong>Last Name:</strong> {{ user.metadata.lastname }}</li>
                                {% endif %}
                                {% if user.metadata.role %}
                                    <li><strong>Role:</strong> {{ user.metadata.role }}</li>
                                {% endif %}
                                {% for key, value in user.metadata.items() %}
                                    {% if key not in ['firstname', 'lastname', 'role'] %}
                                        <li><strong>{{ key }}:</strong> {{ value }}</li>
                                    {% endif %}
                                {% endfor %}
                            </ul>
                        </div>
                        {% endif %}
                        
                        <a href="/logout" class="btn">Logout</a>
                        <a href="/protected" class="btn">View Protected Resource</a>
                    </div>
                {% else %}
                    <div class="info">
                        <h2>Welcome to OAuth 2.0 Demo</h2>
                        <p>This is a demonstration of the OAuth 2.0 Authorization Code flow.</p>
                        <p>Click the button below to start the OAuth flow and log in.</p>
                        <a href="/login" class="btn">Login with OAuth</a>
                    </div>
                {% endif %}
            </div>
            
            <div class="column">
                <div class="info">
                    <h2>OAuth 2.0 Flow Visualization</h2>
                    <p>Watch the OAuth 2.0 flow happen in real-time as you proceed through authentication.</p>
                    <button onclick="refreshFlow()" class="btn refresh-btn">Refresh Flow</button>
                </div>
            </div>
        </div>
        
        <div class="flow-container">
            <div class="flow-steps">
                <h3>OAuth 2.0 Steps</h3>
                <div class="flow-step" data-step="1">
                    <span class="step-number">1</span>
                    <strong>Client Authorization Request</strong>
                    <p>Client requests authorization from the user</p>
                </div>
                <div class="flow-step" data-step="2">
                    <span class="step-number">2</span>
                    <strong>User Authentication</strong>
                    <p>User logs in at the authorization server</p>
                </div>
                <div class="flow-step" data-step="3">
                    <span class="step-number">3</span>
                    <strong>User Consent</strong>
                    <p>User approves the requested permissions</p>
                </div>
                <div class="flow-step" data-step="4">
                    <span class="step-number">4</span>
                    <strong>Authorization Code Grant</strong>
                    <p>Server redirects back with an authorization code</p>
                </div>
                <div class="flow-step" data-step="5">
                    <span class="step-number">5</span>
                    <strong>Token Exchange</strong>
                    <p>Client exchanges the code for an access token</p>
                </div>
                <div class="flow-step" data-step="6">
                    <span class="step-number">6</span>
                    <strong>Resource Access</strong>
                    <p>Client uses the token to access protected resources</p>
                </div>
            </div>
            
            <div class="flow-details">
                <h3>OAuth Flow Log <button onclick="refreshFlow()" class="btn refresh-btn">Refresh</button></h3>
                <div id="flow-log" class="flow-log">
                    <div class="log-entry">Loading OAuth flow logs...</div>
                </div>
            </div>
        </div>
        
        {% if token %}
            <div class="info">
                <h2>Access Token</h2>
                <pre>{{ token | tojson(indent=2) }}</pre>
            </div>
        {% endif %}
    </div>
</body>
</html>
""")

# Create error.html template
error_template_path = templates_dir / "error.html"
with open(error_template_path, "w") as f:
    f.write("""
<!DOCTYPE html>
<html>
<head>
    <title>OAuth 2.0 Client - Error</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 500px;
            margin: 0 auto;
            padding: 20px;
        }
        .container {
            border: 1px solid #ddd;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        }
        h1 {
            color: #333;
        }
        .error {
            color: red;
            background-color: #ffebee;
            padding: 10px;
            border-radius: 4px;
            margin-bottom: 20px;
        }
        .btn {
            background-color: #4CAF50;
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Error</h1>
        <div class="error">{{ error }}</div>
        <a href="/" class="btn">Back to Home</a>
    </div>
</body>
</html>
""")

# Create protected.html template
protected_template_path = templates_dir / "protected.html"
with open(protected_template_path, "w") as f:
    f.write("""
<!DOCTYPE html>
<html>
<head>
    <title>Protected Page</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
        }
        .container {
            border: 1px solid #ddd;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        }
        h1, h2, h3 {
            color: #333;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .user-info {
            background-color: #e9f7ef;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .scopes {
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .scope-item {
            display: inline-block;
            background-color: #4CAF50;
            color: white;
            padding: 5px 10px;
            border-radius: 15px;
            margin-right: 5px;
            margin-bottom: 5px;
        }
        .token-info {
            background-color: #f1f8ff;
            padding: 15px;
            border-radius: 5px;
        }
        pre {
            background-color: #f6f8fa;
            padding: 10px;
            border-radius: 5px;
            overflow-x: auto;
        }
        .btn {
            background-color: #4CAF50;
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            text-decoration: none;
        }
        .logout-btn {
            background-color: #f44336;
        }
        .flow-container {
            display: flex;
            margin-top: 20px;
        }
        .flow-steps {
            flex: 1;
            min-width: 200px;
            margin-right: 20px;
        }
        .flow-details {
            flex: 2;
        }
        .flow-step {
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 4px;
            background-color: #f1f8ff;
            position: relative;
        }
        .flow-step.completed {
            background-color: #e9f7ef;
            border-left: 4px solid #4CAF50;
        }
        .flow-step.current {
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
        }
        .flow-step.pending {
            background-color: #f8f9fa;
            border-left: 4px solid #6c757d;
            opacity: 0.7;
        }
        .step-number {
            display: inline-block;
            width: 25px;
            height: 25px;
            line-height: 25px;
            text-align: center;
            border-radius: 50%;
            background-color: #6c757d;
            color: white;
            margin-right: 10px;
        }
        .step-number.completed {
            background-color: #4CAF50;
        }
        .step-number.current {
            background-color: #ffc107;
            color: #333;
        }
        .flow-log {
            margin-top: 20px;
            max-height: 400px;
            overflow-y: auto;
        }
        .log-entry {
            padding: 10px;
            border-bottom: 1px solid #eee;
        }
        .log-entry:last-child {
            border-bottom: none;
        }
        .log-time {
            color: #6c757d;
            font-size: 0.9em;
            margin-right: 10px;
        }
        .refresh-btn {
            background-color: #007bff;
            font-size: 0.9em;
            padding: 5px 10px;
            margin-left: 10px;
        }
        .two-columns {
            display: flex;
            gap: 20px;
        }
        .column {
            flex: 1;
        }
        .metadata {
            background-color: #e6f7ff;
            padding: 12px;
            margin-top: 15px;
            border-radius: 5px;
            border-left: 4px solid #1890ff;
        }
        .metadata h3 {
            color: #1890ff;
            margin-top: 0;
            margin-bottom: 10px;
        }
        .metadata ul {
            list-style-type: none;
            padding-left: 0;
            margin-bottom: 0;
        }
        .metadata li {
            padding: 5px 0;
            border-bottom: 1px solid #eee;
        }
        .metadata li:last-child {
            border-bottom: none;
        }
    </style>
    <script>
        // Auto-refresh the flow logs every 3 seconds
        function setupAutoRefresh() {
            if (document.getElementById('flow-log')) {
                setInterval(() => {
                    fetch('/flow-status')
                        .then(response => response.json())
                        .then(data => {
                            const logContainer = document.getElementById('flow-log');
                            if (logContainer && data.logs && data.logs.length > 0) {
                                logContainer.innerHTML = '';
                                
                                data.logs.forEach(entry => {
                                    const logEntry = document.createElement('div');
                                    logEntry.className = 'log-entry';
                                    
                                    const timeSpan = document.createElement('span');
                                    timeSpan.className = 'log-time';
                                    timeSpan.textContent = entry.timestamp;
                                    
                                    logEntry.appendChild(timeSpan);
                                    logEntry.appendChild(document.createTextNode(entry.step));
                                    
                                    if (Object.keys(entry.details).length > 0) {
                                        const details = document.createElement('pre');
                                        details.textContent = JSON.stringify(entry.details, null, 2);
                                        logEntry.appendChild(details);
                                    }
                                    
                                    logContainer.appendChild(logEntry);
                                });
                                
                                // Update step indicators
                                updateStepIndicators(data.current_step);
                            }
                        });
                }, 3000);
            }
        }
        
        function updateStepIndicators(currentStep) {
            const steps = document.querySelectorAll('.flow-step');
            steps.forEach((step, index) => {
                const stepNum = step.getAttribute('data-step');
                const numElement = step.querySelector('.step-number');
                
                if (stepNum < currentStep) {
                    step.className = 'flow-step completed';
                    if (numElement) numElement.className = 'step-number completed';
                } else if (stepNum == currentStep) {
                    step.className = 'flow-step current';
                    if (numElement) numElement.className = 'step-number current';
                } else {
                    step.className = 'flow-step pending';
                    if (numElement) numElement.className = 'step-number';
                }
            });
        }
        
        function refreshFlow() {
            fetch('/flow-status')
                .then(response => response.json())
                .then(data => {
                    const logContainer = document.getElementById('flow-log');
                    if (logContainer) {
                        logContainer.innerHTML = '';
                        
                        if (data.logs && data.logs.length > 0) {
                            data.logs.forEach(entry => {
                                const logEntry = document.createElement('div');
                                logEntry.className = 'log-entry';
                                
                                const timeSpan = document.createElement('span');
                                timeSpan.className = 'log-time';
                                timeSpan.textContent = entry.timestamp;
                                
                                logEntry.appendChild(timeSpan);
                                logEntry.appendChild(document.createTextNode(entry.step));
                                
                                if (Object.keys(entry.details).length > 0) {
                                    const details = document.createElement('pre');
                                    details.textContent = JSON.stringify(entry.details, null, 2);
                                    logEntry.appendChild(details);
                                }
                                
                                logContainer.appendChild(logEntry);
                            });
                        } else {
                            logContainer.innerHTML = '<div class="log-entry">No OAuth flow logs yet.</div>';
                        }
                        
                        // Update step indicators
                        updateStepIndicators(data.current_step);
                    }
                });
        }
        
        window.onload = function() {
            setupAutoRefresh();
            // Initial refresh
            refreshFlow();
        };
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Protected Resource</h1>
            <div>
                <a href="/" class="btn">Home</a>
                <a href="/logout" class="btn logout-btn">Logout</a>
            </div>
        </div>
        
        <div class="user-info">
            <h2>Hi, {{ user.username }}!</h2>
            <p>Email: {{ user.email }}</p>
            
            {% if user.metadata %}
            <div class="metadata">
                <h3>User Metadata:</h3>
                <ul>
                    {% if user.metadata.firstname %}
                        <li><strong>First Name:</strong> {{ user.metadata.firstname }}</li>
                    {% endif %}
                    {% if user.metadata.lastname %}
                        <li><strong>Last Name:</strong> {{ user.metadata.lastname }}</li>
                    {% endif %}
                    {% if user.metadata.role %}
                        <li><strong>Role:</strong> {{ user.metadata.role }}</li>
                    {% endif %}
                    {% for key, value in user.metadata.items() %}
                        {% if key not in ['firstname', 'lastname', 'role'] %}
                            <li><strong>{{ key }}:</strong> {{ value }}</li>
                        {% endif %}
                    {% endfor %}
                </ul>
            </div>
            {% endif %}
        </div>
        
        <div class="scopes">
            <h2>Authorized Scopes:</h2>
            {% if scopes %}
                {% for scope in scopes %}
                    <div class="scope-item">{{ scope }}</div>
                {% endfor %}
            {% else %}
                <p>No scopes were authorized.</p>
            {% endif %}
        </div>
        
        <h2>OAuth 2.0 Flow Completed Successfully!</h2>
        
        <div class="flow-container">
            <div class="flow-steps">
                <h3>OAuth 2.0 Steps</h3>
                <div class="flow-step completed" data-step="1">
                    <span class="step-number completed">1</span>
                    <strong>Client Authorization Request</strong>
                    <p>Client requests authorization from the user</p>
                </div>
                <div class="flow-step completed" data-step="2">
                    <span class="step-number completed">2</span>
                    <strong>User Authentication</strong>
                    <p>User logs in at the authorization server</p>
                </div>
                <div class="flow-step completed" data-step="3">
                    <span class="step-number completed">3</span>
                    <strong>User Consent</strong>
                    <p>User approves the requested permissions</p>
                </div>
                <div class="flow-step completed" data-step="4">
                    <span class="step-number completed">4</span>
                    <strong>Authorization Code Grant</strong>
                    <p>Server redirects back with an authorization code</p>
                </div>
                <div class="flow-step completed" data-step="5">
                    <span class="step-number completed">5</span>
                    <strong>Token Exchange</strong>
                    <p>Client exchanges the code for an access token</p>
                </div>
                <div class="flow-step completed" data-step="6">
                    <span class="step-number completed">6</span>
                    <strong>Resource Access</strong>
                    <p>Client uses the token to access protected resources</p>
                </div>
            </div>
            
            <div class="flow-details">
                <h3>OAuth Flow Log <button onclick="refreshFlow()" class="btn refresh-btn">Refresh</button></h3>
                <div id="flow-log" class="flow-log">
                    <div class="log-entry">Loading OAuth flow logs...</div>
                </div>
            </div>
        </div>
        
        <div class="token-info">
            <h2>Access Token Information:</h2>
            <pre>{{ token | tojson(indent=2) }}</pre>
        </div>
    </div>
</body>
</html>
""")

# Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Get cookie
    session_id = request.cookies.get("session_id")
    if not session_id:
        # Create a new session ID
        session_id = secrets.token_urlsafe(16)
        response = templates.TemplateResponse(
            "home.html", 
            {
                "request": request,
                "user": None,
                "token": None
            }
        )
        response.set_cookie(key="session_id", value=session_id, httponly=True)
        log_oauth_flow(session_id, "Session Initialized", {"new_session": True})
        return response
    
    token = None
    user = None
    
    # Check if the user has an access token
    if session_id in TOKENS:
        token = TOKENS[session_id]
        
        # Get user info using the access token
        try:
            user_response = requests.get(
                USERINFO_ENDPOINT,
                headers={"Authorization": f"Bearer {token['access_token']}"}
            )
            
            if user_response.status_code == 200:
                user = user_response.json()
                log_oauth_flow(session_id, "Resource Access - User Information Retrieved", {
                    "status": user_response.status_code,
                    "user": user
                })
            else:
                # Token might be expired or invalid, clear it
                log_oauth_flow(session_id, "Resource Access Failed - Invalid Token", {
                    "status": user_response.status_code,
                    "error": user_response.text
                })
                TOKENS.pop(session_id, None)
        except Exception as e:
            # Token might be expired or invalid, clear it
            log_oauth_flow(session_id, "Resource Access Failed - Exception", {
                "error": str(e)
            })
            TOKENS.pop(session_id, None)
    
    return templates.TemplateResponse(
        "home.html", 
        {
            "request": request,
            "user": user,
            "token": token
        }
    )

@app.get("/login")
async def login(request: Request):
    # Generate a random state
    state = secrets.token_urlsafe(32)
    
    # Get or create a session ID
    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = secrets.token_urlsafe(16)
    
    # Store the state and session_id
    STATES[state] = {"session_id": session_id}
    
    # Define scopes to request
    requested_scopes = "profile email metadata"
    
    # Log the authorization request
    log_oauth_flow(session_id, "Authorization Request Initiated", {
        "state": state, 
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": requested_scopes
    })
    
    # Redirect to the authorization endpoint
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": requested_scopes,
        "state": state
    }
    
    authorization_url = f"{AUTHORIZATION_ENDPOINT}?{urlencode(params)}"
    response = RedirectResponse(url=authorization_url)
    
    # Set a cookie with the session ID
    response.set_cookie(key="session_id", value=session_id, httponly=True)
    
    return response

@app.get("/callback")
async def callback(request: Request):
    # Get query parameters directly from request
    params = dict(request.query_params)
    code = params.get("code")
    state = params.get("state")
    error = params.get("error")
    
    # Debug the raw request information
    print(f"Callback raw query params: {params}")
    
    return await handle_callback(request, code, state, error)

@app.post("/callback")
async def callback_post(request: Request):
    # For POST requests, get form data
    form = await request.form()
    code = form.get("code")
    state = form.get("state")
    error = form.get("error")
    
    # If not in form, try query parameters
    if not code and "code" in request.query_params:
        code = request.query_params.get("code")
    if not state and "state" in request.query_params:
        state = request.query_params.get("state")
    if not error and "error" in request.query_params:
        error = request.query_params.get("error")
    
    print(f"Callback POST params: form={dict(form)}, query={dict(request.query_params)}")
    
    return await handle_callback(request, code, state, error)

async def handle_callback(request: Request, code: str = None, state: str = None, error: str = None):
    # Check if there's an error
    if error:
        # Log the error
        session_id = request.cookies.get("session_id", "unknown")
        log_oauth_flow(session_id, "Authorization Error", {
            "error": error,
            "state": state
        })
        
        return templates.TemplateResponse(
            "error.html", 
            {
                "request": request,
                "error": f"Authorization error: {error}"
            }
        )
    
    # For debugging: log received data
    print(f"Received code in handle_callback: {code}")
    print(f"Received state in handle_callback: {state}")
    print(f"Available states: {list(STATES.keys())}")
    
    # Validate code
    if not code:
        # Log the error
        session_id = request.cookies.get("session_id", "unknown")
        log_oauth_flow(session_id, "Missing Authorization Code", {
            "state": state
        })
        
        return templates.TemplateResponse(
            "error.html", 
            {
                "request": request,
                "error": "Missing authorization code in callback"
            }
        )
    
    # Validate state - more lenient checking
    if not state:
        # Log the error
        session_id = request.cookies.get("session_id", "unknown")
        log_oauth_flow(session_id, "Missing State Parameter", {
            "code": code
        })
        
        return templates.TemplateResponse(
            "error.html", 
            {
                "request": request,
                "error": "Missing state parameter"
            }
        )
    
    # If the state is not in STATES, try to get the session ID from the cookie
    if state not in STATES:
        session_id = request.cookies.get("session_id")
        if not session_id:
            return templates.TemplateResponse(
                "error.html", 
                {
                    "request": request,
                    "error": "Invalid state parameter. Using fallback session."
                }
            )
    else:
        # Get the session ID from the state
        session_data = STATES.pop(state)
        session_id = session_data["session_id"]
    
    # Log the authorization code received
    log_oauth_flow(session_id, "Authorization Code Received", {
        "code": code[:10] + "..." if code else None,
        "state": state
    })
    
    # Exchange the authorization code for an access token
    try:
        # Debug the token request
        print(f"Sending token request with code: {code}")
        
        # Simple token request with minimal parameters
        token_data = {
            "grant_type": "authorization_code",  # Using standard OAuth flow
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "redirect_uri": REDIRECT_URI
        }
        
        # Log token exchange
        log_oauth_flow(session_id, "Token Exchange - Request Sent", {
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "code": code[:10] + "..." if code else None
        })
        
        print(f"Token request data: {token_data}")
        
        # Make the token request
        token_response = requests.post(
            TOKEN_ENDPOINT,
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        # Debug response
        print(f"Token response status: {token_response.status_code}")
        print(f"Token response content: {token_response.content}")
        
        # Check if the token request was successful
        if token_response.status_code != 200:
            try:
                error_data = token_response.json()
                error_message = error_data.get('error', 'Unknown error')
                
                # Log token exchange failure
                log_oauth_flow(session_id, "Token Exchange Failed", {
                    "status": token_response.status_code,
                    "error": error_message
                })
            except:
                error_message = f"Status code: {token_response.status_code}, Content: {token_response.content}"
                
                # Log token exchange failure
                log_oauth_flow(session_id, "Token Exchange Failed - Parse Error", {
                    "status": token_response.status_code,
                    "content": token_response.content.decode('utf-8', errors='ignore')
                })
                
            return templates.TemplateResponse(
                "error.html", 
                {
                    "request": request,
                    "error": f"Token request failed: {error_message}"
                }
            )
        
        # Store the token
        token_data = token_response.json()
        TOKENS[session_id] = token_data
        
        # Log token exchange success
        log_oauth_flow(session_id, "Token Exchange Successful", {
            "token_type": token_data.get("token_type"),
            "expires_in": token_data.get("expires_in"),
            "scope": token_data.get("scope")
        })
        
        # Redirect to the protected page with explicit GET method
        return RedirectResponse(url="/protected", status_code=303)
    
    except Exception as e:
        print(f"Exception during token exchange: {str(e)}")
        
        # Log exception
        log_oauth_flow(session_id, "Token Exchange Exception", {
            "error": str(e)
        })
        
        return templates.TemplateResponse(
            "error.html", 
            {
                "request": request,
                "error": f"Token request failed: {str(e)}"
            }
        )

@app.get("/logout")
async def logout(request: Request):
    # Get cookie
    session_id = request.cookies.get("session_id")
    
    if session_id:
        # Log logout
        log_oauth_flow(session_id, "User Logged Out", {
            "session_terminated": True
        })
        
        # Remove token
        if session_id in TOKENS:
            TOKENS.pop(session_id)
    
    # Redirect to the home page
    response = RedirectResponse(url="/")
    
    # Clear the cookie
    response.delete_cookie(key="session_id")
    
    return response

@app.get("/protected", response_class=HTMLResponse)
async def protected(request: Request):
    # Get cookie
    session_id = request.cookies.get("session_id")
    
    # Check if the user has an access token
    if not session_id or session_id not in TOKENS:
        # Log unauthorized access attempt
        if session_id:
            log_oauth_flow(session_id, "Protected Resource Access - Unauthorized", {
                "error": "No valid token found"
            })
        
        # Redirect to login if not authenticated
        return RedirectResponse(url="/")
    
    token = TOKENS[session_id]
    
    # Get user info using the access token
    try:
        # Log resource access attempt
        log_oauth_flow(session_id, "Resource Access - Requesting User Info", {
            "endpoint": USERINFO_ENDPOINT
        })
        
        user_response = requests.get(
            USERINFO_ENDPOINT,
            headers={"Authorization": f"Bearer {token['access_token']}"}
        )
        
        if user_response.status_code != 200:
            # Log resource access failure
            log_oauth_flow(session_id, "Resource Access Failed", {
                "status": user_response.status_code,
                "error": user_response.text
            })
            
            # Token might be invalid, redirect to login
            TOKENS.pop(session_id, None)
            return RedirectResponse(url="/")
        
        user = user_response.json()
        scopes = token.get('scope', '').split() if token.get('scope') else []
        
        # Log successful resource access
        log_oauth_flow(session_id, "Resource Access Successful", {
            "user": user,
            "scopes": scopes
        })
        
        return templates.TemplateResponse(
            "protected.html", 
            {
                "request": request,
                "user": user,
                "scopes": scopes,
                "token": token
            }
        )
    except Exception as e:
        # Log resource access exception
        log_oauth_flow(session_id, "Resource Access Exception", {
            "error": str(e)
        })
        
        # Handle error, redirect to home
        print(f"Error accessing protected resource: {str(e)}")
        return RedirectResponse(url="/")

@app.get("/flow-status")
async def flow_status(request: Request):
    """
    Get the current status of the OAuth flow for this session
    """
    session_id = request.cookies.get("session_id")
    if not session_id:
        return {"logs": [], "current_step": 0}
    
    # Get flow logs for this session
    logs = FLOW_LOGS.get(session_id, [])
    
    # Determine current step
    current_step = 0
    for log in logs:
        step_num = 0
        if "Authorization Request Initiated" in log["step"]:
            step_num = 1
        elif "User Authentication" in log["step"]:
            step_num = 2
        elif "User Consent" in log["step"]:
            step_num = 3
        elif "Authorization Code Received" in log["step"]:
            step_num = 4
        elif "Token Exchange" in log["step"]:
            step_num = 5
        elif "Resource Access" in log["step"]:
            step_num = 6
        
        if step_num > current_step:
            current_step = step_num
    
    return {"logs": logs, "current_step": current_step}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001) 