import bpy
import os
import sys


if __name__ == "__main__":
    argv = sys.argv

    if "--" in argv:
        script_args = argv[argv.index("--") + 1 :]
    else:
        script_args = argv[5:]

    if len(script_args) < 3:
        raise SystemExit("Expected input_path, format, output_path")

    input_path = script_args[0]
    bpy.ops.wm.open_mainfile(filepath=input_path)

    format = script_args[1]
    output_path = script_args[2]

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
    elif format == ".gltf" or format == ".glb":
        bpy.ops.export_scene.gltf(
            filepath=output_path,
            export_format='GLB' if format == '.glb' else 'GLTF_SEPARATE',
            use_selection=False,
            export_materials='EXPORT'
        )
    elif format == ".x3d":
        bpy.ops.export_scene.x3d(filepath=output_path)
    elif format == ".blend":
        bpy.ops.wm.save_as_mainfile(filepath=output_path)
    else:
        # default
        bpy.ops.export_scene.obj(filepath=output_path)

    # Must exit with 0 to avoid error!
    exit(0)
