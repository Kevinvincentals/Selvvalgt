from fastapi import FastAPI, Depends, HTTPException, status, Form, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from pydantic import BaseModel
import os
import secrets
from fastapi.templating import Jinja2Templates
import json
import pathlib

# Create templates directory structure
base_dir = pathlib.Path(__file__).parent.resolve()
templates_dir = base_dir / "templates"
templates_dir.mkdir(exist_ok=True)

# Initialize FastAPI app
app = FastAPI(title="OAuth 2.0 Authorization Server")

# Mock user database (in a real app, this would be in a proper database)
USERS_DB = {
    "user": {
        "username": "user",
        "password": "password",  # In a real app, this would be hashed
        "email": "user@example.com",
        "metadata": {
            "firstname": "Lars",
            "lastname": "Jensen",
            "role": "admin"
        },
        "disabled": False,
    }
}

# Client application information
CLIENT_ID = "client123"
CLIENT_SECRET = "secret123"
REDIRECT_URIS = ["http://localhost:5001/callback"]

# Authorization code store
AUTH_CODES: Dict[str, Dict] = {}

# Token store
TOKENS: Dict[str, Dict] = {}

# JWT settings
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"  # In a real app, generate this securely
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# CORS settings
origins = [
    "http://localhost:5001",  # Client application
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Templates
templates = Jinja2Templates(directory=str(templates_dir))

# Models
class User(BaseModel):
    username: str
    email: Optional[str] = None
    disabled: Optional[bool] = None

class UserInDB(User):
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class AuthorizeRequest(BaseModel):
    response_type: str
    client_id: str
    redirect_uri: Optional[str] = None
    scope: Optional[str] = None
    state: Optional[str] = None

class TokenRequest(BaseModel):
    grant_type: str
    code: Optional[str] = None
    redirect_uri: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None

# Authentication functions
def verify_password(plain_password, password):
    return plain_password == password  # In a real app, use proper password hashing

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)
    return None

def authenticate_user(username: str, password: str):
    user = get_user(USERS_DB, username)
    if not user:
        return False
    if not verify_password(password, user.password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def generate_auth_code():
    return secrets.token_urlsafe(32)

# Create login.html template
login_template_path = templates_dir / "login.html"
with open(login_template_path, "w") as f:
    f.write("""
<!DOCTYPE html>
<html>
<head>
    <title>OAuth 2.0 Login</title>
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
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
        }
        input[type="text"], input[type="password"] {
            width: 100%;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        button {
            background-color: #4CAF50;
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        .error {
            color: red;
            margin-bottom: 15px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Login to Authorize</h1>
        <p>The application <strong>{{ client_id }}</strong> is requesting access to your account.</p>
        
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        
        <form method="post">
            <input type="hidden" name="client_id" value="{{ client_id }}">
            <input type="hidden" name="redirect_uri" value="{{ redirect_uri }}">
            <input type="hidden" name="state" value="{{ state }}">
            <input type="hidden" name="scope" value="{{ scope }}">
            
            <div class="form-group">
                <label for="username">Username:</label>
                <input type="text" id="username" name="username" required>
            </div>
            
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            
            <button type="submit">Authorize</button>
        </form>
    </div>
</body>
</html>
""")

# Create consent.html template
consent_template_path = templates_dir / "consent.html"
with open(consent_template_path, "w") as f:
    f.write("""
<!DOCTYPE html>
<html>
<head>
    <title>OAuth 2.0 Consent</title>
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
        .scopes {
            margin: 20px 0;
        }
        .scope-item {
            margin-bottom: 15px;
            padding: 10px;
            background-color: #f8f9fa;
            border-radius: 4px;
            border-left: 3px solid #1890ff;
        }
        .scope-name {
            font-weight: bold;
            margin-bottom: 5px;
        }
        .scope-description {
            color: #666;
            font-size: 0.9em;
        }
        .buttons {
            display: flex;
            justify-content: space-between;
            margin-top: 30px;
        }
        .allow-btn {
            background-color: #4CAF50;
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        .deny-btn {
            background-color: #f44336;
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Authorization Request</h1>
        <p>The application <strong>{{ client_id }}</strong> is requesting access to your account.</p>
        
        <div class="scopes">
            <h3>The application is requesting:</h3>
            {% for scope in scopes %}
            <div class="scope-item">
                <div class="scope-name">{{ scope.name }}</div>
                <div class="scope-description">{{ scope.description }}</div>
            </div>
            {% endfor %}
        </div>
        
        <div class="buttons">
            <form method="post" action="/approve">
                <input type="hidden" name="client_id" value="{{ client_id }}">
                <input type="hidden" name="redirect_uri" value="{{ redirect_uri }}">
                <input type="hidden" name="state" value="{{ state }}">
                <input type="hidden" name="scope" value="{{ scope }}">
                <input type="hidden" name="username" value="{{ username }}">
                <button class="allow-btn" type="submit">Allow</button>
            </form>
            
            <form method="get" action="/deny">
                <input type="hidden" name="client_id" value="{{ client_id }}">
                <input type="hidden" name="redirect_uri" value="{{ redirect_uri }}">
                <input type="hidden" name="state" value="{{ state }}">
                <button class="deny-btn" type="submit">Deny</button>
            </form>
        </div>
    </div>
</body>
</html>
""")

# Routes
@app.get("/")
async def root():
    return {"message": "OAuth 2.0 Authorization Server"}

@app.get("/authorize")
async def authorize(
    request: Request,
    response_type: str = "code",
    client_id: str = None,
    redirect_uri: str = None,
    scope: str = "",
    state: str = None
):
    # Validate the request
    if response_type != "code":
        return JSONResponse(
            status_code=400,
            content={"error": "unsupported_response_type"}
        )
    
    if client_id != CLIENT_ID:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_client"}
        )
    
    if redirect_uri and redirect_uri not in REDIRECT_URIS:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_redirect_uri"}
        )
    
    # Show login page
    return templates.TemplateResponse(
        "login.html", 
        {
            "request": request,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": scope
        }
    )

@app.post("/authorize")
async def authorize_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
    state: str = Form(None),
    scope: str = Form("")
):
    # Validate the request
    if client_id != CLIENT_ID:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_client"}
        )
    
    if redirect_uri not in REDIRECT_URIS:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_redirect_uri"}
        )
    
    # Validate user credentials
    user = authenticate_user(username, password)
    if not user:
        return templates.TemplateResponse(
            "login.html", 
            {
                "request": request,
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "state": state,
                "scope": scope,
                "error": "Invalid username or password"
            },
            status_code=401
        )
    
    # Show consent page
    scopes = scope.split() if scope else []
    
    # Prepare scope descriptions for the consent page
    scope_descriptions = {
        "profile": "Access to your basic profile information",
        "email": "Access to your email address",
        "metadata": "Access to additional user information (name, role, etc.)",
    }
    
    # Create list of scopes with descriptions
    scope_info = []
    for s in scopes:
        scope_info.append({
            "name": s,
            "description": scope_descriptions.get(s, f"Access to {s} data")
        })
    
    return templates.TemplateResponse(
        "consent.html", 
        {
            "request": request,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": scope,
            "scopes": scope_info,
            "username": username
        }
    )

@app.post("/approve")
async def approve(
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
    state: str = Form(None),
    scope: str = Form(""),
    username: str = Form(...)
):
    # Generate authorization code
    auth_code = generate_auth_code()
    
    # Store the code with associated information
    AUTH_CODES[auth_code] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "username": username,
        "expires_at": datetime.utcnow() + timedelta(minutes=10)
    }
    
    # Construct the redirect URL
    redirect_url = f"{redirect_uri}?code={auth_code}"
    if state:
        redirect_url += f"&state={state}"
    
    return RedirectResponse(url=redirect_url)

@app.get("/deny")
async def deny(
    client_id: str,
    redirect_uri: str,
    state: str = None
):
    # Construct the redirect URL with error
    redirect_url = f"{redirect_uri}?error=access_denied"
    if state:
        redirect_url += f"&state={state}"
    
    return RedirectResponse(url=redirect_url)

@app.post("/token")
async def token(request: Request):
    # Get form data directly without using OAuth2PasswordRequestForm
    form = await request.form()
    
    # Extract data in standard OAuth format
    grant_type = form.get("grant_type")
    code = form.get("code")
    client_id = form.get("client_id")
    client_secret = form.get("client_secret")
    redirect_uri = form.get("redirect_uri")
    
    # Debug information
    print(f"Token request received with raw form data: {dict(form)}")
    print(f"Grant type: {grant_type}, Code: {code}")
    print(f"Client ID: {client_id}, Redirect URI: {redirect_uri}")
    print(f"Available codes: {list(AUTH_CODES.keys())}")
    
    # Validate grant type
    if grant_type != "authorization_code":
        return JSONResponse(
            status_code=400,
            content={"error": "unsupported_grant_type", "error_description": f"Unsupported grant type: {grant_type}"}
        )
    
    # Validate client credentials
    if client_id != CLIENT_ID or client_secret != CLIENT_SECRET:
        print(f"Invalid client credentials")
        return JSONResponse(
            status_code=401,
            content={"error": "invalid_client"}
        )
    
    # Validate the authorization code
    if not code or code not in AUTH_CODES:
        print(f"Invalid code: {code}")
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_grant", "error_description": "Invalid or missing authorization code"}
        )
    
    auth_code_data = AUTH_CODES[code]
    
    # Check if the code has expired
    if datetime.utcnow() > auth_code_data["expires_at"]:
        # Remove the expired code
        AUTH_CODES.pop(code)
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_grant", "error_description": "Authorization code expired"}
        )
    
    # Check that the client_id matches
    if auth_code_data["client_id"] != client_id:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_grant", "error_description": "Client ID mismatch"}
        )
    
    # Check that the redirect_uri matches (if provided)
    if redirect_uri and auth_code_data["redirect_uri"] != redirect_uri:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_grant", "error_description": "Redirect URI mismatch"}
        )
    
    # Generate access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": auth_code_data["username"]},
        expires_delta=access_token_expires
    )
    
    # Remove the used authorization code
    AUTH_CODES.pop(code)
    
    # Store the token
    token_data = {
        "access_token": access_token,
        "token_type": "bearer",
        "username": auth_code_data["username"],
        "scope": auth_code_data["scope"],
        "expires_at": datetime.utcnow() + access_token_expires
    }
    TOKENS[access_token] = token_data
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "scope": auth_code_data["scope"]
    }

@app.get("/userinfo")
async def userinfo(request: Request):
    # Extract the Authorization header
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"error": "invalid_token"}
        )
    
    token = auth_header.split(" ")[1]
    
    # Check if the token exists
    if token not in TOKENS:
        return JSONResponse(
            status_code=401,
            content={"error": "invalid_token"}
        )
    
    token_data = TOKENS[token]
    
    # Check if the token has expired
    if datetime.utcnow() > token_data["expires_at"]:
        # Remove the expired token
        TOKENS.pop(token)
        return JSONResponse(
            status_code=401,
            content={"error": "invalid_token", "error_description": "Token expired"}
        )
    
    # Get the user information
    username = token_data["username"]
    user_data = USERS_DB.get(username)
    
    if not user_data:
        return JSONResponse(
            status_code=404,
            content={"error": "user_not_found"}
        )
    
    # Construct the response based on authorized scopes
    response = {
        "username": user_data["username"],
        "email": user_data["email"]
    }
    
    # Check if the metadata scope was authorized
    scopes = token_data.get("scope", "").split()
    if "metadata" in scopes:
        # Add metadata to the response
        response["metadata"] = user_data.get("metadata", {})
    
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000) 