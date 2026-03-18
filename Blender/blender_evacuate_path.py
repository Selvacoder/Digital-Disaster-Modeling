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
    }


def create_path_material():
    """Create a bright green material for the evacuation path."""
    mat = bpy.data.materials.new(name="EvacPathMaterial")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (0.1, 1.0, 0.2, 1.0)  # Bright green
    emission.inputs["Strength"].default_value = 3.0
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return mat


def create_exit_material():
    """Create a pulsing yellow material for exit markers."""
    mat = bpy.data.materials.new(name="ExitMarkerMaterial")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (1.0, 0.9, 0.1, 1.0)  # Yellow
    emission.inputs["Strength"].default_value = 5.0
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return mat


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
    """
    min_x, max_x, min_y, max_y = get_scene_bounds()
    
    min_x -= 1
    min_y -= 1
    max_x += 1
    max_y += 1
    
    cols = int((max_x - min_x) / resolution) + 1
    rows = int((max_y - min_y) / resolution) + 1
    grid = [[0] * cols for _ in range(rows)]
    
    walkable_names = ["floor", "room", "ground", "surface"]
    obstacle_names = ["wall", "pillar", "column", "box", "vert"]
    
    scene = bpy.context.scene
    depsgraph = scene.view_layers[0].depsgraph
    
    for r in range(rows):
        for c in range(cols):
            wx = min_x + c * resolution
            wy = min_y + r * resolution
            
            # 1. Check for floor (raycast down)
            origin = (wx, wy, 5.0)
            hit, loc, norm, index, obj, matrix = scene.ray_cast(depsgraph, origin, (0, 0, -1))
            
            if hit:
                if any(kw in obj.name.lower() for kw in walkable_names):
                    grid[r][c] = 1 # Walkable
            
            # 2. Check for walls at ankle height
            if grid[r][c] == 1:
                origin_wall = (wx, wy, 0.5)
                for dx, dy in [(0.1, 0), (-0.1, 0), (0, 0.1), (0, -0.1)]:
                    hit_w, loc_w, norm_w, idx_w, obj_w, mat_w = scene.ray_cast(
                        depsgraph, origin_wall, (dx, dy, 0), distance=resolution*0.8)
                    if hit_w and any(kw in obj_w.name.lower() for kw in obstacle_names):
                        grid[r][c] = 2 # Obstacle
                        break

    exit_cells = []
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and ("door" in obj.name.lower() or "window" in obj.name.lower()):
            wc = obj.matrix_world @ obj.location
            er = int((wc.y - min_y) / resolution)
            ec = int((wc.x - min_x) / resolution)
            if 0 <= er < rows and 0 <= ec < cols:
                exit_cells.append((er, ec))
                grid[er][ec] = 1
    
    if not exit_cells:
        for r in range(rows):
            for c in range(cols):
                if grid[r][c] == 1:
                    if r <= 1 or r >= rows - 2 or c <= 1 or c >= cols - 2:
                        exit_cells.append((r, c))

    return grid, rows, cols, min_x, min_y, resolution, exit_cells


def astar(grid, rows, cols, start, goals):
    """A* pathfinding from start to nearest goal."""
    sr, sc = start
    sr = max(0, min(rows - 1, sr))
    sc = max(0, min(cols - 1, sc))
    
    if grid[sr][sc] != 1:
        best = None
        best_dist = float('inf')
        for r in range(rows):
            for c in range(cols):
                if grid[r][c] == 1:
                    dist = abs(r - sr) + abs(c - sc)
                    if dist < best_dist:
                        best_dist = dist
                        best = (r, c)
        if best: sr, sc = best

    goal_set = set(goals)
    open_set = [(0, 0, sr, sc)]
    came_from = {}
    g_score = {(sr, sc): 0}
    
    def h(r, c):
        return min(abs(r - gr) + abs(c - gc) for gr, gc in goals) if goals else 0
    
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
    
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
            if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 1:
                move_cost = 1.414 if (dr != 0 and dc != 0) else 1.0
                new_g = g + move_cost
                if (nr, nc) not in g_score or new_g < g_score[(nr, nc)]:
                    g_score[(nr, nc)] = new_g
                    heapq.heappush(open_set, (new_g + h(nr, nc), new_g, nr, nc))
                    came_from[(nr, nc)] = (cr, cc)
    
    if goals:
        nearest = min(goals, key=lambda g: abs(g[0] - sr) + abs(g[1] - sc))
        return [(sr, sc), nearest]
    return [(sr, sc)]


def create_path_visualization(path_world_coords, path_mat):
    """Create a 3D tube and convert to mesh."""
    if len(path_world_coords) < 2: return
    curve_data = bpy.data.curves.new(name="EvacPath", type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.bevel_depth = 0.1
    curve_data.bevel_resolution = 4
    spline = curve_data.splines.new('NURBS')
    spline.points.add(len(path_world_coords) - 1)
    for i, (x, y, z) in enumerate(path_world_coords):
        spline.points[i].co = (x, y, z, 1)
    spline.use_endpoint_u = True
    curve_obj = bpy.data.objects.new("EvacuationPath", curve_data)
    bpy.context.collection.objects.link(curve_obj)
    bpy.context.view_layer.objects.active = curve_obj
    curve_obj.select_set(True)
    bpy.ops.object.convert(target='MESH')
    curve_obj.data.materials.append(path_mat)


def create_markers(start_world, exit_world, path_mat, exit_mat):
    """Create start and exit markers."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.25, location=start_world)
    bpy.context.active_object.data.materials.append(path_mat)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.3, location=exit_world)
    bpy.context.active_object.data.materials.append(exit_mat)


def export_obj(output_path):
    """Export the scene to OBJ using the most compatible operator."""
    # Ensure all objects are visible and selected
    for obj in bpy.data.objects:
        obj.hide_set(False)
        try:
            obj.select_set(True)
        except:
            pass

    try:
        # Try new OBJ-IO (3.0+)
        if hasattr(bpy.ops.wm, "obj_export"):
            bpy.ops.wm.obj_export(filepath=output_path, forward_axis='NEGATIVE_Z', up_axis='Y')
        else:
            bpy.ops.export_scene.obj(filepath=output_path, axis_forward='-Z', axis_up='Y')
    except Exception as e:
        print(f"Export failed with primary method: {e}")
        # Final fallback
        bpy.ops.export_scene.obj(filepath=output_path)


def main():
    params = parse_args()
    if not params: exit(1)
    blend_path, output_path = params["blend_path"], params["output_path"]
    start_x, start_y = params["start_x"], params["start_y"]

    bpy.ops.wm.open_mainfile(filepath=blend_path)
    grid, rows, cols, min_x, min_y, resolution, exit_cells = build_navigable_grid(resolution=0.4)
    start_r, start_c = int((start_y - min_y) / resolution), int((start_x - min_x) / resolution)
    path_cells = astar(grid, rows, cols, (start_r, start_c), exit_cells)
    
    path_height = 0.3
    path_world = [(min_x + c * resolution, min_y + r * resolution, path_height) for r, c in path_cells]
    
    path_mat, exit_mat = create_path_material(), create_exit_material()
    if path_world:
        create_path_visualization(path_world, path_mat)
        create_markers(path_world[0], path_world[-1], path_mat, exit_mat)

    export_obj(output_path)
    exit(0)


if __name__ == "__main__":
    main()
