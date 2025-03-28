import subprocess
import sys
import os
import time
import threading
import webbrowser

def run_server():
    print("Starting OAuth 2.0 Authorization Server...")
    os.chdir("server")
    server_process = subprocess.Popen([sys.executable, "run.py"])
    return server_process

def run_client():
    print("Starting OAuth 2.0 Client Application...")
    os.chdir("client")
    client_process = subprocess.Popen([sys.executable, "run.py"])
    return client_process

def open_browser():
    print("Opening browser to client application...")
    time.sleep(3)  # Wait for the servers to start
    webbrowser.open("http://localhost:5001")

if __name__ == "__main__":
    print("Starting OAuth 2.0 Demo Applications")
    
    original_dir = os.getcwd()
    
    # Start the server
    server_process = run_server()
    
    # Return to the original directory
    os.chdir(original_dir)
    
    # Start the client
    client_process = run_client()
    
    # Return to the original directory
    os.chdir(original_dir)
    
    # Open browser after a delay
    threading.Thread(target=open_browser).start()
    
    try:
        print("\nPress Ctrl+C to stop both applications...\n")
        # Wait for the processes to complete
        server_process.wait()
        client_process.wait()
    except KeyboardInterrupt:
        print("\nStopping applications...")
        server_process.terminate()
        client_process.terminate()
        
    print("OAuth 2.0 Demo Applications have been stopped.") 