# 2D Blueprint to 3D Model

This project converts 2D floorplans into 3D building models, supports disaster simulation, predicts damage severity, and generates evacuation routes with Blender-based pathfinding.

## Project Overview

The repository includes a complete pipeline:

1. Upload a blueprint image
2. Convert it into a 3D model
3. Run disaster simulation (fire, flood, earthquake)
4. Predict damage severity per area
5. Generate evacuation path and export an evacuated model

Core components:

- FastAPI backend for orchestration and APIs
- Next.js frontend for interactive workflow and 3D preview
- Blender scripts for model processing and route generation
- Floorplan processing library for geometry and analysis

## Main Features

- Blueprint to 3D conversion
- Simulation-aware model processing
- Damage prediction with severity summary
- Evacuation route generation with:
   - Reachable-exit detection
   - Outside-connected void handling
   - Simulated-mode routing safeguards
   - Diagonal corner-cut prevention in fallback search
   - Route diagnostics metadata output

## Repository Structure

Top-level folders/files commonly used in development:

- Blender/
   - Blender automation scripts including evacuation pathfinding
- FloorplanToBlenderLib/
   - Core floorplan parsing, transformation, and generation logic
- webapp/backend/
   - FastAPI backend service and API endpoints
- webapp/frontend/
   - Next.js frontend application
- Data/
   - Processed/intermediate data assets
- Target/
   - Generated output models and artifacts
- Models/
   - Model and q-table related artifacts

## Tech Stack

- Python, FastAPI, Uvicorn
- Blender Python API (bpy)
- Next.js, React, TypeScript
- NumPy/OpenCV and related Python ecosystem packages

## Prerequisites

- Windows environment (recommended for current scripts)
- Python 3.10+
- Node.js 18+
- Blender installed and accessible from system path or configured path

## Setup

### 1) Clone repository

```bash
git clone https://github.com/jayant1554/2d_blueprint_to_3d_model.git
cd 2d_blueprint_to_3d_model
```

### 2) Python environment

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3) Frontend dependencies

```bash
cd webapp/frontend
npm install
cd ../..
```

## Running the Project

### Backend

```bash
uvicorn webapp.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd webapp/frontend
npm run dev
```

### Access

- Frontend: http://localhost:3000
- Backend docs: http://localhost:8000/docs

## User Workflow

1. Open frontend UI
2. Upload blueprint
3. Convert to 3D model
4. Optionally run simulation
5. Run damage prediction
6. Go to evacuation and select start point
7. Generate evacuation route and review exported result

## API Endpoints (Core)

- POST /convert
- POST /simulate
- POST /damage-predict
- POST /pathfind
- GET /history

## Pathfinding Behavior Notes

- Q-learning path generation is available for learned routing behavior.
- Deterministic fallback is used when Q-learning output is unreliable.
- Simulated model inputs are detected and handled with tuned grid behavior.
- Outside completion logic helps routes end visibly outside the building envelope.
- Diagnostics are written next to output model as `.pathmeta.json`.

## Performance Notes

- Current tabular Q-learning implementation is CPU-bound Python logic.
- It does not fully utilize GPU hardware by default.
- Runtime improvements already integrated include:
   - Adaptive episode sizing
   - Early convergence stop
   - Retry warm-start with retained Q-table

## Troubleshooting

### bpy unresolved in editor

If static analysis reports unresolved import for `bpy`, this is expected outside Blender runtime.

### Path intersects wall after simulation

- Ensure latest pathfinding script changes are present in Blender evacuation script.
- Verify simulated-mode inputs are being used when expected.

### Pathfinding takes too long

- Use deterministic route mode where learning is not required.
- Reduce simulation complexity and verify environment resources.

### Stale generated models

- Check output files in Target/ and rerun conversion/simulation as needed.

## Documentation Files

Additional generated documentation in this repo:

- README_PUBLIC.md
- README_DEVELOPER.md

## Contributing

Contributions are welcome.

1. Create a feature branch
2. Keep commits focused and scoped
3. Open a pull request with clear test notes

See CONTRIBUTING.md for contribution guidance.

## License

MIT License. See LICENSE for details.
