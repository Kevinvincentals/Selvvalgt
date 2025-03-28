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
            max-width: 800px;
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
    </style>
</head>
<body>
    <div class="container">
        <h1>OAuth 2.0 Demo Client</h1>
        {% if user %}
            <div class="user-info">
                <h2>You are logged in!</h2>
                <p>Username: {{ user.username }}</p>
                <p>Email: {{ user.email }}</p>
            </div>
            <a href="/logout" class="btn">Logout</a>
        {% else %}
            <p>This is a demonstration of the OAuth 2.0 Authorization Code flow.</p>
            <p>Click the button below to log in with the OAuth 2.0 server.</p>
            <a href="/login" class="btn">Login with OAuth</a>
        {% endif %}
        
        <div class="info">
            <h2>OAuth 2.0 Flow</h2>
            <p>This example demonstrates the OAuth 2.0 Authorization Code grant type:</p>
            <ol>
                <li>Client requests authorization from the user</li>
                <li>User authenticates and approves the authorization</li>
                <li>Authorization server sends an authorization code to the client</li>
                <li>Client exchanges the code for an access token</li>
                <li>Client uses the access token to access protected resources</li>
            </ol>
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
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        .container {
            border: 1px solid #ddd;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        }
        h1, h2 {
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
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Protected Resource</h1>
            <a href="/logout" class="btn logout-btn">Logout</a>
        </div>
        
        <div class="user-info">
            <h2>Hi, {{ user.username }}!</h2>
            <p>Email: {{ user.email }}</p>
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
        
        <div class="token-info">
            <h2>Access Token Information:</h2>
            <pre>{{ token | tojson(indent=2) }}</pre>
        </div>
        
        <p style="margin-top: 20px;">
            <a href="/" class="btn">Back to Home</a>
        </p>
    </div>
</body>
</html>
""")

# Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Get cookie
    session_id = request.cookies.get("session_id")
    token = None
    user = None
    
    # Check if the user has an access token
    if session_id and session_id in TOKENS:
        token = TOKENS[session_id]
        
        # Get user info using the access token
        try:
            user_response = requests.get(
                USERINFO_ENDPOINT,
                headers={"Authorization": f"Bearer {token['access_token']}"}
            )
            if user_response.status_code == 200:
                user = user_response.json()
        except Exception as e:
            # Token might be expired or invalid, clear it
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
    
    # Print for debugging
    print(f"Created new state: {state}")
    print(f"Associated with session: {session_id}")
    
    # Redirect to the authorization endpoint
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "profile email",
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
        return templates.TemplateResponse(
            "error.html", 
            {
                "request": request,
                "error": "Missing authorization code in callback"
            }
        )
    
    # Validate state - more lenient checking
    if not state:
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
            except:
                error_message = f"Status code: {token_response.status_code}, Content: {token_response.content}"
                
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
        
        # Redirect to the protected page with explicit GET method
        return RedirectResponse(url="/protected", status_code=303)
    
    except Exception as e:
        print(f"Exception during token exchange: {str(e)}")
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
    
    # Remove token
    if session_id and session_id in TOKENS:
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
        # Redirect to login if not authenticated
        return RedirectResponse(url="/")
    
    token = TOKENS[session_id]
    
    # Get user info using the access token
    try:
        user_response = requests.get(
            USERINFO_ENDPOINT,
            headers={"Authorization": f"Bearer {token['access_token']}"}
        )
        
        if user_response.status_code != 200:
            # Token might be invalid, redirect to login
            TOKENS.pop(session_id, None)
            return RedirectResponse(url="/")
        
        user = user_response.json()
        scopes = token.get('scope', '').split() if token.get('scope') else []
        
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
        # Handle error, redirect to home
        print(f"Error accessing protected resource: {str(e)}")
        return RedirectResponse(url="/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001) 