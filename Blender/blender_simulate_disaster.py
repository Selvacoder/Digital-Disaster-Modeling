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


def create_pbr_material(name, color, roughness=0.75, metallic=0.05, emission=None, emission_strength=0.0):
    """Create a principled material with optional emission for fire damage stages."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.inputs["Base Color"].default_value = color
    principled.inputs["Roughness"].default_value = roughness
    principled.inputs["Metallic"].default_value = metallic
    if emission is not None:
        # Blender socket naming differs across versions:
        # - 3.6: "Emission"
        # - 4.x: "Emission Color"
        if "Emission Color" in principled.inputs:
            principled.inputs["Emission Color"].default_value = emission
        elif "Emission" in principled.inputs:
            principled.inputs["Emission"].default_value = emission

        if "Emission Strength" in principled.inputs:
            principled.inputs["Emission Strength"].default_value = emission_strength

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


def create_smoke_material(name, alpha=0.18):
    """Create a soft dark transparent material for smoke puffs."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    if hasattr(mat, 'blend_method'):
        mat.blend_method = 'BLEND'
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.inputs["Base Color"].default_value = (0.06, 0.06, 0.07, 1.0)
    principled.inputs["Alpha"].default_value = alpha
    principled.inputs["Roughness"].default_value = 0.95
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    return mat


def get_all_mesh_objects():
    """Get all mesh objects in the scene."""
    return [obj for obj in bpy.data.objects if obj.type == 'MESH']


def get_object_center(obj):
    """Get world-space geometric center of an object from its bounding box."""
    world_bbox = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
    center = mathutils.Vector((0.0, 0.0, 0.0))
    for v in world_bbox:
        center += v
    return center / max(1, len(world_bbox))


def get_object_base_z(obj):
    """Get the lowest world-space Z coordinate of an object's bounding box."""
    world_bbox = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
    return min(v.z for v in world_bbox)


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
    """Apply center-origin fire spread with full-model coverage, burn stages, and collapse."""
    wind_speed = float(params.get("wind_speed", 15.0))
    ambient_temp = float(params.get("ambient_temp", 25.0))

    meshes = get_all_mesh_objects()
    if not meshes:
        return

    min_v, max_v = get_scene_bounds(meshes)
    diag, xy_extent = get_scene_scale(meshes)
    floor_z = float(min_v.z) if min_v is not None else 0.0

    # Fire behavior controls tuned for realism.
    base_intensity = max(0.35, min(1.65, 0.45 + ambient_temp / 75.0 + wind_speed / 140.0))
    spread_radius = max(1.0, xy_extent * (0.16 + wind_speed / 420.0))
    radial_extent = max(1.0, xy_extent * 0.46)
    scene_center = mathutils.Vector(((min_v.x + max_v.x) * 0.5, (min_v.y + max_v.y) * 0.5, floor_z))
    max_center_dist = max(1.0, xy_extent * 0.72)

    # Pseudo-time spread progress: high heat/wind pushes the front farther, faster.
    spread_progress = min(1.0, 0.42 + 0.26 * base_intensity + wind_speed / 240.0)

    # Materials representing progressive burn stages.
    soot_mat = create_pbr_material("FireSootMat", (0.24, 0.20, 0.18, 1.0), roughness=0.88, metallic=0.02)
    char_mat = create_pbr_material("FireCharMat", (0.12, 0.09, 0.08, 1.0), roughness=0.95, metallic=0.03)
    ember_mat = create_pbr_material(
        "FireEmberMat",
        (0.16, 0.10, 0.08, 1.0),
        roughness=0.82,
        metallic=0.03,
        emission=(0.95, 0.28, 0.08, 1.0),
        emission_strength=1.6,
    )

    # Center-origin ignition sources avoid one-side bias and create global spread.
    src_count = 4
    source_centers = []
    for idx in range(src_count):
        angle = (idx / src_count) * math.tau + random.uniform(-0.2, 0.2)
        ring = xy_extent * random.uniform(0.03, 0.11)
        source_centers.append(
            mathutils.Vector(
                (
                    scene_center.x + math.cos(angle) * ring,
                    scene_center.y + math.sin(angle) * ring,
                    floor_z + random.uniform(0.05, 0.2),
                )
            )
        )

    # Wind direction drives asymmetric spread.
    theta = random.uniform(0, math.tau)
    wind_dir = mathutils.Vector((math.cos(theta), math.sin(theta), 0.0)).normalized()

    debris_budget = 0

    for obj in meshes:
        name = obj.name.lower()
        center = get_object_center(obj)

        # Compute damage score with center radial propagation plus source hotspots.
        score = 0.0
        for src in source_centers:
            vec = center - src
            dist = max(0.01, vec.length)
            proximity = math.exp(-dist / spread_radius)

            horizontal = mathutils.Vector((vec.x, vec.y, 0.0))
            if horizontal.length > 1e-6:
                horizontal.normalize()
                downwind = max(0.0, horizontal.dot(wind_dir))
            else:
                downwind = 0.0

            wind_boost = 1.0 + downwind * (wind_speed / 60.0)
            height_damp = 1.0 - max(0.0, min(0.35, (center.z - floor_z) / max(1.0, diag) * 0.8))
            local = proximity * wind_boost * height_damp
            if local > score:
                score = local

        center_vec = mathutils.Vector((center.x - scene_center.x, center.y - scene_center.y, 0.0))
        center_dist = center_vec.length
        radial = math.exp(-center_dist / radial_extent)
        dist_norm = min(1.0, center_dist / max_center_dist)

        # Outer rooms ignite later: delay ramps from center to perimeter.
        delay_start = max(0.0, dist_norm - 0.22)
        delay_band = 0.32
        delay_ratio = max(0.0, min(1.0, (spread_progress - delay_start) / max(1e-6, delay_band)))
        ignition_delay = delay_ratio * delay_ratio * (3.0 - 2.0 * delay_ratio)

        center_boost = 1.0 + 0.55 * (1.0 - dist_norm)
        baseline = (0.05 + 0.28 * radial * center_boost) * ignition_delay

        score = max(score * base_intensity, baseline * base_intensity)
        score = min(score, 1.35)

        # Apply burn-stage material by damage score.
        if score > 0.08 and any(k in name for k in ("wall", "room", "floor", "door", "window")):
            obj.data.materials.clear()
            if score > 0.78:
                obj.data.materials.append(ember_mat)
            elif score > 0.42:
                obj.data.materials.append(char_mat)
            else:
                obj.data.materials.append(soot_mat)

        # Structural deformation for heavily damaged structures.
        if score > 0.52 and any(k in name for k in ("wall", "room")):
            settle = (0.02 + 0.08 * min(1.0, score)) * (0.9 + 0.1 * radial)
            base_z = get_object_base_z(obj)
            max_sink = max(0.0, (base_z - floor_z) - 0.02)
            obj.location.z = max(floor_z, obj.location.z - min(settle, max_sink))
            # Keep damage visually strong but avoid directional side collapse artifacts.
            obj.rotation_euler.z += random.uniform(-0.03, 0.03) * min(1.0, score)

        # Debris near severely damaged structural elements.
        if score > 0.62 and debris_budget < 70 and min_v is not None:
            for _ in range(2):
                offset = mathutils.Vector((random.uniform(-1, 1), random.uniform(-1, 1), 0.0)) * max(0.35, diag * 0.03)
                bpy.ops.mesh.primitive_cube_add(
                    size=max(0.16, diag * 0.008),
                    location=(center.x + offset.x, center.y + offset.y, floor_z + 0.08),
                )
                debris = bpy.context.active_object
                debris.scale = (
                    random.uniform(0.7, 2.6),
                    random.uniform(0.3, 1.4),
                    random.uniform(0.2, 0.8),
                )
                debris.rotation_euler = (
                    random.uniform(0, math.pi),
                    random.uniform(0, math.pi),
                    random.uniform(0, math.pi),
                )
                debris.data.materials.append(char_mat)
                debris_budget += 1


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
    """Apply magnitude/depth-driven earthquake shaking, cracking, and debris."""
    magnitude = float(params.get("magnitude", 6.0))
    depth = float(params.get("depth", 10.0))
    
    rubble_mat = create_solid_material("RubbleMat", (0.3, 0.3, 0.3, 1.0))
    cracked_mat = create_solid_material("CrackedMat", (0.2, 0.2, 0.25, 1.0))
    
    meshes = get_all_mesh_objects()
    if not meshes:
        return

    min_v, max_v = get_scene_bounds(meshes)
    if min_v is None or max_v is None:
        return

    diag, xy_extent = get_scene_scale(meshes)
    center = mathutils.Vector(((min_v.x + max_v.x) * 0.5, (min_v.y + max_v.y) * 0.5, min_v.z))

    mag_norm = max(0.0, min(1.0, (magnitude - 4.0) / 4.5))
    depth_factor = math.exp(-max(0.0, depth - 5.0) / 22.0)
    quake_power = max(0.15, min(1.35, 0.2 + 1.15 * mag_norm * (0.55 + 0.45 * depth_factor)))
    major_damage_threshold = 0.5 + 0.25 * (1.0 - quake_power)

    # Fault-like directional bands create realistic uneven shaking zones.
    fault_count = 2 if quake_power < 0.9 else 3
    fault_data = []
    for _ in range(fault_count):
        angle = random.uniform(0.0, math.tau)
        direction = mathutils.Vector((math.cos(angle), math.sin(angle), 0.0)).normalized()
        shift = mathutils.Vector(
            (
                random.uniform(-0.2, 0.2) * xy_extent,
                random.uniform(-0.2, 0.2) * xy_extent,
                0.0,
            )
        )
        band_center = center + shift
        band_width = max(0.7, xy_extent * random.uniform(0.06, 0.14))
        fault_data.append((direction, band_center, band_width))

    structural_meshes = []

    for obj in meshes:
        if not ("wall" in obj.name.lower() or "room" in obj.name.lower() or "door" in obj.name.lower()):
            continue

        structural_meshes.append(obj)

        world_center = get_object_center(obj)
        cxy = mathutils.Vector((world_center.x, world_center.y, 0.0))
        center_dist = (cxy - mathutils.Vector((center.x, center.y, 0.0))).length
        radial_damage = math.exp(-center_dist / max(1.0, xy_extent * 0.45))

        fault_damage = 0.0
        for direction, band_center, band_width in fault_data:
            rel = cxy - mathutils.Vector((band_center.x, band_center.y, 0.0))
            normal = mathutils.Vector((-direction.y, direction.x, 0.0))
            dist_to_fault = abs(rel.dot(normal))
            influence = math.exp(-(dist_to_fault ** 2) / (2.0 * (band_width ** 2)))
            fault_damage = max(fault_damage, influence)

        local_damage = quake_power * (0.45 * radial_damage + 0.75 * fault_damage)
        if local_damage < 0.14:
            continue

        rot_amp = 0.01 + 0.04 * local_damage
        shift_amp = (0.02 + 0.12 * local_damage) * (diag / max(1.0, xy_extent + 0.001))

        # Keep roll/pitch subtle so the building does not collapse to one side.
        obj.rotation_euler.x += random.uniform(-rot_amp, rot_amp) * 0.08
        obj.rotation_euler.y += random.uniform(-rot_amp, rot_amp) * 0.08
        obj.rotation_euler.z += random.uniform(-0.07, 0.07) * local_damage
        obj.location.x += random.uniform(-shift_amp, shift_amp)
        obj.location.y += random.uniform(-shift_amp, shift_amp)

        sink = random.uniform(0.0, 0.04) * local_damage
        base_z = get_object_base_z(obj)
        max_sink = max(0.0, (base_z - min_v.z) - 0.02)
        obj.location.z = max(min_v.z, obj.location.z - min(sink, max_sink))

        if local_damage >= 0.32:
            obj.data.materials.clear()
            obj.data.materials.append(cracked_mat)

    rubble_count = int(18 + 52 * quake_power)
    for _ in range(rubble_count):
        fault_pick = random.choice(fault_data)
        direction, band_center, band_width = fault_pick
        t = random.uniform(-0.55, 0.55) * xy_extent
        normal = mathutils.Vector((-direction.y, direction.x, 0.0))
        side = random.uniform(-1.0, 1.0)

        base_xy = mathutils.Vector((band_center.x, band_center.y, 0.0)) + direction * t + normal * side * band_width * 0.9
        x = max(min_v.x, min(max_v.x, base_xy.x))
        y = max(min_v.y, min(max_v.y, base_xy.y))

        size = max(0.08, diag * random.uniform(0.006, 0.018) * (0.7 + 0.7 * quake_power))
        z = float(min_v.z + size * random.uniform(0.8, 1.6))

        if random.random() < 0.65:
            bpy.ops.mesh.primitive_cube_add(size=size, location=(x, y, z))
        else:
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=size * 0.8, location=(x, y, z))

        rub = bpy.context.active_object
        rub.scale = (
            random.uniform(0.5, 2.4),
            random.uniform(0.4, 1.9),
            random.uniform(0.2, 1.0),
        )
        rub.rotation_euler = (
            random.uniform(0, math.pi),
            random.uniform(0, math.pi),
            random.uniform(0, math.pi),
        )
        rub.data.materials.append(rubble_mat)

    if quake_power > major_damage_threshold:
        severe_objs = [o for o in meshes if ("wall" in o.name.lower() or "room" in o.name.lower())]
        random.shuffle(severe_objs)
        for obj in severe_objs[: max(3, int(len(severe_objs) * 0.12))]:
            # Avoid large roll/pitch in major damage stage; keep readable but stable geometry.
            obj.rotation_euler.z += random.uniform(-0.08, 0.08)
            sink = random.uniform(0.03, 0.12)
            base_z = get_object_base_z(obj)
            max_sink = max(0.0, (base_z - min_v.z) - 0.02)
            obj.location.z = max(min_v.z, obj.location.z - min(sink, max_sink))
            obj.data.materials.clear()
            obj.data.materials.append(cracked_mat)

    # Final stabilization: clamp residual roll/pitch and keep structural meshes above floor.
    for obj in structural_meshes:
        obj.rotation_euler.x = max(-0.035, min(0.035, obj.rotation_euler.x))
        obj.rotation_euler.y = max(-0.035, min(0.035, obj.rotation_euler.y))
        base_z = get_object_base_z(obj)
        if base_z < min_v.z:
            obj.location.z += (min_v.z - base_z)


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
            export_materials='EXPORT'
        )
    except Exception as e:
        raise RuntimeError(f"Export failed: {e}")


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
