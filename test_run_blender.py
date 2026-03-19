import subprocess

blender_exe = r"D:\SteamLibrary\steamapps\common\Blender\blender.exe"
script = r"Blender/blender_simulate_disaster.py"
blend_file = r"Target/2241e491-dcd1-405a-bf88-742e3d8f9fae.blend"
out_file = r"Target/test_sim.glb"
cmd = [blender_exe, "-noaudio", "--background", "--python", script, "--", blend_file, out_file, "fire"]

res = subprocess.run(cmd, capture_output=True, text=True)
print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)
print("RC:", res.returncode)
