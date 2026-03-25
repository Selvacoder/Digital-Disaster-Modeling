from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from subprocess import check_output, CalledProcessError
import shutil
import os
import sys
import uuid
import configparser
import json
import math

# Add root directory to path to import core logic
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(ROOT_DIR)
# Set CWD to root for library path resolution
os.chdir(ROOT_DIR)

from FloorplanToBlenderLib import IO, execution, config, floorplan, const
from FloorplanToBlenderLib.damage_predictor import BuildingDamagePredictor

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

_damage_predictor = None


def get_damage_predictor():
    """Load RF damage model once; train a bootstrap model if no saved model exists."""
    global _damage_predictor
    if _damage_predictor is not None:
        return _damage_predictor

    predictor = BuildingDamagePredictor(n_trees=300)
    try:
        predictor.load_model()
        # Refresh old lightweight models with a stronger forest.
        loaded_trees = getattr(predictor.damage_classifier, "n_estimators", predictor.n_trees)
        if loaded_trees < 250:
            predictor = BuildingDamagePredictor(n_trees=300)
            predictor.train(generate_synthetic=True, n_synthetic=5000)
            predictor.save_model()
        else:
            # Quality probe: extreme scenarios should not collapse to very low severity.
            probe = predictor.predict_damage(
                area_width=6.0,
                area_depth=5.0,
                area_height=3.0,
                building_material="wood",
                distance_to_epicenter=2.0,
                fragility_index=0.85,
                wall_quality=0.45,
                num_openings=3,
                disaster_type="fire",
                disaster_intensity=90.0,
            )
            if probe.get("damage_severity", 0.0) < 45.0:
                predictor = BuildingDamagePredictor(n_trees=300)
                predictor.train(generate_synthetic=True, n_synthetic=5000)
                predictor.save_model()
    except Exception:
        predictor.train(generate_synthetic=True, n_synthetic=5000)
        predictor.save_model()
    _damage_predictor = predictor
    return _damage_predictor


def infer_disaster_intensity(disaster_type, wind_speed, ambient_temp, water_level, rainfall_rate, magnitude, depth):
    """Infer a normalized 0-100 intensity from simulation controls when not provided."""
    if disaster_type == "fire":
        ws = wind_speed if wind_speed is not None else 15.0
        at = ambient_temp if ambient_temp is not None else 25.0
        # Fire-load-inspired proxy: combines combustible heat potential and HRR trend.
        qc_proxy = max(0.0, 0.9 * at + 0.45 * ws)
        hrr_proxy = max(0.0, 0.7 * at + 0.85 * ws)
        growth_term = 0.18 * math.sqrt(max(0.0, ws * at))
        intensity = (0.55 * qc_proxy) + (0.45 * hrr_proxy) + growth_term - 8.0
        return max(0.0, min(100.0, intensity))
    if disaster_type == "flood":
        wl = water_level if water_level is not None else 1.5
        rr = rainfall_rate if rainfall_rate is not None else 20.0
        # Flood impact proxy W ~ depth and velocity, with return-period amplification.
        velocity_proxy = max(0.05, 0.08 * rr + 0.4 * wl)
        impact_w = wl * math.sqrt(1.0 + velocity_proxy * velocity_proxy)
        aep_proxy = max(0.005, min(0.98, 0.22 * math.exp(-0.35 * wl) + 0.18 * math.exp(-0.03 * rr)))
        return_period = min(500.0, 1.0 / aep_proxy)
        extreme_factor = min(1.0, math.log10(return_period + 1.0) / 2.7)
        intensity = (18.0 * wl) + (0.55 * rr) + (1.6 * impact_w) + (18.0 * extreme_factor) - 10.0
        return max(0.0, min(100.0, intensity))
    if disaster_type == "earthquake":
        mg = magnitude if magnitude is not None else 5.5
        dp = depth if depth is not None else 10.0

        # Magnitude bands requested by user with smooth interpolation.
        if mg < 2.0:
            base = 5.0
            upper = 14.0
            frac = max(0.0, min(1.0, mg / 2.0))
        elif mg < 3.0:
            base = 14.0
            upper = 24.0
            frac = mg - 2.0
        elif mg < 4.0:
            base = 24.0
            upper = 40.0
            frac = mg - 3.0
        elif mg < 5.0:
            base = 40.0
            upper = 55.0
            frac = mg - 4.0
        elif mg < 6.0:
            base = 55.0
            upper = 72.0
            frac = mg - 5.0
        elif mg < 7.0:
            base = 72.0
            upper = 88.0
            frac = mg - 6.0
        elif mg < 8.0:
            base = 88.0
            upper = 97.0
            frac = mg - 7.0
        else:
            base = 97.0
            upper = 100.0
            frac = min(1.0, mg - 8.0)

        depth_factor = max(0.75, min(1.1, 0.75 + 0.35 * math.exp(-max(0.0, dp - 8.0) / 18.0)))
        intensity = (base + (upper - base) * frac) * depth_factor
        return max(0.0, min(100.0, intensity))
    return 60.0


def compute_prediction_confidence(class_probabilities, damage_severity, disaster_intensity):
    """Calibrate confidence from class distribution, severity support, and scenario intensity."""
    probs_raw = [float(v) for v in class_probabilities.values()]
    probs_raw = [max(0.0, min(1.0, p)) for p in probs_raw]
    if not probs_raw:
        return 45.0

    total = sum(probs_raw)
    if total <= 1e-9:
        return 45.0

    probs = [p / total for p in probs_raw]
    probs.sort(reverse=True)
    top1 = probs[0]
    top2 = probs[1] if len(probs) > 1 else 0.0
    margin = max(0.0, top1 - top2)

    n = max(2, len(probs))
    entropy = -sum(p * math.log(max(p, 1e-12)) for p in probs) / math.log(n)
    certainty = max(0.0, min(1.0, 1.0 - entropy))

    sev_norm = max(0.0, min(1.0, float(damage_severity) / 100.0))
    int_norm = max(0.0, min(1.0, float(disaster_intensity) / 100.0))

    class_centers = {
        "No Damage": 8.0,
        "Minor": 25.0,
        "Moderate": 50.0,
        "Severe": 72.0,
        "Catastrophic": 92.0,
    }
    expected_sev = 0.0
    for cls, center in class_centers.items():
        expected_sev += float(class_probabilities.get(cls, 0.0)) * center
    agreement = max(0.0, 1.0 - abs(float(damage_severity) - expected_sev) / 60.0)

    score = (
        0.30 * top1
        + 0.26 * certainty
        + 0.20 * margin
        + 0.15 * agreement
        + 0.06 * sev_norm
        + 0.05 * int_norm
    )

    if int_norm >= 0.75 and sev_norm >= 0.55:
        score = max(score, 0.64 + 0.18 * (int_norm - 0.75))

    adaptive_min = 38.0 + 22.0 * int_norm + 10.0 * max(0.0, sev_norm - 0.5)
    confidence = max(adaptive_min, min(99.0, score * 100.0))

    return round(confidence, 2)


def build_area_profiles(total_area, room_count):
    """Create deterministic room-like area profiles from total building area."""
    room_count = max(1, room_count)
    weights = []
    for i in range(room_count):
        if i == 0:
            weights.append(2.2)  # living room
        elif i % 4 == 0:
            weights.append(1.6)  # kitchen/hall
        else:
            weights.append(1.2)  # bedrooms/others

    weight_sum = sum(weights)
    profiles = []
    for i in range(room_count):
        area = max(8.0, total_area * (weights[i] / weight_sum))
        width = max(2.0, (area * 1.25) ** 0.5)
        depth = max(2.0, area / width)
        height = 3.0 if i % 5 else 3.2
        profiles.append(
            {
                "name": f"Area-{i + 1}",
                "width": width,
                "depth": depth,
                "height": height,
                "distance": 2.0 + i * (18.0 / max(1, room_count - 1)),
                "openings": 1 + (i % 3),
                "area": area,
                "preview_x": float((i % 4) * 2.2),
                "preview_z": float((i // 4) * 2.2),
            }
        )
    return profiles


def _polygon_area_xy(vertices):
    """Compute polygon area on XY plane using shoelace formula."""
    if not vertices or len(vertices) < 3:
        return 0.0
    area2 = 0.0
    for i in range(len(vertices)):
        x1, y1 = vertices[i][0], vertices[i][1]
        x2, y2 = vertices[(i + 1) % len(vertices)][0], vertices[(i + 1) % len(vertices)][1]
        area2 += (x1 * y2) - (x2 * y1)
    return abs(area2) * 0.5


def _find_data_path_for_uploaded_file(filename):
    """Find generated Data/* folder matching an uploaded image filename."""
    data_root = os.path.join(ROOT_DIR, "Data")
    if not os.path.isdir(data_root):
        return None

    for folder in os.listdir(data_root):
        candidate = os.path.join(data_root, folder)
        transform_path = os.path.join(candidate, "transform.txt")
        if not os.path.isfile(transform_path):
            continue
        try:
            with open(transform_path, "r", encoding="utf-8") as f:
                transform = json.load(f)
            image_name = os.path.basename(transform.get("image_path", ""))
            if image_name == filename:
                origin_path = transform.get("origin_path") or transform.get("data_path")
                if origin_path:
                    origin_abs = os.path.join(ROOT_DIR, origin_path)
                    if os.path.isdir(origin_abs):
                        return origin_abs
                return candidate
        except Exception:
            continue

    return None


def build_area_profiles_from_real_model(filename):
    """Build area profiles from real detected room polygons in generated data."""
    data_path = _find_data_path_for_uploaded_file(filename)
    if not data_path:
        return []

    room_verts_path = os.path.join(data_path, "room_verts.txt")
    if not os.path.isfile(room_verts_path):
        return []

    try:
        with open(room_verts_path, "r", encoding="utf-8") as f:
            room_polygons = json.load(f)
    except Exception:
        return []

    raw_profiles = []
    for polygon in room_polygons:
        if not polygon or len(polygon) < 3:
            continue

        area = _polygon_area_xy(polygon)
        if area < 1.0:
            continue

        xs = [v[0] for v in polygon]
        ys = [v[1] for v in polygon]
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        width = max(xs) - min(xs)
        depth = max(ys) - min(ys)

        raw_profiles.append(
            {
                "area": area,
                "width": max(2.0, width),
                "depth": max(2.0, depth),
                "height": 3.0,
                "cx": cx,
                "cy": cy,
            }
        )

    if not raw_profiles:
        return []

    # Use model centroid as a deterministic disaster center proxy for distance feature.
    model_cx = sum(p["cx"] for p in raw_profiles) / len(raw_profiles)
    model_cy = sum(p["cy"] for p in raw_profiles) / len(raw_profiles)

    # Sort by area descending for stable Area-1..N labels.
    raw_profiles.sort(key=lambda p: p["area"], reverse=True)

    profiles = []
    for idx, p in enumerate(raw_profiles):
        dx = p["cx"] - model_cx
        dy = p["cy"] - model_cy
        distance = (dx * dx + dy * dy) ** 0.5

        profiles.append(
            {
                "name": f"Area-{idx + 1}",
                "width": p["width"],
                "depth": p["depth"],
                "height": p["height"],
                "distance": max(0.5, distance),
                "openings": 2,
                "area": p["area"],
                "preview_x": p["cx"],
                "preview_z": p["cy"],
            }
        )

    return profiles

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
        
        # 2. Export to GLB for web viewing
        glb_path_abs = target_base_abs + ".glb"
        check_output(
            [
                blender_install_path,
                "-noaudio",
                "--background",
                "--python",
                os.path.join(program_path, "Blender/blender_export_any.py"),
                target_path_abs,
                ".glb",
                glb_path_abs
            ]
        )
        
        return glb_path_abs
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
        
        # 2. Trigger Blender to build project and export GLB
        glb_path = create_blender_project([data_path], unique_id, wall_height)
        
        import time
        cache_buster = int(time.time())
        return {
            "status": "success",
            "model_url": f"/target/{unique_id}.glb?t={cache_buster}",
            "blend_url": f"/target/{unique_id}.blend?t={cache_buster}"
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history")
async def get_history():
    history = []
    if not os.path.exists(TARGET_DIR):
        return []
    
    # Get all .glb files in Target
    for filename in os.listdir(TARGET_DIR):
        if filename.endswith(".glb"):
            unique_id = os.path.splitext(filename)[0]
            file_path = os.path.join(TARGET_DIR, filename)
            
            # Find corresponding upload to get a preview image if possible
            preview_url = None
            for upload in os.listdir(UPLOAD_DIR):
                if upload.startswith(unique_id):
                    preview_url = f"/uploads/{upload}"
                    break
            
            stats = os.stat(file_path)
            history.append({
                "id": unique_id,
                "filename": filename,
                "timestamp": stats.st_mtime,
                "model_url": f"/target/{filename}",
                "preview_url": preview_url,
                "size": stats.st_size
            })
            
    # Sort by newest first
    history.sort(key=lambda x: x["timestamp"], reverse=True)
    return history

@app.post("/simulate")
async def simulate_disaster(
    filename: str = Form(...),
    disaster_type: str = Form(...),
    wind_speed: Optional[float] = Form(None),
    ambient_temp: Optional[float] = Form(None),
    water_level: Optional[float] = Form(None),
    rainfall_rate: Optional[float] = Form(None),
    magnitude: Optional[float] = Form(None),
    depth: Optional[float] = Form(None)
):
    """Run real disaster simulation using Blender."""
    unique_id = os.path.splitext(filename)[0]
    blend_path = os.path.join(TARGET_DIR, unique_id + ".blend")
    
    if not os.path.exists(blend_path):
        raise HTTPException(status_code=404, detail="3D model not found. Please convert the blueprint first.")
    
    blender_path = get_blender_path()
    if not blender_path:
        raise HTTPException(status_code=500, detail="Blender not found on this system.")
    
    output_obj = os.path.join(TARGET_DIR, f"{unique_id}_simulated.glb")
    script_path = os.path.join(ROOT_DIR, "Blender", "blender_simulate_disaster.py")
    
    # Build CLI args for the simulation script
    extra_args = []
    if disaster_type == "fire":
        if wind_speed is not None:
            extra_args.append(f"wind_speed={wind_speed}")
        if ambient_temp is not None:
            extra_args.append(f"ambient_temp={ambient_temp}")
    elif disaster_type == "flood":
        if water_level is not None:
            extra_args.append(f"water_level={water_level}")
        if rainfall_rate is not None:
            extra_args.append(f"rainfall_rate={rainfall_rate}")
    elif disaster_type == "earthquake":
        if magnitude is not None:
            extra_args.append(f"magnitude={magnitude}")
        if depth is not None:
            extra_args.append(f"depth={depth}")
    
    try:
        cmd = [
            blender_path,
            "-noaudio",
            "--background",
            "--python", script_path,
            "--",
            blend_path,
            output_obj,
            disaster_type,
        ] + extra_args
        
        check_output(cmd)
        
        # Verify the file was created
        if not os.path.exists(output_obj):
            raise Exception("Blender script finished but simulated model was not created.")
        file_size = os.path.getsize(output_obj)
        if file_size < 1024:
            raise Exception("Simulated model export is invalid (file too small).")
        
        import time
        cache_buster = int(time.time())
        return {
            "status": "success",
            "model_url": f"/target/{unique_id}_simulated.glb?t={cache_buster}",
            "disaster_type": disaster_type,
            "export": {
                "path": output_obj,
                "size_bytes": file_size,
            },
        }
    except CalledProcessError as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Simulation error: {str(e)}")


@app.post("/damage-predict")
async def predict_building_damage(
    filename: str = Form(...),
    disaster_type: str = Form("fire"),
    disaster_intensity: Optional[float] = Form(None),
    total_area: float = Form(180.0),
    room_count: int = Form(6),
    building_material: str = Form("concrete"),
    fragility_index: float = Form(0.65),
    wall_quality: float = Form(0.75),
    wind_speed: Optional[float] = Form(None),
    ambient_temp: Optional[float] = Form(None),
    water_level: Optional[float] = Form(None),
    rainfall_rate: Optional[float] = Form(None),
    magnitude: Optional[float] = Form(None),
    depth: Optional[float] = Form(None),
):
    """Predict building damage by area using Random Forest."""
    unique_id = os.path.splitext(filename)[0]
    blend_path = os.path.join(TARGET_DIR, unique_id + ".blend")
    if not os.path.exists(blend_path):
        raise HTTPException(status_code=404, detail="3D model not found. Please convert the blueprint first.")

    intensity = (
        float(disaster_intensity)
        if disaster_intensity is not None
        else infer_disaster_intensity(
            disaster_type,
            wind_speed,
            ambient_temp,
            water_level,
            rainfall_rate,
            magnitude,
            depth,
        )
    )
    intensity = max(0.0, min(100.0, intensity))

    total_area = max(20.0, total_area)
    room_count = max(1, min(40, room_count))
    fragility_index = max(0.1, min(1.0, fragility_index))
    wall_quality = max(0.1, min(1.0, wall_quality))

    predictor = get_damage_predictor()
    area_profiles = build_area_profiles_from_real_model(filename)
    using_real_model_areas = len(area_profiles) > 0
    if not using_real_model_areas:
        area_profiles = build_area_profiles(total_area, room_count)

    predictions = []
    for area in area_profiles:
        pred = predictor.predict_damage(
            area_width=area["width"],
            area_depth=area["depth"],
            area_height=area["height"],
            building_material=building_material,
            distance_to_epicenter=area["distance"],
            fragility_index=fragility_index,
            wall_quality=wall_quality,
            num_openings=area["openings"],
            disaster_type=disaster_type,
            disaster_intensity=intensity,
        )
        predictions.append(
            {
                "name": area["name"],
                "area": round(area["area"], 2),
                "preview_x": round(float(area.get("preview_x", 0.0)), 3),
                "preview_z": round(float(area.get("preview_z", 0.0)), 3),
                "damage_class": pred["damage_class"],
                "damage_class_name": pred["damage_class_name"],
                "damage_severity": round(pred["damage_severity"], 2),
                "confidence": compute_prediction_confidence(
                    pred["class_probabilities"],
                    pred["damage_severity"],
                    intensity,
                ),
                "risk_level": pred["risk_level"],
                "class_probabilities": pred["class_probabilities"],
            }
        )

    severities = [p["damage_severity"] for p in predictions]
    avg_severity = (sum(severities) / len(severities)) if severities else 0.0
    max_severity = max(severities) if severities else 0.0
    detected_total_area = sum(p["area"] for p in area_profiles) if area_profiles else total_area
    detected_room_count = len(area_profiles) if area_profiles else room_count

    class_counts = {"No Damage": 0, "Minor": 0, "Moderate": 0, "Severe": 0, "Catastrophic": 0}
    for p in predictions:
        if p["damage_class_name"] in class_counts:
            class_counts[p["damage_class_name"]] += 1

    confidences = [p["confidence"] for p in predictions if "confidence" in p]
    avg_confidence = (sum(confidences) / len(confidences)) if confidences else 0.0
    severe_or_above = class_counts["Severe"] + class_counts["Catastrophic"]
    moderate_or_above = severe_or_above + class_counts["Moderate"]
    top_damage_area = max(predictions, key=lambda p: p["damage_severity"]) if predictions else None

    model_info = predictor.get_model_info()

    return {
        "status": "success",
        "filename": filename,
        "disaster_type": disaster_type,
        "disaster_intensity": round(intensity, 2),
        "summary": {
            "total_area": round(detected_total_area, 2),
            "room_count": detected_room_count,
            "average_severity": round(avg_severity, 2),
            "max_severity": round(max_severity, 2),
            "class_counts": class_counts,
            "building_risk": predictor._get_risk_level(avg_severity),
            "areas_source": "real_model" if using_real_model_areas else "fallback_profile",
            "average_confidence": round(avg_confidence, 2),
            "critical_areas": severe_or_above,
            "affected_areas": moderate_or_above,
            "top_damage_area": top_damage_area["name"] if top_damage_area else None,
            "top_damage_severity": round(top_damage_area["damage_severity"], 2) if top_damage_area else 0.0,
            "model_trees": model_info.get("n_trees", 0),
            "model_features": model_info.get("n_features", 0),
        },
        "areas": predictions,
    }

@app.post("/pathfind")
async def pathfind_evacuation(
    filename: str = Form(...),
    start_x: float = Form(...),
    start_y: float = Form(...),
    dest_x: Optional[float] = Form(None),
    dest_y: Optional[float] = Form(None),
    use_simulated: bool = Form(False),
    algorithm: str = Form("qlearning") # 'astar' or 'qlearning'
):
    """Run real evacuation pathfinding using Blender, supporting optional destination points."""
    unique_id = os.path.splitext(filename)[0]
    
    # Use simulated aftermath only when explicitly requested by frontend.
    simulated_glb = os.path.join(TARGET_DIR, unique_id + "_simulated.glb")
    if use_simulated:
        if not os.path.exists(simulated_glb):
            raise HTTPException(status_code=404, detail="Simulated model not found. Run simulation first.")
        blend_path = simulated_glb
    else:
        blend_path = os.path.join(TARGET_DIR, unique_id + ".blend")
        if not os.path.exists(blend_path):
            raise HTTPException(status_code=404, detail="3D model not found. Please convert the blueprint first.")
    
    blender_path = get_blender_path()
    if not blender_path:
        raise HTTPException(status_code=500, detail="Blender not found on this system.")
    
    output_obj = os.path.join(TARGET_DIR, f"{unique_id}_evacuated.glb")
    script_path = os.path.join(ROOT_DIR, "Blender", "blender_evacuate_path.py")
    
    try:
        cmd = [
            blender_path,
            "-noaudio",
            "--background",
            "--python", script_path,
            "--",
            blend_path,
            output_obj,
            str(start_x),
            str(start_y),
            str(dest_x) if dest_x is not None else "None",
            str(dest_y) if dest_y is not None else "None",
            algorithm
        ]
        
        check_output(cmd)
        
        # Verify the file was created
        if not os.path.exists(output_obj):
            raise Exception("Blender script finished but evacuation path model was not created.")

        diagnostics = None
        meta_path = output_obj + ".pathmeta.json"
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    diagnostics = json.load(f)
            except Exception:
                diagnostics = None
        
        import time
        cache_buster = int(time.time())
        return {
            "status": "success",
            "model_url": f"/target/{unique_id}_evacuated.glb?t={cache_buster}",
            "source_model": "simulated" if use_simulated else "original",
            "path_diagnostics": diagnostics,
        }
    except CalledProcessError as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Pathfinding failed: {str(e)}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Pathfinding error: {str(e)}")

# Static mounts
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/target", StaticFiles(directory=TARGET_DIR), name="target")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
