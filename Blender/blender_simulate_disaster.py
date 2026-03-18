"""
Blender Disaster Simulation Script
Runs headlessly via Blender CLI to apply visual disaster effects to a 3D floorplan model.

Usage:
    blender -noaudio --background --python blender_simulate_disaster.py -- \
        <blend_path> <output_obj_path> <disaster_type> [param=value ...]

Disaster Types & Effects:
    fire:       Emissive orange/red materials on rooms, particle-like fire spheres
    flood:      Blue translucent water plane at specified height, blue-tinted lower rooms
    earthquake: Vertex displacement on walls, cracked material colors
"""

import bpy
import sys
import os
import random
import math
import json
import mathutils


def parse_args():
    """Parse arguments after '--' separator."""
    argv = sys.argv
    if "--" not in argv:
        return {}
    args = argv[argv.index("--") + 1:]
    params = {
        "blend_path": args[0],
        "output_path": args[1],
        "disaster_type": args[2],
    }
    # Parse key=value pairs
    for arg in args[3:]:
        if "=" in arg:
            key, val = arg.split("=", 1)
            try:
                params[key] = float(val)
            except ValueError:
                params[key] = val
    return params


def create_emission_material(name, color, strength=5.0):
    """Create a glowing emission material."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = color
    emission.inputs["Strength"].default_value = strength
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return mat


def create_solid_material(name, color):
    """Create a simple solid-color material."""
    mat = bpy.data.materials.new(name=name)
    mat.diffuse_color = color
    return mat


def create_transparent_material(name, color, alpha=0.4):
    """Create a transparent material for flood water."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    mat.blend_method = 'BLEND' if hasattr(mat, 'blend_method') else None
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.inputs["Base Color"].default_value = color
    principled.inputs["Alpha"].default_value = alpha
    # Try to set roughness low for a glassy water look
    principled.inputs["Roughness"].default_value = 0.1
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    return mat


def get_all_mesh_objects():
    """Get all mesh objects in the scene."""
    return [obj for obj in bpy.data.objects if obj.type == 'MESH']


def get_object_center(obj):
    """Get world-space center of an object."""
    return obj.matrix_world @ obj.location


def get_bounding_box(obj):
    """Get world-space bounding box of an object."""
    bbox = [obj.matrix_world @ bpy.mathutils.Vector(corner) if hasattr(bpy, 'mathutils') else corner
            for corner in obj.bound_box]
    return bbox


def simulate_fire(params):
    """Apply realistic fire spread and smoke."""
    wind_speed = params.get("wind_speed", 15)
    
    fire_mat = create_emission_material("FireMat", (1.0, 0.4, 0.1, 1.0), 10.0)
    char_mat = create_solid_material("CharredMat", (0.05, 0.05, 0.05, 1.0))
    smoke_mat = create_transparent_material("SmokeMat", (0.2, 0.2, 0.2, 1.0), 0.6)

    meshes = get_all_mesh_objects()
    if not meshes: return

    # Simple spread: pick 2 random sources and affect neighbors
    sources = random.sample(meshes, min(2, len(meshes)))
    affected = set(sources)
    
    # Expand 1-2 generations based on wind
    for _ in range(int(1 + wind_speed / 20)):
        new_affected = set()
        for obj in affected:
            for other in meshes:
                if other not in affected and (obj.location - other.location).length < 4.0:
                    new_affected.add(other)
        affected.update(new_affected)

    for obj in meshes:
        if obj in affected:
            obj.data.materials.clear()
            obj.data.materials.append(fire_mat if random.random() > 0.4 else char_mat)
            
            # Add smoke particles
            for i in range(3):
                offset = mathutils.Vector((random.uniform(-1,1), random.uniform(-1,1), 2.0))
                bpy.ops.mesh.primitive_uv_sphere_add(radius=0.4, location=obj.location + offset)
                smoke = bpy.context.active_object
                smoke.data.materials.append(smoke_mat)


def simulate_flood(params):
    """Apply flood with water surface and debris."""
    water_level = params.get("water_level", 1.0)
    
    water_mat = create_transparent_material("WaterMat", (0.1, 0.4, 0.9, 1.0), 0.5)
    debris_mat = create_solid_material("DebrisMat", (0.4, 0.2, 0.1, 1.0))

    meshes = get_all_mesh_objects()
    if not meshes: return

    # Water plane
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, water_level))
    water = bpy.context.active_object
    water.scale = (5, 5, 1)
    water.data.materials.append(water_mat)

    # Add floating debris
    for i in range(15):
        loc = (random.uniform(-5, 5), random.uniform(-5, 5), water_level + random.uniform(-0.1, 0.1))
        bpy.ops.mesh.primitive_cube_add(size=0.2, location=loc)
        deb = bpy.context.active_object
        deb.rotation_euler = (random.random(), random.random(), random.random())
        deb.data.materials.append(debris_mat)


def simulate_earthquake(params):
    """Apply earthquake fracturing and rubble."""
    magnitude = params.get("magnitude", 6.0)
    
    rubble_mat = create_solid_material("RubbleMat", (0.3, 0.3, 0.3, 1.0))
    
    meshes = get_all_mesh_objects()
    for obj in meshes:
        if "wall" in obj.name.lower():
            # Jitter vertices slightly for fracturing look
            for v in obj.data.vertices:
                jitter = mathutils.Vector((random.uniform(-0.1, 0.1), random.uniform(-0.1, 0.1), 0)) * (magnitude/5)
                v.co += jitter
            
            if random.random() > 0.7:
                obj.rotation_euler.x += random.uniform(-0.1, 0.1)
                
    # Add rubble heaps
    for i in range(10):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.2, location=(random.uniform(-5,5), random.uniform(-5,5), 0.1))
        rub = bpy.context.active_object
        rub.scale = (1, 1, 0.5)
        rub.data.materials.append(rubble_mat)


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
            bpy.ops.export_scene.obj(
                filepath=output_path,
                use_selection=False,
                use_mesh_modifiers=True,
                use_materials=True,
                use_triangles=True,
                axis_forward='-Z',
                axis_up='Y'
            )
    except Exception as e:
        print(f"Export failed with primary method: {e}")
        # Final fallback
        bpy.ops.export_scene.obj(filepath=output_path)


def log(msg):
    print(msg)
    sys.stdout.flush()

def main():
    try:
        log("Starting simulation script...")
        params = parse_args()
        if not params:
            log("ERROR: No arguments provided")
            sys.exit(1)

        blend_path = params["blend_path"]
        output_path = params["output_path"]
        disaster_type = params["disaster_type"]

        if not os.path.exists(blend_path):
            log(f"ERROR: Blend file not found: {blend_path}")
            sys.exit(1)

        log(f"Opening blend file: {blend_path}")
        bpy.ops.wm.open_mainfile(filepath=blend_path)

        log(f"Running simulation: {disaster_type}")
        if disaster_type == "fire":
            simulate_fire(params)
        elif disaster_type == "flood":
            simulate_flood(params)
        elif disaster_type == "earthquake":
            simulate_earthquake(params)
        else:
            log(f"ERROR: Unknown disaster type: {disaster_type}")
            sys.exit(1)

        log(f"Exporting to: {output_path}")
        export_obj(output_path)
        
        if os.path.exists(output_path):
            log("SUCCESS: Simulation complete and file exported.")
        else:
            log("ERROR: Export finished but file missing!")
            sys.exit(1)
            
        sys.exit(0)
    except Exception as e:
        import traceback
        log("CRITICAL ERROR IN BLENDER SCRIPT:")
        log(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
