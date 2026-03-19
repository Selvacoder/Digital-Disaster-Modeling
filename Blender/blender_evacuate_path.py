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
        "algo": args[6] if len(args) > 6 else "astar"
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
                grid[r][c] = 1          # Outside the building — walkable
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
                        grid[r][c] = 2
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

    # --- Locate exit cells from named door/window objects ---
    exit_cells   = []
    door_keywords = ["door", "window", "entry", "gate", "doorway", "opening"]
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and any(k in obj.name.lower() for k in door_keywords):
            wc = obj.matrix_world @ obj.location
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

    # --- Fallback: perimeter cells if no door objects found ---
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

        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            nr, nc = r + dr, c + dc
            if (0 <= nr < rows and 0 <= nc < cols
                    and grid[nr][nc] in (1, 3)
                    and (nr, nc) not in visited):
                visited.add((nr, nc))
                queue.append((nr, nc))

    return reachable, visited


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


class QLearningAgent:
    """Q-Learning agent for grid pathfinding (alternative to A*)."""
    def __init__(self, grid, rows, cols, start, goals,
                 alpha=0.3, gamma=0.9, epsilon=0.1):
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

    def get_q_values(self, state):
        if state not in self.q_table:
            self.q_table[state] = [0.0] * len(self.actions)
        return self.q_table[state]

    def get_heuristic(self, state):
        if not self.goals: return 0
        return min(abs(state[0]-gr)+abs(state[1]-gc) for gr, gc in self.goals)

    def choose_action(self, state):
        if random.random() < self.epsilon:
            return random.randint(0, len(self.actions)-1)
        q = self.get_q_values(state)
        mx = max(q)
        return random.choice([i for i,v in enumerate(q) if v == mx])

    def train(self, episodes=5000):
        print(f"ML STATUS: Q-Learning training for {episodes} episodes…")
        for ep in range(episodes):
            state = self.start
            steps = 0
            while state not in self.goals and steps < 1200:
                idx  = self.choose_action(state)
                dr, dc = self.actions[idx]
                ns   = (state[0]+dr, state[1]+dc)

                if not (0 <= ns[0] < self.rows and 0 <= ns[1] < self.cols):
                    reward, ts = -25, state
                elif self.grid[ns[0]][ns[1]] == 2:
                    reward, ts = -40, state
                else:
                    if ns in self.goals:
                        reward = 1000
                    else:
                        shaping = (self.get_heuristic(state)-self.get_heuristic(ns))*0.5
                        reward  = -1 + shaping
                        if self.grid[ns[0]][ns[1]] == 3:
                            reward -= 2.0
                    ts = ns

                old_q  = self.get_q_values(state)[idx]
                next_max = max(self.get_q_values(ts))
                self.q_table[state][idx] = old_q + self.alpha*(reward+self.gamma*next_max-old_q)
                state = ts
                steps += 1

            if ep == 10000: self.epsilon = 0.05
            if ep == 30000: self.epsilon = 0.02
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
            if max(q) == 0: break
            idx    = q.index(max(q))
            dr, dc = self.actions[idx]
            state  = (state[0]+dr, state[1]+dc)
            if state in visited: break
            path.append(state)
            visited.add(state)
            steps += 1
        return path


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

    # --- Build grid ---
    grid, rows, cols, min_x, min_y, resolution, exit_cells = \
        build_navigable_grid(resolution=0.15)

    # --- Snap start to walkable cell ---
    start_r = int((start_y - min_y) / resolution)
    start_c = int((start_x - min_x) / resolution)
    start_r = max(0, min(rows-1, start_r))
    start_c = max(0, min(cols-1, start_c))

    if grid[start_r][start_c] not in (1, 3):
        found = False
        for dist in range(1, 20):
            for dr in range(-dist, dist+1):
                for dc in range(-dist, dist+1):
                    nr, nc = start_r+dr, start_c+dc
                    if (0 <= nr < rows and 0 <= nc < cols
                            and grid[nr][nc] in (1, 3)):
                        start_r, start_c = nr, nc
                        found = True
                        break
                if found: break
            if found: break
        print(f"DEBUG: Snapped start → ({start_r}, {start_c})")

    # --- Override exit with explicit destination if provided ---
    if dest_x is not None and dest_y is not None:
        dest_r = int((dest_y - min_y) / resolution)
        dest_c = int((dest_x - min_x) / resolution)
        exit_cells = [(dest_r, dest_c)]

    # --- Filter to reachable exits ---
    reachable_goals, reachable_set = find_reachable_exits(
        grid, rows, cols, (start_r, start_c), exit_cells)

    is_trapped  = False
    final_goals = reachable_goals

    if not reachable_goals:
        is_trapped = True
        print("WARNING: No reachable exits found — TRAPPED scenario.")
        if reachable_set:
            sorted_r = sorted(
                list(reachable_set),
                key=lambda x: abs(x[0]-start_r)+abs(x[1]-start_c),
                reverse=True)
            final_goals = [sorted_r[0]]
        else:
            final_goals = exit_cells

    # --- Pathfinding ---
    if algo == "qlearning":
        agent = QLearningAgent(grid, rows, cols, (start_r, start_c), final_goals)
        agent.train(episodes=40000)
        path_cells = agent.get_optimal_path()
    else:
        path_cells = astar(grid, rows, cols, (start_r, start_c), final_goals)

    print(f"DEBUG: Raw path length = {len(path_cells)}")
    print(f"DEBUG: start={path_cells[:1]}  end={path_cells[-1:]}  trapped={is_trapped}")

    # --- Optimise & smooth ---
    optimized_cells = optimize_path_los(grid, path_cells)
    path_height     = 0.35
    path_world      = [(min_x + c*resolution, min_y + r*resolution, path_height)
                       for r, c in optimized_cells]
    path_world      = smooth_path_coords(path_world, passes=3)

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
    sys.exit(0)


if __name__ == "__main__":
    main()