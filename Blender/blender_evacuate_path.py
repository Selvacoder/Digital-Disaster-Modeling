"""
Blender Evacuation Pathfinding Script
Runs headlessly to compute and visualize evacuation paths on a 3D floorplan.

Usage:
    blender -noaudio --background --python blender_evacuate_path.py -- \
        <blend_path> <output_obj_path> <start_x> <start_y>

Algorithm:
    1. Analyze floor/room meshes to build a 2D navigable grid.
    2. Identify exit points (doors/windows) as destinations.
    3. Run A* pathfinding from start to nearest exit.
    4. Create a visible green tube along the path.
"""

import bpy
import sys
import os
import math
import heapq
import random
import json
from collections import deque


def parse_args():
    """Parse arguments after '--' separator."""
    argv = sys.argv
    if "--" not in argv:
        return {}
    args = argv[argv.index("--") + 1:]
    return {
        "blend_path": args[0],
        "output_path": args[1],
        "start_x": float(args[2]),
        "start_y": float(args[3]),
        "dest_x": float(args[4]) if len(args) > 4 and args[4] != "None" else None,
        "dest_y": float(args[5]) if len(args) > 5 and args[5] != "None" else None,
        "algo": args[6] if len(args) > 6 else "qlearning"
    }


def make_emission_material(name, color_rgba, strength=10.0):
    """
    Create a pure emission material and return it.
    Works correctly before AND after bpy.ops.object.convert(target='MESH').
    color_rgba: tuple (R, G, B, A) with values 0.0-1.0
    """
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output   = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value   = color_rgba
    emission.inputs["Strength"].default_value = strength
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return mat


def create_path_material():
    """Bright red emission material for the evacuation path tube."""
    return make_emission_material("EvacPathMaterial", (1.0, 0.05, 0.05, 1.0), strength=10.0)


def create_exit_material():
    """Yellow emission material for the exit destination marker."""
    return make_emission_material("ExitMarkerMaterial", (1.0, 0.9, 0.1, 1.0), strength=5.0)


def create_trapped_path_material():
    """Orange-red emission material used when no exit is reachable."""
    return make_emission_material("TrappedPathMaterial", (1.0, 0.2, 0.0, 1.0), strength=10.0)


def create_trapped_exit_material():
    """Red emission material for the endpoint when trapped."""
    return make_emission_material("TrappedExitMaterial", (1.0, 0.0, 0.0, 1.0), strength=8.0)


def get_scene_bounds():
    """Get the XY bounding box of all mesh objects."""
    min_x = min_y = float('inf')
    max_x = max_y = float('-inf')

    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            for vert in obj.data.vertices:
                world_co = obj.matrix_world @ vert.co
                min_x = min(min_x, world_co.x)
                max_x = max(max_x, world_co.x)
                min_y = min(min_y, world_co.y)
                max_y = max(max_y, world_co.y)

    return min_x, max_x, min_y, max_y


def build_navigable_grid(resolution=0.5):
    """
    Build a 2D grid marking walkable vs obstacle cells.
    Uses raycasting to detect floor and wall positions accurately.
    Grid values:
        0  = unvisited (treated as obstacle)
        1  = walkable floor
        2  = hard obstacle (wall / rubble)
        3  = soft obstacle (adjacent to wall, high path cost)
    """
    min_x, max_x, min_y, max_y = get_scene_bounds()

    min_x -= 1; min_y -= 1
    max_x += 1; max_y += 1

    cols = int((max_x - min_x) / resolution) + 1
    rows = int((max_y - min_y) / resolution) + 1
    grid = [[0] * cols for _ in range(rows)]

    scene    = bpy.context.scene
    depsgraph = scene.view_layers[0].depsgraph

    for r in range(rows):
        for c in range(cols):
            wx = min_x + c * resolution
            wy = min_y + r * resolution

            # --- Vertical downward ray from 1 m height ---
            origin = (wx, wy, 1.0)
            hit, loc, norm, index, obj, matrix = scene.ray_cast(depsgraph, origin, (0, 0, -1))

            if not hit:
                grid[r][c] = 0          # Outside/void — not walkable
            elif loc.z <= 0.25:
                grid[r][c] = 1          # Floor level — walkable
            else:
                grid[r][c] = 2          # Elevated surface — obstacle

            # --- Horizontal wall-probe at ankle height ---
            if grid[r][c] == 1:
                origin_wall = (wx, wy, 0.5)
                diagonals   = [(1,0),(-1,0),(0,1),(0,-1),
                               (0.707,0.707),(-0.707,0.707),(0.707,-0.707),(-0.707,-0.707)]
                for dx, dy in diagonals:
                    hit_w, loc_w, *_ = scene.ray_cast(
                        depsgraph, origin_wall, (dx, dy, 0), distance=resolution * 0.8)
                    if hit_w:
                        # Treat near-wall hits as soft obstacle, not hard block,
                        # to avoid over-blocking after simulation debris appears.
                        grid[r][c] = 3
                        break

            # --- High-floor / debris override ---
            if grid[r][c] == 2:
                origin_high = (wx, wy, 0.4)
                hit_h, loc_h, *_ = scene.ray_cast(depsgraph, origin_high, (0, 0, -1))
                if hit_h and loc_h.z <= 0.45:
                    grid[r][c] = 1

    # --- Soft obstacle (wall-proximity penalty) layer ---
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 2:
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 1:
                            grid[nr][nc] = 3

    # --- Detect outside-connected void to derive true building exits topologically ---
    outside_void = set()
    q = deque()
    for r in range(rows):
        for c in (0, cols - 1):
            if grid[r][c] == 0 and (r, c) not in outside_void:
                outside_void.add((r, c))
                q.append((r, c))
    for c in range(cols):
        for r in (0, rows - 1):
            if grid[r][c] == 0 and (r, c) not in outside_void:
                outside_void.add((r, c))
                q.append((r, c))

    while q:
        r, c = q.popleft()
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 0 and (nr, nc) not in outside_void:
                outside_void.add((nr, nc))
                q.append((nr, nc))

    topological_exits = []
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] not in (1, 3):
                continue
            # A walkable cell adjacent to outside-connected void is an actual exit edge.
            for dr, dc in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
                nr, nc = r + dr, c + dc
                if (nr, nc) in outside_void:
                    topological_exits.append((r, c))
                    break

    # --- Locate exit cells from boundary-facing door/window objects (secondary signal) ---
    exit_cells   = []
    door_keywords = ["door", "window", "entry", "gate", "doorway", "opening"]
    core_min_x = min_x + 1.0
    core_max_x = max_x - 1.0
    core_min_y = min_y + 1.0
    core_max_y = max_y - 1.0
    core_span = max(1.0, min(core_max_x - core_min_x, core_max_y - core_min_y))
    edge_threshold = max(0.8, core_span * 0.12)

    for obj in bpy.data.objects:
        if obj.type == 'MESH' and any(k in obj.name.lower() for k in door_keywords):
            wc = obj.matrix_world @ obj.location
            name = obj.name.lower()

            # Ignore internal doors/openings; keep only envelope exits near outer boundary.
            if "emergency" not in name and "exit" not in name:
                dist_to_outer = min(
                    abs(wc.x - core_min_x),
                    abs(core_max_x - wc.x),
                    abs(wc.y - core_min_y),
                    abs(core_max_y - wc.y),
                )
                if dist_to_outer > edge_threshold:
                    continue

            er = int((wc.y - min_y) / resolution)
            ec = int((wc.x - min_x) / resolution)
            if 0 <= er < rows and 0 <= ec < cols:
                exit_cells.append((er, ec))
                # Force a clear passage around the door
                for dr in range(-2, 3):
                    for dc in range(-2, 3):
                        nr, nc = er + dr, ec + dc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            grid[nr][nc] = 1

    # Merge exits: prefer topology-derived exits so pathfinding does not rely on object names.
    exit_cells = topological_exits + exit_cells

    # De-duplicate exits and keep only walkable cells.
    if exit_cells:
        unique = []
        seen = set()
        for rc in exit_cells:
            if rc in seen:
                continue
            seen.add(rc)
            r, c = rc
            if 0 <= r < rows and 0 <= c < cols and grid[r][c] in (1, 3):
                unique.append(rc)
        exit_cells = unique

    # --- Fallback: perimeter-adjacent interior cells if no valid boundary exits found ---
    if not exit_cells:
        for r in range(rows):
            for c in range(cols):
                if grid[r][c] == 1:
                    if r <= 2 or r >= rows - 3 or c <= 2 or c >= cols - 3:
                        exit_cells.append((r, c))

    return grid, rows, cols, min_x, min_y, resolution, exit_cells


def find_reachable_exits(grid, rows, cols, start, goals):
    """BFS flood-fill to find which exits are actually reachable from start."""
    from collections import deque
    sr, sc  = start
    queue   = deque([(sr, sc)])
    visited = {(sr, sc)}
    reachable = []
    goal_set  = set(goals)

    while queue:
        r, c = queue.popleft()
        if (r, c) in goal_set:
            reachable.append((r, c))

        for dr, dc in [
            (-1,0),(1,0),(0,-1),(0,1),
            (-1,-1),(-1,1),(1,-1),(1,1)
        ]:
            nr, nc = r + dr, c + dc
            if (0 <= nr < rows and 0 <= nc < cols
                    and grid[nr][nc] in (1, 3)
                    and (nr, nc) not in visited):
                visited.add((nr, nc))
                queue.append((nr, nc))

    return reachable, visited


def build_safety_map(grid, rows, cols):
    """
    Build a normalized safety map (0..1) based on distance from hard obstacles/void.
    Higher score means safer walking cell.
    """
    from collections import deque

    inf = 10**9
    dist = [[inf] * cols for _ in range(rows)]
    q = deque()

    for r in range(rows):
        for c in range(cols):
            if grid[r][c] in (0, 2):
                dist[r][c] = 0
                q.append((r, c))

    for r, c in q:
        pass

    while q:
        r, c = q.popleft()
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and dist[nr][nc] > dist[r][c] + 1:
                dist[nr][nc] = dist[r][c] + 1
                q.append((nr, nc))

    max_safe_dist = 8.0
    safety = [[0.0] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] not in (1, 3):
                safety[r][c] = 0.0
            else:
                safety[r][c] = min(1.0, dist[r][c] / max_safe_dist)
    return safety


def astar(grid, rows, cols, start, goals):
    """A* pathfinding from start to nearest reachable goal."""
    sr, sc = start
    sr = max(0, min(rows - 1, sr))
    sc = max(0, min(cols - 1, sc))

    # Snap start to nearest walkable cell if it's on an obstacle
    if grid[sr][sc] not in (1, 3):
        best, best_dist = None, float('inf')
        for r in range(rows):
            for c in range(cols):
                if grid[r][c] in (1, 3):
                    d = abs(r - sr) + abs(c - sc)
                    if d < best_dist:
                        best_dist, best = d, (r, c)
        if best:
            sr, sc = best

    goal_set = set(goals)

    def h(r, c):
        return min(abs(r - gr) + abs(c - gc) for gr, gc in goals) if goals else 0

    open_set = [(0, 0, sr, sc)]
    came_from = {}
    g_score   = {(sr, sc): 0}

    directions = [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]

    while open_set:
        f, g, cr, cc = heapq.heappop(open_set)

        if (cr, cc) in goal_set:
            path = [(cr, cc)]
            while (cr, cc) in came_from:
                cr, cc = came_from[(cr, cc)]
                path.append((cr, cc))
            path.reverse()
            return path

        for dr, dc in directions:
            nr, nc = cr + dr, cc + dc
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue
            if grid[nr][nc] not in (1, 3):
                continue

            move_cost = 1.414 if (dr != 0 and dc != 0) else 1.0
            if grid[nr][nc] == 3:
                move_cost += 5.0   # Wall-proximity penalty

            new_g = g + move_cost
            if (nr, nc) not in g_score or new_g < g_score[(nr, nc)]:
                g_score[(nr, nc)] = new_g
                heapq.heappush(open_set, (new_g + h(nr, nc), new_g, nr, nc))
                came_from[(nr, nc)] = (cr, cc)

    # Fallback: return straight line to nearest goal
    if goals:
        nearest = min(goals, key=lambda g: abs(g[0]-sr)+abs(g[1]-sc))
        return [(sr, sc), nearest]
    return [(sr, sc)]


def astar_breakout(grid, rows, cols, start, goals):
    """Emergency A* that can cross hard obstacles with very high penalty when map is trapped."""
    sr, sc = start
    sr = max(0, min(rows - 1, sr))
    sc = max(0, min(cols - 1, sc))

    if grid[sr][sc] not in (1, 3, 2):
        best, best_dist = None, float('inf')
        for r in range(rows):
            for c in range(cols):
                if grid[r][c] in (1, 3, 2):
                    d = abs(r - sr) + abs(c - sc)
                    if d < best_dist:
                        best_dist, best = d, (r, c)
        if best:
            sr, sc = best

    goal_set = set(goals)

    def h(r, c):
        return min(abs(r - gr) + abs(c - gc) for gr, gc in goals) if goals else 0

    open_set = [(0, 0, sr, sc)]
    came_from = {}
    g_score = {(sr, sc): 0}
    directions = [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]

    while open_set:
        f, g, cr, cc = heapq.heappop(open_set)

        if (cr, cc) in goal_set:
            path = [(cr, cc)]
            while (cr, cc) in came_from:
                cr, cc = came_from[(cr, cc)]
                path.append((cr, cc))
            path.reverse()
            return path

        for dr, dc in directions:
            nr, nc = cr + dr, cc + dc
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue
            if grid[nr][nc] not in (1, 3, 2):
                continue

            move_cost = 1.414 if (dr != 0 and dc != 0) else 1.0
            if grid[nr][nc] == 3:
                move_cost += 5.0
            if grid[nr][nc] == 2:
                move_cost += 18.0  # emergency breakout penalty

            new_g = g + move_cost
            if (nr, nc) not in g_score or new_g < g_score[(nr, nc)]:
                g_score[(nr, nc)] = new_g
                heapq.heappush(open_set, (new_g + h(nr, nc), new_g, nr, nc))
                came_from[(nr, nc)] = (cr, cc)

    if goals:
        nearest = min(goals, key=lambda g: abs(g[0]-sr)+abs(g[1]-sc))
        return [(sr, sc), nearest]
    return [(sr, sc)]


class QLearningAgent:
    """Q-Learning agent for grid pathfinding (alternative to A*)."""
    def __init__(self, grid, rows, cols, start, goals,
                 alpha=0.25, gamma=0.92, epsilon=0.18, safety_map=None, train_starts=None):
        self.grid    = grid
        self.rows    = rows
        self.cols    = cols
        self.start   = start
        self.goals   = set(goals)
        self.alpha   = alpha
        self.gamma   = gamma
        self.epsilon = epsilon
        self.q_table = {}
        self.actions = [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]
        self.safety_map = safety_map if safety_map is not None else [[0.5] * cols for _ in range(rows)]
        self.train_starts = list(train_starts) if train_starts else [start]

    def get_q_values(self, state):
        if state not in self.q_table:
            self.q_table[state] = [0.0] * len(self.actions)
        return self.q_table[state]

    def get_heuristic(self, state):
        if not self.goals: return 0
        return min(abs(state[0]-gr)+abs(state[1]-gc) for gr, gc in self.goals)

    def choose_action(self, state):
        legal = self.get_legal_action_indices(state)
        if not legal:
            return None
        if random.random() < self.epsilon:
            return random.choice(legal)
        q = self.get_q_values(state)
        mx = max(q[i] for i in legal)
        return random.choice([i for i in legal if q[i] == mx])

    def is_walkable(self, rc):
        r, c = rc
        return 0 <= r < self.rows and 0 <= c < self.cols and self.grid[r][c] in (1, 3)

    def valid_transition(self, state, action_idx):
        dr, dc = self.actions[action_idx]
        ns = (state[0] + dr, state[1] + dc)
        if not self.is_walkable(ns):
            return None

        # Prevent diagonal corner-cutting through tight wall corners.
        if abs(dr) == 1 and abs(dc) == 1:
            side1 = (state[0] + dr, state[1])
            side2 = (state[0], state[1] + dc)
            if not (self.is_walkable(side1) and self.is_walkable(side2)):
                return None
        return ns

    def get_legal_action_indices(self, state):
        legal = []
        for idx in range(len(self.actions)):
            if self.valid_transition(state, idx) is not None:
                legal.append(idx)
        return legal

    def train(self, episodes=5000):
        print(f"ML STATUS: Q-Learning training for {episodes} episodes…")
        for ep in range(episodes):
            state = self.start if random.random() < 0.35 else random.choice(self.train_starts)
            steps = 0
            visited_ep = {state}
            while state not in self.goals and steps < 1200:
                idx = self.choose_action(state)
                if idx is None:
                    break

                ns = self.valid_transition(state, idx)
                if ns is None:
                    reward, ts = -25, state
                else:
                    if ns in self.goals:
                        reward = 1400
                    else:
                        progress = self.get_heuristic(state) - self.get_heuristic(ns)
                        safety_bonus = 3.5 * (self.safety_map[ns[0]][ns[1]] - 0.5)
                        reward = -1.2 + (1.8 * progress) + safety_bonus
                        if self.grid[ns[0]][ns[1]] == 3:
                            reward -= 4.0
                        if ns in visited_ep:
                            reward -= 1.5
                    ts = ns

                old_q  = self.get_q_values(state)[idx]
                next_max = max(self.get_q_values(ts))
                self.q_table[state][idx] = old_q + self.alpha*(reward+self.gamma*next_max-old_q)
                state = ts
                steps += 1
                visited_ep.add(state)

            self.epsilon = max(0.02, self.epsilon * 0.99992)
            if ep % 1000 == 0:
                print(f"ML STATUS: {ep}/{episodes} episodes…")

        print("ML STATUS: Training done. Extracting path.")

    def get_optimal_path(self):
        state   = self.start
        path    = [state]
        visited = {state}
        steps   = 0
        while state not in self.goals and steps < 1200:
            q = self.get_q_values(state)
            legal = self.get_legal_action_indices(state)
            if not legal:
                break

            # Safety-first score: learned Q + safety bonus + modest goal pull.
            ranked = sorted(
                legal,
                key=lambda i: (
                    q[i]
                    + 2.4 * self.safety_map[self.valid_transition(state, i)[0]][self.valid_transition(state, i)[1]]
                    - 0.05 * self.get_heuristic(self.valid_transition(state, i))
                ),
                reverse=True,
            )

            next_state = None
            for cand in ranked:
                ns = self.valid_transition(state, cand)
                if ns is None:
                    continue
                if ns not in visited:
                    next_state = ns
                    break
            if next_state is None:
                next_state = self.valid_transition(state, ranked[0])
                if next_state is None:
                    break

            state = next_state
            path.append(state)
            visited.add(state)
            steps += 1
        return path


def path_reaches_goal(path, goals):
    """Return True when path reaches a goal cell (or immediate neighborhood)."""
    if not path or not goals:
        return False
    end = path[-1]
    goal_set = set(goals)
    if end in goal_set:
        return True
    return min(abs(end[0] - g[0]) + abs(end[1] - g[1]) for g in goal_set) <= 1


def path_cost(grid, path):
    """Compute weighted travel cost for a cell path."""
    if not path or len(path) < 2:
        return float('inf')
    total = 0.0
    for i in range(1, len(path)):
        pr, pc = path[i - 1]
        cr, cc = path[i]
        diag = (pr != cr and pc != cc)
        step = 1.414 if diag else 1.0
        if grid[cr][cc] == 3:
            step += 5.0
        total += step
    return total


def snap_to_walkable_cell(grid, rows, cols, start_r, start_c, max_radius=26):
    """Snap a possibly invalid start cell to the nearest walkable cell."""
    start_r = max(0, min(rows - 1, start_r))
    start_c = max(0, min(cols - 1, start_c))

    if grid[start_r][start_c] in (1, 3):
        return start_r, start_c

    for dist in range(1, max_radius + 1):
        for dr in range(-dist, dist + 1):
            for dc in range(-dist, dist + 1):
                nr, nc = start_r + dr, start_c + dc
                if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] in (1, 3):
                    return nr, nc
    return start_r, start_c


def choose_best_start_candidate(grid, rows, cols, min_x, min_y, resolution, start_x, start_y, exit_cells):
    """
    Choose the better start coordinate mapping between y and mirrored -y.
    This makes the pipeline robust to upstream axis-sign mismatches.
    """
    # Candidate A: direct y. Candidate B: mirrored y.
    candidates_world = [(start_x, start_y), (start_x, -start_y)]
    best = None

    for cand_x, cand_y in candidates_world:
        cand_r = int((cand_y - min_y) / resolution)
        cand_c = int((cand_x - min_x) / resolution)
        cand_r, cand_c = snap_to_walkable_cell(grid, rows, cols, cand_r, cand_c)

        reachable_goals, reachable_set = find_reachable_exits(
            grid, rows, cols, (cand_r, cand_c), exit_cells
        )
        # Score prefers starts that can reach more exits and larger connected walkable space.
        score = (len(reachable_goals) * 100000) + len(reachable_set)
        info = {
            "r": cand_r,
            "c": cand_c,
            "reachable_goals": reachable_goals,
            "reachable_set": reachable_set,
            "score": score,
            "world": (cand_x, cand_y),
        }
        if best is None or info["score"] > best["score"]:
            best = info

    return best


def pick_best_reachable_toward_exits(reachable_set, exit_cells, start_cell):
    """Choose a trapped fallback cell that moves toward the closest exit frontier."""
    if not reachable_set:
        return start_cell
    if not exit_cells:
        return max(reachable_set, key=lambda rc: abs(rc[0] - start_cell[0]) + abs(rc[1] - start_cell[1]))

    # Prefer cells in reachable component that are closest to any exit candidate.
    def score(rc):
        to_exit = min(abs(rc[0] - g[0]) + abs(rc[1] - g[1]) for g in exit_cells)
        travel = abs(rc[0] - start_cell[0]) + abs(rc[1] - start_cell[1])
        return (to_exit, -travel)

    return min(reachable_set, key=score)


# ---------------------------------------------------------------------------
# Path optimisation & smoothing
# ---------------------------------------------------------------------------

def check_los(grid, p1, p2):
    """Bresenham line-of-sight check — returns False if any hard obstacle blocks."""
    r0, c0 = p1
    r1, c1 = p2
    dr = abs(r1 - r0); dc = abs(c1 - c0)
    sr = 1 if r0 < r1 else -1
    sc = 1 if c0 < c1 else -1
    err = dr - dc
    while True:
        if grid[r0][c0] == 2:
            return False
        if r0 == r1 and c0 == c1:
            break
        e2 = 2 * err
        if e2 > -dc: err -= dc; r0 += sr
        if e2 <  dr: err += dr; c0 += sc
    return True


def optimize_path_los(grid, path):
    """
    Pull path tight with line-of-sight shortcuts.
    Conservative: only skips waypoints when LOS is truly clear.
    """
    if len(path) < 3:
        return path

    optimized = [path[0]]
    curr_idx  = 0

    while curr_idx < len(path) - 1:
        best_next = curr_idx + 1          # Safe default: advance one step
        # Look ahead; skip as many intermediate cells as LOS allows
        for next_idx in range(len(path) - 1, curr_idx + 1, -1):
            if check_los(grid, path[curr_idx], path[next_idx]):
                best_next = next_idx
                break
        optimized.append(path[best_next])
        curr_idx = best_next

    return optimized


def smooth_path_coords(coords, passes=3):
    """Laplacian smoothing on world-space 3D coordinates."""
    if len(coords) < 3:
        return coords
    pts = list(coords)
    for _ in range(passes):
        new_pts = [pts[0]]
        for i in range(1, len(pts) - 1):
            avg_x = (pts[i-1][0] + pts[i+1][0]) / 2.0
            avg_y = (pts[i-1][1] + pts[i+1][1]) / 2.0
            new_pts.append(((pts[i][0]+avg_x)/2.0,
                            (pts[i][1]+avg_y)/2.0,
                             pts[i][2]))
        new_pts.append(pts[-1])
        pts = new_pts
    return pts


# ---------------------------------------------------------------------------
# Blender object creation
# ---------------------------------------------------------------------------

def create_path_visualization(path_world_coords, path_mat):
    """
    Build a NURBS tube along the path, convert to mesh, then assign material.
    The material is assigned AFTER conversion so it is not lost.
    """
    if len(path_world_coords) < 2:
        return

    curve_data              = bpy.data.curves.new(name="EvacPath", type='CURVE')
    curve_data.dimensions   = '3D'
    curve_data.bevel_depth  = 0.12       # Tube radius
    curve_data.bevel_resolution = 6

    spline = curve_data.splines.new('NURBS')
    spline.points.add(len(path_world_coords) - 1)
    for i, (x, y, z) in enumerate(path_world_coords):
        spline.points[i].co = (x, y, z, 1)
    spline.use_endpoint_u = True

    curve_obj = bpy.data.objects.new("EvacuationPath", curve_data)
    bpy.context.collection.objects.link(curve_obj)

    # Select & make active for conversion
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = curve_obj
    curve_obj.select_set(True)
    bpy.ops.object.convert(target='MESH')

    # Re-assign material AFTER conversion (conversion resets material slots)
    mesh_obj = bpy.context.active_object
    if mesh_obj.data.materials:
        mesh_obj.data.materials[0] = path_mat
    else:
        mesh_obj.data.materials.append(path_mat)


def create_marker(location, mat, radius=0.25):
    """Add a UV sphere marker with the given emission material."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=location)
    obj = bpy.context.active_object
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    return obj


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_glb(output_path):
    """Export the full scene to a GLB file."""
    for obj in bpy.data.objects:
        obj.hide_set(False)
        try:
            obj.select_set(True)
        except Exception:
            pass

    try:
        bpy.ops.export_scene.gltf(
            filepath=output_path,
            export_format='GLB',
            use_selection=False,
            export_materials='EXPORT',
            export_colors=True,
        )
        print(f"Exported GLB to: {output_path}")
    except Exception as e:
        print(f"Export failed: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    params = parse_args()
    if not params:
        print("ERROR: No arguments provided.")
        sys.exit(1)

    blend_path  = params["blend_path"]
    output_path = params["output_path"]
    start_x     = params["start_x"]
    start_y     = params["start_y"]
    dest_x      = params["dest_x"]
    dest_y      = params["dest_y"]
    algo        = params.get("algo", "astar")

    # --- Load scene ---
    if blend_path.lower().endswith('.glb'):
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()
        bpy.ops.import_scene.gltf(filepath=blend_path)
    else:
        bpy.ops.wm.open_mainfile(filepath=blend_path)

    bpy.context.view_layer.update()

    # --- Build grid and retry with coarser resolutions for hard scenarios ---
    resolution_candidates = [0.20, 0.26, 0.32]
    chosen = None

    for res in resolution_candidates:
        trial_grid, trial_rows, trial_cols, trial_min_x, trial_min_y, trial_resolution, trial_exits = \
            build_navigable_grid(resolution=res)

        trial_start = choose_best_start_candidate(
            trial_grid,
            trial_rows,
            trial_cols,
            trial_min_x,
            trial_min_y,
            trial_resolution,
            start_x,
            start_y,
            trial_exits,
        )
        trial_start_r = trial_start["r"]
        trial_start_c = trial_start["c"]

        if dest_x is not None and dest_y is not None:
            trial_dest_r = int((dest_y - trial_min_y) / trial_resolution)
            trial_dest_c = int((dest_x - trial_min_x) / trial_resolution)
            trial_dest_r, trial_dest_c = snap_to_walkable_cell(trial_grid, trial_rows, trial_cols, trial_dest_r, trial_dest_c)
            trial_exits = [(trial_dest_r, trial_dest_c)]

        trial_reachable_goals, trial_reachable_set = find_reachable_exits(
            trial_grid, trial_rows, trial_cols, (trial_start_r, trial_start_c), trial_exits
        )

        trial_score = len(trial_reachable_goals) * 100000 + len(trial_reachable_set)
        print(
            "DEBUG: Grid trial",
            f"res={trial_resolution}",
            f"start=({trial_start_r},{trial_start_c})",
            f"reachable_exits={len(trial_reachable_goals)}",
            f"reachable_cells={len(trial_reachable_set)}",
        )

        if chosen is None or trial_score > chosen["score"]:
            chosen = {
                "score": trial_score,
                "grid": trial_grid,
                "rows": trial_rows,
                "cols": trial_cols,
                "min_x": trial_min_x,
                "min_y": trial_min_y,
                "resolution": trial_resolution,
                "start_r": trial_start_r,
                "start_c": trial_start_c,
                "exit_cells": trial_exits,
                "reachable_goals": trial_reachable_goals,
                "reachable_set": trial_reachable_set,
                "start_world": trial_start["world"],
            }

        # Early stop when a healthy configuration is found.
        if len(trial_reachable_goals) > 0 and len(trial_reachable_set) > 80:
            break

    grid = chosen["grid"]
    rows = chosen["rows"]
    cols = chosen["cols"]
    min_x = chosen["min_x"]
    min_y = chosen["min_y"]
    resolution = chosen["resolution"]
    start_r = chosen["start_r"]
    start_c = chosen["start_c"]
    exit_cells = chosen["exit_cells"]
    reachable_goals = chosen["reachable_goals"]
    reachable_set = chosen["reachable_set"]

    print(
        "DEBUG: Start candidate chosen",
        f"world={chosen['start_world']} grid=({start_r}, {start_c})",
        f"reachable_exits={len(reachable_goals)}",
        f"reachable_cells={len(reachable_set)}",
        f"grid_res={resolution}",
    )

    is_trapped  = False
    route_mode = algo
    fallback_used = False
    final_goals = reachable_goals

    if not reachable_goals:
        is_trapped = True
        print("WARNING: No reachable exits found — TRAPPED scenario.")
        if reachable_set:
            toward_exit = pick_best_reachable_toward_exits(reachable_set, exit_cells, (start_r, start_c))
            final_goals = [toward_exit]
        else:
            final_goals = exit_cells

    # --- Pathfinding ---
    if is_trapped:
        # Explicit emergency route so users can still understand a way out.
        if not final_goals:
            final_goals = exit_cells if exit_cells else [(start_r, start_c)]
        path_cells = astar_breakout(grid, rows, cols, (start_r, start_c), final_goals)
        route_mode = "emergency_breakout"
        fallback_used = True
    elif algo == "qlearning":
        baseline_astar = astar(grid, rows, cols, (start_r, start_c), final_goals)
        baseline_ok = path_reaches_goal(baseline_astar, final_goals)
        safety_map = build_safety_map(grid, rows, cols)
        train_starts = list(reachable_set) if reachable_set else [(start_r, start_c)]
        attempts = [30000, 42000, 56000]
        path_cells = [(start_r, start_c)]
        for idx, episodes in enumerate(attempts):
            agent = QLearningAgent(
                grid,
                rows,
                cols,
                (start_r, start_c),
                final_goals,
                safety_map=safety_map,
                train_starts=train_starts,
                epsilon=0.22 if idx > 0 else 0.18,
            )
            agent.train(episodes=episodes)
            candidate_path = agent.get_optimal_path()
            if len(candidate_path) > len(path_cells):
                path_cells = candidate_path
            if path_reaches_goal(candidate_path, final_goals):
                path_cells = candidate_path
                break

        q_ok = path_reaches_goal(path_cells, final_goals)
        if baseline_ok:
            # If Q-learning route is degenerate or not competitive, use shortest deterministic route.
            q_cost = path_cost(grid, path_cells)
            a_cost = path_cost(grid, baseline_astar)
            if (not q_ok) or len(path_cells) < 3 or q_cost > 1.12 * a_cost or q_cost < 0.35 * a_cost:
                print("ML STATUS: Using A* shortest route (Q-learning not reliable for this map).")
                path_cells = baseline_astar
                q_ok = True
                route_mode = "astar_shortest_fallback"
                fallback_used = True

        if not q_ok:
            print("ML STATUS: Q-learning could not reach an exit; trying deterministic rescue fallback.")
            rescue_path = astar(grid, rows, cols, (start_r, start_c), final_goals)
            if rescue_path and len(rescue_path) > len(path_cells):
                path_cells = rescue_path
            route_mode = "astar_rescue"
            fallback_used = True

            # If still degenerate, force a visible two-point route toward nearest candidate.
            if len(path_cells) < 2 and final_goals:
                nearest_goal = min(final_goals, key=lambda g: abs(g[0] - start_r) + abs(g[1] - start_c))
                if nearest_goal != (start_r, start_c):
                    path_cells = [(start_r, start_c), nearest_goal]
            print(f"ML STATUS: Rescue path length = {len(path_cells)}")
    else:
        # Keep for backward compatibility when explicit API requests astar.
        path_cells = astar(grid, rows, cols, (start_r, start_c), final_goals)
        route_mode = "astar"

    print(f"DEBUG: Raw path length = {len(path_cells)}")
    print(f"DEBUG: start={path_cells[:1]}  end={path_cells[-1:]}  trapped={is_trapped}")

    # --- Optimise & smooth ---
    # For Q-learning safety mode, avoid aggressive LOS shortcutting.
    optimized_cells = path_cells if algo == "qlearning" else optimize_path_los(grid, path_cells)
    path_height     = 0.35
    path_world      = [(min_x + c*resolution, min_y + r*resolution, path_height)
                       for r, c in optimized_cells]
    path_world      = smooth_path_coords(path_world, passes=1 if algo == "qlearning" else 3)

    # --- Choose materials based on trapped state ---
    if is_trapped:
        path_mat = create_trapped_path_material()
        exit_mat = create_trapped_exit_material()
    else:
        path_mat = create_path_material()
        exit_mat = create_exit_material()

    # --- Visualise ---
    if path_world:
        create_path_visualization(path_world, path_mat)
        create_marker(path_world[0],  path_mat, radius=0.20)   # Start — red/orange sphere
        create_marker(path_world[-1], exit_mat, radius=0.30)   # Exit  — yellow sphere

    # --- Export ---
    export_glb(output_path)

    # --- Diagnostics metadata for API/UI transparency ---
    meta_path = output_path + ".pathmeta.json"
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "route_mode": route_mode,
                    "fallback_used": fallback_used,
                    "trapped": is_trapped,
                    "path_length": len(path_cells),
                    "optimized_length": len(optimized_cells),
                    "reachable_exit_count": len(reachable_goals),
                    "candidate_exit_count": len(exit_cells),
                    "chosen_grid_resolution": resolution,
                    "start_cell": [start_r, start_c],
                    "end_cell": list(path_cells[-1]) if path_cells else [start_r, start_c],
                },
                f,
                indent=2,
            )
    except Exception as e:
        print(f"WARNING: Could not write path diagnostics metadata: {e}")

    sys.exit(0)


if __name__ == "__main__":
    main()