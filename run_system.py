import subprocess
import time
import os
import sys

def run_command(command, cwd=None, new_console=True):
    """
    Runs a command in a new console window (Windows).
    """
    kwargs = {}
    if new_console and sys.platform == "win32":
        kwargs['creationflags'] = subprocess.CREATE_NEW_CONSOLE
    
    print(f"[RUNNER] Starting: {command}")
    return subprocess.Popen(command, cwd=cwd, shell=True, **kwargs)

def main():
    print("===========================================")
    print("   ECOPE Production System Launcher")
    print("===========================================")
    
    # 1. Start Backend
    print("\n[1/3] Starting Backend (FastAPI)...")
    CMD_BACKEND = "python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000"
    p_backend = run_command(CMD_BACKEND)
    
    # Wait for backend to init
    time.sleep(3)
    
    # 2. Start Frontend
    print("\n[2/3] Starting Frontend (React)...")
    CMD_FRONTEND = "npm run dev"
    cwd_frontend = os.path.join(os.getcwd(), "frontend")
    p_frontend = run_command(CMD_FRONTEND, cwd=cwd_frontend)
    
    print("\n===========================================")
    print("   Backend & Frontend Launched!")
    print("===========================================")
    print("-> Backend: http://localhost:8000")
    print("-> Frontend: http://localhost:5173")
    print("\n[3/3] To start the CV Engine, please run the following command manually in a new terminal:")
    print(f"   python {os.path.join('cv_engine', 'orchestrator.py')}")
    print("\n(Press Ctrl+C in this window to stop the launcher, though child processes may persist)")
    
    try:
        while True:
            time.sleep(1)
            # Check if processes are alive
            if p_backend.poll() is not None:
                print("[RUNNER] Backend stopped unexpectedly.")
                break
            if p_frontend.poll() is not None:
                print("[RUNNER] Frontend stopped unexpectedly.")
                break
    except KeyboardInterrupt:
        print("\n[RUNNER] Stopping services...")
        p_backend.terminate()
        p_frontend.terminate()
        print("[RUNNER] Done.")

if __name__ == "__main__":
    main()
