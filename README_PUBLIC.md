# Blueprint to 3D Model

Convert 2D floorplans into 3D models, run disaster simulations, estimate damage, and generate evacuation paths.

## What This Project Does

- Upload a floorplan image
- Convert it into a 3D building model
- Simulate disaster scenarios (fire, flood, earthquake)
- Predict damage severity by area
- Generate evacuation routes with Blender-based pathfinding

## Highlights

- End-to-end 2D to 3D pipeline
- Interactive web UI for conversion, simulation, and route generation
- Robust exit-oriented pathfinding with outside-aware completion
- Simulation-aware collision handling to reduce wall clipping
- FastAPI backend + Next.js frontend + Blender automation

## Tech Stack

- Python, FastAPI, Uvicorn
- Blender Python API
- Next.js, React, TypeScript

## Quick Start

1. Clone repo

```bash
git clone <your-repo-url>
cd 2d_blueprint_to_3d_model
```

2. Setup Python

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

3. Setup frontend

```bash
cd webapp/frontend
npm install
cd ../..
```

4. Run backend

```bash
uvicorn webapp.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

5. Run frontend

```bash
cd webapp/frontend
npm run dev
```

6. Open app

- Frontend: http://localhost:3000
- Backend API docs: http://localhost:8000/docs

## Main Workflow

1. Upload blueprint
2. Convert to 3D
3. Run simulation
4. Run damage prediction
5. Generate evacuation path

## Project Layout

- Blender/ - Blender scripts for conversion/pathfinding export flow
- FloorplanToBlenderLib/ - Core floorplan parsing and geometry logic
- webapp/backend/ - FastAPI endpoints
- webapp/frontend/ - Next.js UI
- Target/ - Generated output models

## License

MIT (see LICENSE)
