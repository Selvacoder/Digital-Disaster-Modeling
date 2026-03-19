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
    """Create a principled solid-color material."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.inputs["Base Color"].default_value = color
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])
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
    return [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]


def get_scene_bounds(meshes):
    """
    Compute world-space AABB for a list of mesh objects.
    Returns (min_vec, max_vec). If empty, returns (None, None).
    """
    if not meshes:
        return None, None

    min_v = mathutils.Vector((float("inf"), float("inf"), float("inf")))
    max_v = mathutils.Vector((float("-inf"), float("-inf"), float("-inf")))
    for obj in meshes:
        for corner in obj.bound_box:
            v = obj.matrix_world @ mathutils.Vector(corner)
            min_v.x = min(min_v.x, v.x)
            min_v.y = min(min_v.y, v.y)
            min_v.z = min(min_v.z, v.z)
            max_v.x = max(max_v.x, v.x)
            max_v.y = max(max_v.y, v.y)
            max_v.z = max(max_v.z, v.z)
    return min_v, max_v


def get_scene_scale(meshes):
    """Return (diag_len, xy_extent_len) derived from world-space bounds."""
    min_v, max_v = get_scene_bounds(meshes)
    if min_v is None or max_v is None:
        return 1.0, 1.0
    diag = (max_v - min_v).length
    xy_extent = mathutils.Vector((max_v.x - min_v.x, max_v.y - min_v.y, 0.0)).length
    return max(diag, 1e-6), max(xy_extent, 1e-6)


def simulate_fire(params):
    """Apply realistic post-fire structural damage."""
    wind_speed = params.get("wind_speed", 15)
    
    # Realistic scorched, dark brownish-grey material for fire damage
    # (0.2, 0.15, 0.15) looks like burnt wood/plaster, unlike flat black which looks like a rendering error.
    burnt_mat = create_solid_material("BurntMat", (0.2, 0.15, 0.15, 1.0))

    meshes = get_all_mesh_objects()
    if not meshes: return

    diag, _xy = get_scene_scale(meshes)
    neighbor_radius = max(1.0, diag * 0.1)  

    sources = random.sample(meshes, min(2, len(meshes)))
    affected = set(sources)
    
    for _ in range(int(1 + wind_speed / 15)):
        new_affected = set()
        for obj in affected:
            for other in meshes:
                if other not in affected and (obj.location - other.location).length < neighbor_radius:
                    new_affected.add(other)
        affected.update(new_affected)

    min_v, max_v = get_scene_bounds(meshes)

    for obj in meshes:
        if obj in affected:
            # We add severe structural damage
            if ("wall" in obj.name.lower() or "room" in obj.name.lower()):
                
                # Turn the walls into a scorched/burnt color!
                obj.data.materials.clear()
                obj.data.materials.append(burnt_mat)
                
                if random.random() > 0.4:
                    obj.location.z -= random.uniform(0, min(0.3, obj.location.z))
                    obj.rotation_euler.x += random.uniform(-0.15, 0.15)
                    obj.rotation_euler.y += random.uniform(-0.15, 0.15)
                    obj.rotation_euler.z += random.uniform(-0.05, 0.05)
                
            # Add scattered burnt debris blocks (like fallen roof beams)
            if "floor" in obj.name.lower() or "room" in obj.name.lower():
                for i in range(3):
                    if min_v is None: break
                    offset = mathutils.Vector(
                        (random.uniform(-1, 1), random.uniform(-1, 1), 0.0)
                    ) * max(0.5, diag * 0.05)
                    
                    bpy.ops.mesh.primitive_cube_add(
                        size=max(0.2, diag * 0.01), 
                        location=(obj.location.x + offset.x, obj.location.y + offset.y, float(min_v.z) + 0.1)
                    )
                    debris = bpy.context.active_object
                    debris.scale = (random.uniform(1.0, 4.0), random.uniform(0.5, 1.5), random.uniform(0.2, 0.6))
                    debris.rotation_euler = (random.uniform(0, 3.14), random.uniform(0, 3.14), random.uniform(0, 3.14))
                    debris.data.materials.append(burnt_mat)


def simulate_flood(params):
    """Apply muddy flood water with realistic messy debris."""
    water_level = params.get("water_level", 1.0)
    
    # Using a slightly more opaque, realistic blue/cyan transparent water
    water_mat = create_transparent_material("WaterMat", (0.1, 0.45, 0.75, 1.0), 0.8)
    debris_mat = create_solid_material("DebrisMat", (0.35, 0.25, 0.15, 1.0))
    plank_mat = create_solid_material("PlankMat", (0.45, 0.3, 0.2, 1.0))

    meshes = get_all_mesh_objects()
    if not meshes: return

    min_v, max_v = get_scene_bounds(meshes)
    if min_v is None or max_v is None:
        return

    # Interpret water_level as meters ABOVE the model's floor (min Z)
    z = float(min_v.z + water_level)

    # The frontend ground plane is 200x200, so we make the water plane 250x250 to cover everything
    sx = 250.0
    sy = 250.0
    cx = (min_v.x + max_v.x) * 0.5
    cy = (min_v.y + max_v.y) * 0.5

    # Use a highly subdivided grid for ripples across the massive ocean
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=100, y_subdivisions=100, size=1.0, location=(cx, cy, z))
    water = bpy.context.active_object
    # Scale exactly by sx and sy because size=1.0 is a 1x1 unit square
    water.scale = (sx, sy, 1)
    
    # Add wavy displacement to flood surface (gentler ripples)
    for v in water.data.vertices:
        v.co.z += random.uniform(-0.02, 0.02)
    water.data.update()
    
    # Enable smooth shading so the grid polygons blend into a smooth glassy water surface
    bpy.ops.object.shade_smooth()
        
    water.data.materials.append(water_mat)

    # Add floating planks and debris chunks
    deb_margin = max(2.0, (max_v - min_v).length * 0.1)
    for i in range(40):
        loc = (
            random.uniform(min_v.x - deb_margin, max_v.x + deb_margin),
            random.uniform(min_v.y - deb_margin, max_v.y + deb_margin),
            z + random.uniform(-0.02, 0.03),
        )
        bpy.ops.mesh.primitive_cube_add(size=0.3, location=loc)
        deb = bpy.context.active_object
        
        # 50% chance of making it look like a floating wooden plank
        if random.random() > 0.5:
            deb.scale = (random.uniform(1.0, 3.0), random.uniform(0.2, 0.5), random.uniform(0.05, 0.1))
            deb.data.materials.append(plank_mat)
        else: # Or just a chunk of irregular junk
            deb.scale = (random.uniform(0.5, 1.0), random.uniform(0.5, 1.0), random.uniform(0.5, 1.0))
            deb.data.materials.append(debris_mat)
            
        deb.rotation_euler = (random.uniform(-0.2, 0.2), random.uniform(-0.2, 0.2), random.uniform(0, 3.14))


def simulate_earthquake(params):
    """Apply earthquake fracturing and rubble."""
    magnitude = params.get("magnitude", 6.0)
    
    rubble_mat = create_solid_material("RubbleMat", (0.3, 0.3, 0.3, 1.0))
    cracked_mat = create_solid_material("CrackedMat", (0.2, 0.2, 0.25, 1.0))
    
    meshes = get_all_mesh_objects()
    if not meshes: return
    
    diag, _xy = get_scene_scale(meshes)

    for obj in meshes:
        if "wall" in obj.name.lower() or "room" in obj.name.lower():
            rand_val = random.random()
            
            # Massive collapse effect (Object level, not vertex level)
            if rand_val > 0.6:
                # Tilt and collapse
                obj.rotation_euler.x += random.uniform(-0.15, 0.15)
                obj.rotation_euler.y += random.uniform(-0.15, 0.15)
                obj.rotation_euler.z += random.uniform(-0.1, 0.1)
                
                # Shift, but do not sink below ground
                obj.location.x += random.uniform(-0.2, 0.2)
                obj.location.y += random.uniform(-0.2, 0.2)
                # Sink slightly, but bounded to not go through floor
                obj.location.z -= random.uniform(0, min(0.2, obj.location.z))
                
            if rand_val > 0.4:
                # Apply cracked material to simulating burnt/damaged structures
                obj.data.materials.clear()
                obj.data.materials.append(cracked_mat)
                
    # Add scattered jagged rubble (no perfect spheres)
    min_v, max_v = get_scene_bounds(meshes)
    if min_v is not None and max_v is not None:
        for i in range(35):
            radius = max(0.3, diag * 0.015)
            scale_z = random.uniform(0.2, 0.8)
            
            # Ensure the rubble rests ON the floor instead of penetrating below it
            z_offset = radius * scale_z + random.uniform(0.01, 0.5)
            
            # Use icosphere with low subdivisions for a jagged, rocky look
            bpy.ops.mesh.primitive_ico_sphere_add(
                subdivisions=1,
                radius=radius,
                location=(
                    random.uniform(min_v.x, max_v.x),
                    random.uniform(min_v.y, max_v.y),
                    float(min_v.z + z_offset),
                ),
            )
            rub = bpy.context.active_object
            # Scale unevenly to form long or flat rocks
            rub.scale = (random.uniform(0.5, 2.0), random.uniform(0.5, 2.0), scale_z)
            rub.rotation_euler = (random.uniform(0, 3.14), random.uniform(0, 3.14), random.uniform(0, 3.14))
            rub.data.materials.append(rubble_mat)


def export_glb(output_path):
    """Export the scene to GLB format."""
    # Ensure all objects are visible and selected
    for obj in bpy.data.objects:
        obj.hide_set(False)
        try:
            obj.select_set(True)
        except:
            pass

    try:
        bpy.ops.export_scene.gltf(
            filepath=output_path,
            export_format='GLB',
            use_selection=False,
            export_materials='EXPORT',
            export_colors=True
        )
    except Exception as e:
        print(f"Export failed: {e}")


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
        export_glb(output_path)
        
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
