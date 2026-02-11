import bpy
import os
import sys


if __name__ == "__main__":
    argv = sys.argv

    input_path = argv[5]
    bpy.ops.wm.open_mainfile(filepath=input_path)

    format = argv[6]
    output_path = argv[
        7
    ]  # strict argc==5 -> len=6 will be used as argument see Reformat_blender_to_obj.py

    if format == ".obj":
        # Ensure focus on all objects
        for obj in bpy.data.objects:
            obj.hide_set(False)
            obj.select_set(True)
        
        # Use common export settings to include everything
        # Set Up to Y and Forward to -Z for standard Web/Three.js orientation
        bpy.ops.export_scene.obj(
            filepath=output_path,
            use_selection=False,
            use_mesh_modifiers=True,
            use_materials=True,
            use_triangles=True,
            axis_forward='-Z',
            axis_up='Y'
        )
    elif format == ".fbx":
        bpy.ops.export_scene.fbx(filepath=output_path)
    elif format == ".gltf":
        bpy.ops.export_scene.gltf(filepath=output_path)
    elif format == ".x3d":
        bpy.ops.export_scene.x3d(filepath=output_path)
    elif format == ".blend":
        bpy.ops.wm.save_as_mainfile(filepath=output_path)
    else:
        # default
        bpy.ops.export_scene.obj(filepath=output_path)

    # Must exit with 0 to avoid error!
    exit(0)
