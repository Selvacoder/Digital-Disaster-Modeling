# Developer README

This guide covers local development, debugging, and implementation details.

## Prerequisites

- Windows environment (primary tested path)
- Python 3.10+
- Node.js 18+
- Blender installed and accessible by backend process

## Environment Setup

### 1) Python environment

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2) Frontend dependencies

```bash
cd webapp/frontend
npm install
cd ../..
```

## Run Services

### Backend

```bash
uvicorn webapp.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd webapp/frontend
npm run dev
```

## Core Runtime Flow

1. Client uploads blueprint image
2. Backend convert endpoint generates model artifacts
3. Optional simulation endpoint generates simulated model variant
4. Damage prediction endpoint returns area-based severity estimates
5. Pathfinding endpoint launches Blender script and exports evacuated model

## Key Files

- webapp/backend/main.py
  - API orchestration for convert/simulate/damage/pathfind
- webapp/frontend/app/page.tsx
  - UI actions and request payload composition
- Blender/blender_evacuate_path.py
  - Grid build, exit detection, Q-learning/A* path logic, export, diagnostics

## Pathfinding Notes

- Hybrid strategy:
  - Q-learning for learned route behavior
  - Deterministic A* fallback for reliability
- Grid semantics:
  - 0: outside/void
  - 1: walkable
  - 2: hard obstacle
  - 3: soft obstacle (penalized)
- Outside handling:
  - Detect outside-connected void cells
  - Ensure route reaches outside-edge walkable cells
  - Extend route for visible full exit when enabled
- Simulation mode:
  - Auto-detected from simulated input naming
  - Tuned obstacle/floor handling for damaged geometry

## Performance Notes

- Current tabular Q-learning is CPU-bound Python logic.
- GPU (e.g., GTX 1650) is not fully utilized with this algorithm design.
- Speed improvements currently implemented:
  - Adaptive episode counts
  - Early convergence stop
  - Retry warm-start with shared Q-table

## Debugging Tips

### Blender import warning in editor

If you see unresolved bpy import in static analysis, this is expected outside Blender runtime.

### Path looks like it crosses walls

- Verify simulated vs non-simulated input mode
- Check diagonal corner-cut prevention in A* logic
- Inspect generated diagnostics metadata next to exported path model

### Pathfinding too slow

- Confirm adaptive Q-learning settings are active
- Use A* mode for fast deterministic routing if learning behavior is not required

## Useful Endpoints

- POST /convert
- POST /simulate
- POST /damage-predict
- POST /pathfind
- GET /history

## Suggested Commit Grouping

1. Backend API validation/selection changes
2. Frontend request/UX behavior changes
3. Blender pathfinding and export logic changes

## Documentation Files

- PATHFINDING_CHANGELOG.md
- PATHFINDING_COMMIT_MESSAGES.md
- README_PUBLIC.md
- README_DEVELOPER.md
