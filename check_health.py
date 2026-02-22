import socket
import psycopg2
import os
import requests
import sys

# Color codes
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

def check_port(host, port, service_name):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        if result == 0:
            print(f"[{GREEN}OK{RESET}] {service_name} is listening on port {port}")
            return True
        else:
            print(f"[{RED}FAIL{RESET}] {service_name} is NOT listening on port {port}")
            return False
    except Exception as e:
        print(f"[{RED}FAIL{RESET}] {service_name} check error: {e}")
        return False

def check_db():
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="ecope_production",
            user="ecope_user",
            password="ecope_secure_password"
        )
        conn.close()
        print(f"[{GREEN}OK{RESET}] Database connection successful")
        return True
    except Exception as e:
        print(f"[{RED}FAIL{RESET}] Database connection failed: {e}")
        return False

def check_backend_api():
    try:
        # Try to hit the docs endpoint which is standard in FastAPI
        response = requests.get("http://localhost:8000/docs", timeout=2)
        if response.status_code == 200:
            print(f"[{GREEN}OK{RESET}] Backend API is responsive")
            return True
        else:
            print(f"[{RED}FAIL{RESET}] Backend API returned code {response.status_code}")
            return False
    except Exception as e:
        print(f"[{RED}FAIL{RESET}] Backend API request failed: {e}")
        return False

if __name__ == "__main__":
    print("--- System Health Check ---")
    
    # 1. Check DB
    db_ok = check_db()
    
    # 2. Check Ports
    be_port = check_port("localhost", 8000, "Backend Server")
    fe_port = check_port("localhost", 5173, "Frontend Server")
    
    # 3. Check Backend Logic
    be_api = False
    if be_port:
        be_api = check_backend_api()
    
    print("\n--- Summary ---")
    if db_ok and be_port and fe_port and be_api:
        print(f"{GREEN}ALL SYSTEMS NOMINAL. You are ready to launch the CV Engine.{RESET}")
    else:
        print(f"{RED}SOME SYSTEMS ARE DOWN. Please fix before proceeding.{RESET}")
