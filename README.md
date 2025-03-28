# OAuth 2.0 Demo Application

This project demonstrates a basic implementation of the OAuth 2.0 Authorization Code flow, with both a client and server component.

## Project Overview

- **Server**: OAuth 2.0 Authorization Server (FastAPI)
- **Client**: OAuth 2.0 Client Application (FastAPI)

The demo showcases the complete OAuth 2.0 flow:
1. Client requests authorization from the user
2. User authenticates and approves the authorization
3. Authorization server sends an authorization code to the client
4. Client exchanges the code for an access token
5. Client uses the access token to access protected resources

## User Credentials

For testing purposes, the application has a hardcoded user:
- **Username**: user
- **Password**: password

## Setup and Running

### Requirements

- Python 3.7+
- pip

### Server Setup

1. Navigate to the server directory:
   ```
   cd server
   ```

2. Install the required dependencies:
   ```
   pip install fastapi uvicorn python-jose[cryptography] python-multipart secure pydantic authlib itsdangerous jinja2
   ```

3. Run the server:
   ```
   python run.py
   ```

The server will be available at: `http://localhost:5000`

### Client Setup

1. Navigate to the client directory:
   ```
   cd client
   ```

2. Install the required dependencies:
   ```
   pip install fastapi uvicorn requests python-jose[cryptography] python-multipart jinja2 itsdangerous
   ```

3. Run the client:
   ```
   python run.py
   ```

The client will be available at: `http://localhost:5001`

## Testing the OAuth Flow

1. Open a web browser and go to `http://localhost:5001`
2. Click on "Login with OAuth"
3. You will be redirected to the authorization server
4. Enter the username "user" and password "password"
5. Approve the authorization request
6. You will be redirected back to the client application
7. The client will display your user information and access token details

## Project Structure

```
├── client/                 # OAuth 2.0 Client
│   ├── main.py             # Client application
│   ├── run.py              # Client runner
│   └── templates/          # HTML templates (generated)
│       ├── home.html       # Client home page
│       └── error.html      # Error page
│
├── server/                 # OAuth 2.0 Server
│   ├── main.py             # Authorization server
│   ├── run.py              # Server runner
│   └── templates/          # HTML templates (generated)
│       ├── login.html      # Login page
│       └── consent.html    # Consent page
│
└── README.md               # Project documentation
```

## Security Notes

This is a demo application intended for educational purposes only. In a production environment, you would need to implement:

- Secure storage of client secrets and tokens
- Proper user authentication with password hashing
- HTTPS for all communications
- More comprehensive error handling
- Session management with proper expiration
- Security headers and other best practices 