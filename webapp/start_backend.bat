@echo off
set "PYTHON_PATH=C:\Users\selva\AppData\Local\Programs\Python\Python310\python.exe"
cd /d "d:\Projects\2d_blueprint_to_3d_model\webapp\backend"
"%PYTHON_PATH%" -m uvicorn main:app --port 8000
pause
