# Pathfinding Fixes Changelog

## Summary
This changelog captures the pathfinding reliability and performance fixes applied across Blender routing, backend API handling, and frontend request behavior.

## Blender (`Blender/blender_evacuate_path.py`)
- Added robust outside-exit completion logic:
  - Detect outside-connected void region.
  - Ensure the path reaches a true outside-edge walkable cell.
  - Extend final route segment into outside cells for a visible full exit.
- Added optional virtual outside-line extension fallback for edge cases.
- Reduced visual wall overlap:
  - Path tube radius reduced (`bevel_depth` from `0.12` to `0.08`).
  - Added wall-clearance post-processing for interior path cells.
  - Disabled Q-learning smoothing passes to avoid curve bulging into walls.
- Improved simulated aftermath safety:
  - `simulated_mode` auto-detected from `_simulated` inputs.
  - Stricter floor/obstacle interpretation tuned for damaged geometry.
- Fixed wall clipping bug:
  - Added diagonal corner-cut prevention in both `astar` and `astar_breakout`.
- Improved Q-learning runtime:
  - Adaptive episode counts by map complexity.
  - Early convergence stop.
  - Warm-start retries by reusing learned Q-table.
  - Reduced oversized train-start pools.
- Added diagnostics metadata fields:
  - `outside_extended`, `virtual_line_cells`, `simulated_mode`.

## Backend (`webapp/backend/main.py`)
- Pathfinding endpoint hardening:
  - Added algorithm input normalization and validation.
  - Added safe fallback for invalid algorithm values.
- Endpoint behavior clarified:
  - Respect explicit `use_simulated` instead of implicitly preferring stale simulated models.

## Frontend (`webapp/frontend/app/page.tsx`)
- Evacuation request behavior updates:
  - Algorithm request control aligned with backend validation.
  - Coordinate submission consistency retained (`start_y = -targetZ`).
- Converted model-generation defaults aligned with chosen wall/pixel parameters.

## Logging Cleanup
- Removed temporary debug/noise logs from Blender pathfinding flow:
  - Removed `DEBUG:` trial/start/path prints.
  - Removed `ML STATUS:` progress chatter.
  - Kept warnings/errors that are operationally relevant.
