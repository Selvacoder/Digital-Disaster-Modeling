from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from subprocess import check_output, CalledProcessError
import shutil
import os
import sys
import uuid
import configparser

# Add root directory to path to import core logic
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(ROOT_DIR)
# Set CWD to root for library path resolution
os.chdir(ROOT_DIR)

from FloorplanToBlenderLib import IO, execution, config, floorplan, const

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../Images/Uploads"))
TARGET_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../Target"))
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(TARGET_DIR, exist_ok=True)

def get_blender_path():
    # Try current system.ini first
    try:
        path = config.get(const.SYSTEM_CONFIG_FILE_NAME, "SYSTEM", "blender_installation_path").replace('"', "")
        if os.path.isfile(path):
            return path
    except:
        pass
    
    # Fallback to auto-detection
    auto_path = IO.blender_installed()
    if auto_path:
        return auto_path
    
    return shutil.which("blender")

def create_blender_project(data_paths, target_folder_name, wall_height):
    blender_install_path = get_blender_path()
    if not blender_install_path:
        raise Exception("Blender not found. Please set path in Configs/system.ini")

    program_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    blender_script_path = os.path.join(program_path, const.BLENDER_SCRIPT_PATH)
    
    target_base_rel = os.path.join("Target", target_folder_name)
    target_path_rel = "/" + target_base_rel.replace("\\", "/") + const.BASE_FORMAT
    
    # Generate data (ensure uniqueness if needed, but here we use the filename-based folder)
    
    target_base_abs = os.path.join(TARGET_DIR, target_folder_name)
    target_path_abs = target_base_abs + const.BASE_FORMAT
    
    try:
        # Import generator here to update its height property globally
        from FloorplanToBlenderLib import generator
        generator.Generator.height = wall_height
        const.WALL_HEIGHT = wall_height

        # 1. Create .blend project
        check_output(
            [
                blender_install_path,
                "-noaudio",
                "--background",
                "--python",
                blender_script_path,
                program_path,
                target_path_rel,
            ]
            + data_paths
        )
        
        # 2. Export to OBJ for web viewing
        obj_path_abs = target_base_abs + ".obj"
        check_output(
            [
                blender_install_path,
                "-noaudio",
                "--background",
                "--python",
                os.path.join(program_path, "Blender/blender_export_any.py"),
                target_path_abs,
                ".obj",
                obj_path_abs
            ]
        )
        
        return obj_path_abs
    except CalledProcessError as e:
        print(f"Blender error: {e.output.decode() if e.output else str(e)}")
        raise e

@app.get("/")
async def root():
    return {"message": "2D Blueprint to 3D Model API is running"}

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    file_extension = os.path.splitext(file.filename)[1]
    unique_id = str(uuid.uuid4())
    unique_filename = f"{unique_id}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"filename": unique_filename, "id": unique_id}

@app.post("/convert")
async def convert_blueprint(
    filename: str = Form(...), 
    wall_height: float = Form(2.5), 
    pixel_scale: float = Form(100.0),
    generate_walls: bool = Form(True),
    generate_floors: bool = Form(True),
    generate_rooms: bool = Form(True),
    generate_details: bool = Form(True)
):
    image_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    unique_id = os.path.splitext(filename)[0]
    
    try:
        # Sync core library wall height and pixel scale
        from FloorplanToBlenderLib import generator
        generator.Generator.height = wall_height
        generator.Generator.pixelscale = pixel_scale
        const.WALL_HEIGHT = wall_height 
        const.PIXEL_TO_3D_SCALE = pixel_scale
        
        fp = floorplan.new_floorplan("./Configs/default.ini")
        fp.image_path = image_path
        
        # Apply toggles
        fp.walls = generate_walls
        fp.floors = generate_floors
        fp.rooms = generate_rooms
        fp.windows = generate_details
        fp.doors = generate_details
        
        # 1. Generate local vertex/face data
        data_path = execution.simple_single(fp)
        
        # 2. Trigger Blender to build project and export OBJ
        obj_path = create_blender_project([data_path], unique_id, wall_height)
        
        import time
        cache_buster = int(time.time())
        return {
            "status": "success",
            "model_url": f"/target/{unique_id}.obj?t={cache_buster}",
            "blend_url": f"/target/{unique_id}.blend?t={cache_buster}"
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Static mounts
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/target", StaticFiles(directory=TARGET_DIR), name="target")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
