import subprocess

blender_exe = r"D:\SteamLibrary\steamapps\common\Blender\blender.exe"
script = r"Blender/blender_simulate_disaster.py"
blend_file = r"Target/2241e491-dcd1-405a-bf88-742e3d8f9fae.blend"
out_file = r"Target/test_sim.obj"
cmd = [blender_exe, "-noaudio", "--background", "--python", script, "--", blend_file, out_file, "fire"]

try:
    res = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, timeout=12)
    out = res
except subprocess.CalledProcessError as e:
    out = e.output
except Exception as e:
    out = str(e)

with open('blender_out.txt', 'w') as f:
    f.write(out)
