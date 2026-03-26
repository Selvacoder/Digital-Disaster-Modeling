# Commit Message Set

## 1) Backend
feat(backend): harden pathfinding algorithm handling and model selection

- Normalize and validate `algorithm` input in `/pathfind`
- Fallback to safe default when invalid algorithm is provided
- Respect explicit `use_simulated` selection to avoid stale model routing

## 2) Frontend
fix(frontend): align evacuation request defaults and coordinate mapping

- Keep evacuation request payload consistent with backend validation
- Preserve correct click-to-path coordinate mapping (`start_y = -targetZ`)
- Align convert defaults with selected wall height and pixel scale settings

## 3) Blender
fix(blender): stabilize evacuation path quality, outside exit, and runtime

- Prevent wall clipping with diagonal corner-cut checks in A* and breakout
- Ensure path reaches a true outside edge and extends visibly outside
- Improve post-simulation routing robustness with simulated-mode grid tuning
- Reduce visual wall overlap via clearance pass and thinner path tube
- Speed up tabular Q-learning using adaptive episodes, early stop, and warm-start retries
- Remove temporary debug/progress log noise while keeping warnings/errors
