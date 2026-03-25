"""
Blender Q-Learning Evacuation Path Optimizer
Generates optimal evacuation paths using ML-trained Q-Learning model.

Usage:
    blender -noaudio --background --python blender_qlearning_evacuate.py -- \
        <blend_path> <output_obj_path> <start_x> <start_y> <model_path>

Features:
    - Q-Learning based pathfinding (learns from disaster scenarios)
    - Considers disaster proximity and spread
    - Multiple training episodes for robustness
    - Visualization with emission materials
"""

import bpy
import sys
import os
import json
import math


# Try to import ML modules
try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from FloorplanToBlenderLib.qlearning_pathfinder import QLearningPathfinder
    from FloorplanToBlenderLib.building_analyzer import BuildingAnalyzer
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("Warning: ML modules not available. Falling back to basic pathfinding.")


def parse_args():
    """Parse command line arguments."""
    argv = sys.argv
    if "--" not in argv:
        return {}
    
    args = argv[argv.index("--") + 1:]
    return {
        "blend_path": args[0],
        "output_path": args[1],
        "start_x": float(args[2]),
        "start_y": float(args[3]),
        "model_path": args[4] if len(args) > 4 else "Models/qlearning_model.pkl",
        "disaster_type": args[5] if len(args) > 5 else "fire",
        "disaster_intensity": float(args[6]) if len(args) > 6 else 70.0,
    }


def make_emission_material(name, color_rgba, strength=10.0):
    """Create glowing emission material."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = color_rgba
    emission.inputs["Strength"].default_value = strength
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return mat


def create_path_material():
    """Green emission for Q-Learning optimal path."""
    return make_emission_material("QLearningPathMaterial", (0.0, 1.0, 0.2, 1.0), strength=10.0)


def create_exit_material():
    """Blue emission for exit markers."""
    return make_emission_material("ExitMarkerMaterial", (0.1, 0.5, 1.0, 1.0), strength=5.0)


def get_scene_bounds():
    """Get XY bounds of all mesh objects."""
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
    Build navigable grid using raycasting.
    Grid values: 0=unvisited/obstacle, 1=walkable, 2=hazard
    """
    min_x, max_x, min_y, max_y = get_scene_bounds()

    min_x -= 1; min_y -= 1
    max_x += 1; max_y += 1

    cols = int((max_x - min_x) / resolution) + 1
    rows = int((max_y - min_y) / resolution) + 1
    grid = [[0] * cols for _ in range(rows)]

    scene = bpy.context.scene
    depsgraph = scene.view_layers[0].depsgraph

    for r in range(rows):
        for c in range(cols):
            wx = min_x + c * resolution
            wy = min_y + r * resolution

            # Vertical downward ray to detect floor
            origin = (wx, wy, 1.0)
            hit, loc, norm, index, obj, matrix = scene.ray_cast(depsgraph, origin, (0, 0, -1))

            if not hit:
                grid[r][c] = 1  # Outside = walkable
            elif loc.z <= 0.25:
                grid[r][c] = 1  # Floor level = walkable
            else:
                grid[r][c] = 2  # Elevated = obstacle

    return grid, (min_x, max_x, min_y, max_y)


def find_exit_positions(resolution=0.5):
    """Identify exit positions from the scene."""
    exits = []
    
    for obj in bpy.data.objects:
        if 'exit' in obj.name.lower() or 'door' in obj.name.lower():
            exits.append((obj.location.x, obj.location.y))
    
    # If no explicit exits found, use scene boundaries
    if not exits:
        min_x, max_x, min_y, max_y = get_scene_bounds()
        exits = [
            (min_x + 1, min_y + 1),
            (max_x - 1, max_y - 1),
            (min_x + 1, max_y - 1),
            (max_x - 1, min_y + 1)
        ]
    
    return exits


def create_path_visualization(path, path_material, grid_bounds):
    """Create visible tube along evacuation path."""
    if len(path) < 2:
        return None
    
    radius = 0.2
    
    # Create curve for smooth path
    curve_data = bpy.data.curves.new(name="EvacuationPath", type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.resolution_u = 12
    
    polyline = curve_data.splines.new('BEZIER')
    polyline.points.add(len(path) - 1)
    
    for i, (x, y) in enumerate(path):
        polyline.points[i].co = (x, y, 0.5, 1)
    
    # Create object
    curve_obj = bpy.data.objects.new("EvacPath_Curve", curve_data)
    bpy.context.collection.objects.link(curve_obj)
    
    # Convert to mesh
    bpy.context.view_layer.objects.active = curve_obj
    bpy.ops.object.convert(target='MESH')
    
    # Apply material
    if len(curve_obj.data.materials) == 0:
        curve_obj.data.materials.append(path_material)
    else:
        curve_obj.data.materials[0] = path_material
    
    return curve_obj


def save_output(filename):
    """Export scene to OBJ format."""
    bpy.ops.wm.save_as_mainfile(filepath=filename + ".blend")
    bpy.ops.export_scene.obj(filepath=filename + ".obj", use_materials=True)


def main():
    args = parse_args()
    
    if not args:
        print("Error: No arguments provided")
        return
    
    blend_path = args["blend_path"]
    output_path = args["output_path"]
    start_x = args["start_x"]
    start_y = args["start_y"]
    
    print(f"Q-Learning Evacuation Path Optimizer")
    print(f"  Input: {blend_path}")
    print(f"  Start: ({start_x}, {start_y})")
    print(f"  Output: {output_path}")
    
    # Load blend file
    if os.path.exists(blend_path):
        bpy.ops.wm.open_mainfile(filepath=blend_path)
        print("  ✓ Blend file loaded")
    
    # Build navigation grid
    print("\n[Step 1] Building navigation grid...")
    grid, grid_bounds = build_navigable_grid(resolution=0.5)
    print(f"  ✓ Grid created: {len(grid)}x{len(grid[0])}")
    
    # Find exits
    print("\n[Step 2] Identifying exit positions...")
    exits = find_exit_positions()
    print(f"  ✓ Found {len(exits)} exits: {exits[:2]}...")
    
    # Use Q-Learning if available
    optimal_path = None
    
    if ML_AVAILABLE:
        try:
            print("\n[Step 3] Using Q-Learning Path Optimizer...")
            
            # Initialize Q-Learner
            qlearner = QLearningPathfinder(
                grid_resolution=0.5,
                learning_rate=0.1,
                discount_factor=0.9,
                epsilon=0.1
            )
            
            # Try to load pre-trained model
            model_path = args.get("model_path", "Models/qlearning_model.pkl")
            if os.path.exists(model_path):
                qlearner.load_model(model_path)
                print(f"  ✓ Loaded trained model: {model_path}")
            else:
                # Quick training
                print("  Training Q-Learning model (50 episodes)...")
                disaster_zones = [(start_x, start_y, 5, 80)]
                qlearner.train_episodes(
                    building_grid=grid,
                    disaster_zones=disaster_zones,
                    exit_positions=exits,
                    start_positions=[(start_x, start_y)],
                    num_episodes=50
                )
                print("  ✓ Model trained")
            
            # Find optimal path
            if exits:
                nearest_exit = min(exits, key=lambda e: 
                    ((start_x - e[0])**2 + (start_y - e[1])**2)**0.5)
                disaster_zones = [(start_x, start_y, 5, args.get("disaster_intensity", 70))]
                
                optimal_path = qlearner.find_path(grid, (start_x, start_y), 
                                                  nearest_exit, disaster_zones)
                print(f"  ✓ Optimal path found with {len(optimal_path)} waypoints")
                
        except Exception as e:
            print(f"  ✗ Q-Learning error: {e}")
            print("    Falling back to simple pathfinding...")
    
    else:
        print("\n[Step 3] ML modules not available, using simple pathfinding...")
    
    # Fallback: simple straight-line path
    if not optimal_path and exits:
        nearest_exit = min(exits, key=lambda e: 
            ((start_x - e[0])**2 + (start_y - e[1])**2)**0.5)
        # Simple interpolation
        steps = 50
        optimal_path = [(
            start_x + i * (nearest_exit[0] - start_x) / steps,
            start_y + i * (nearest_exit[1] - start_y) / steps
        ) for i in range(steps + 1)]
        print(f"  Using linear path with {len(optimal_path)} waypoints")
    
    # Visualize path
    if optimal_path:
        print("\n[Step 4] Creating path visualization...")
        path_material = create_path_material()
        path_obj = create_path_visualization(optimal_path, path_material, grid_bounds)
        print("  ✓ Path visualization created")
    
    # Save output
    print("\n[Step 5] Saving output...")
    save_output(output_path)
    print(f"  ✓ Output saved to {output_path}")
    
    # Print path summary
    print("\nPath Summary:")
    print(f"  Start: ({optimal_path[0][0]:.2f}, {optimal_path[0][1]:.2f})")
    print(f"  End: ({optimal_path[-1][0]:.2f}, {optimal_path[-1][1]:.2f})")
    print(f"  Total waypoints: {len(optimal_path)}")
    
    # Export to JSON
    path_json = output_path + "_path.json"
    with open(path_json, 'w') as f:
        json.dump({
            'path': optimal_path,
            'start': [start_x, start_y],
            'method': 'q_learning' if ML_AVAILABLE else 'linear',
            'disaster_type': args.get("disaster_type", "fire"),
            'disaster_intensity': args.get("disaster_intensity", 70)
        }, f, indent=2)
    print(f"  Path data saved to {path_json}")


if __name__ == "__main__":
    main()
