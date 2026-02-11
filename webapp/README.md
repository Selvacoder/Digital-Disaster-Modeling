# 🌐 2D Blueprint to 3D Model Web UI

A premium, modern web interface for converting architectural blueprints into 3D models.

## 🚀 Features
- **Premium Dashboard**: Glassmorphic dark mode design.
- **Interactive 3D Preview**: Inspect your models directly in the browser using Three.js.
- **Easy Configuration**: Adjust heights and scales via a visual interface.
- **FastAPI Backend**: Modern, high-performance API handling.

## 🛠️ Setup Instructions

### 1. Prerequisites
- **Node.js**: (v18 or later)
- **Python**: (v3.10 or later)
- **Blender**: (Installed and path set in `Configs/system.ini`)

### 2. Install Dependencies

**Backend:**
```bash
pip install fastapi uvicorn python-multipart
```

**Frontend:**
```bash
cd webapp/frontend
npm install
```

### 3. Run the Application
From the project root:
```bash
python webapp/run_webapp.py
```

- **Dashboard:** [http://localhost:3000](http://localhost:3000)
- **API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

## 📁 Project Structure
- `webapp/backend/`: FastAPI Python server.
- `webapp/frontend/`: Next.js React application.
- `webapp/run_webapp.py`: Multi-server launcher.
