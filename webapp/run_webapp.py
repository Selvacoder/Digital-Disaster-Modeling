import subprocess
import os
import sys
import time

def start_servers():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(base_dir, "backend")
    frontend_dir = os.path.join(base_dir, "frontend")

    print("🚀 Starting 2D Blueprint to 3D Model Web UI...")
    
    # Start Backend
    print("👉 Starting Backend API (FastAPI)...")
    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--reload", "--port", "8000"],
        cwd=backend_dir
    )

    # Start Frontend
    print("👉 Starting Frontend (Next.js)...")
    # Note: Assumes npm install has been run
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_dir,
        shell=True
    )

    print("\n✅ Web UI is launching!")
    print("🔗 Backend API: http://localhost:8000")
    print("🔗 Frontend Dashboard: http://localhost:3000")
    print("\nPress Ctrl+C to stop both servers.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping servers...")
        backend_proc.terminate()
        frontend_proc.terminate()

if __name__ == "__main__":
    start_servers()
