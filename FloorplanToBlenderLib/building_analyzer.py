"""
Building Analysis & ML Integration Layer
Extracts building features, applies ML models, and generates evacuation/damage predictions.

Author: ML Integration Module
"""

import numpy as np
import json
from typing import List, Tuple, Dict, Optional
from .qlearning_pathfinder import QLearningPathfinder
from .damage_predictor import BuildingDamagePredictor

# Optional Blender import (only needed for extract_building_features_from_blender)
try:
    import bpy
    HAS_BLENDER = True
except ImportError:
    HAS_BLENDER = False


class BuildingAnalyzer:
    """
    Analyzes building structure and integrates Q-Learning and Random Forest predictions.
    """
    
    def __init__(self, use_qlearning=True, use_damage_prediction=True):
        """
        Initialize building analyzer with ML models.
        
        Args:
            use_qlearning: Enable Q-Learning path optimization
            use_damage_prediction: Enable Random Forest damage prediction
        """
        self.use_qlearning = use_qlearning
        self.use_damage_prediction = use_damage_prediction
        
        self.qlearner = QLearningPathfinder() if use_qlearning else None
        self.damage_predictor = BuildingDamagePredictor() if use_damage_prediction else None
        
        self.rooms = []
        self.walls = []
        self.doors = []
        self.exits = []
        self.building_grid = None
        self.grid_bounds = None
    
    def extract_building_features_from_blender(self):
        """
        Extract room, wall, and exit information from Blender scene.
        
        Returns:
            dict with building information
        """
        building_info = {
            'rooms': [],
            'walls': [],
            'doors': [],
            'exits': [],
            'total_area': 0
        }
        
        if not HAS_BLENDER:
            print("Warning: Blender (bpy) not available - cannot extract from scene")
            return building_info
        
        if not hasattr(bpy, 'data'):
            print("Warning: Not running in Blender environment")
            return building_info
        
        try:
            for obj in bpy.data.objects:
                if obj.type != 'MESH':
                    continue
                
                # Analyze object by name convention
                obj_name = obj.name.lower()
                bbox = self._get_world_bbox(obj)
                
                if 'room' in obj_name:
                    room_info = {
                        'name': obj.name,
                        'type': self._classify_room_type(obj.name),
                        'position': [obj.location.x, obj.location.y, obj.location.z],
                        'dimensions': self._get_dimensions(obj),
                        'area': self._get_floor_area(obj),
                        'center': [(bbox[0] + bbox[1]) / 2, (bbox[2] + bbox[3]) / 2],
                    }
                    building_info['rooms'].append(room_info)
                    building_info['total_area'] += room_info['area']
                
                elif 'wall' in obj_name:
                    wall_info = {
                        'name': obj.name,
                        'position': [obj.location.x, obj.location.y, obj.location.z],
                        'dimensions': self._get_dimensions(obj),
                        'material': self._detect_material(obj),
                    }
                    building_info['walls'].append(wall_info)
                
                elif 'door' in obj_name or 'opening' in obj_name:
                    door_info = {
                        'name': obj.name,
                        'position': [obj.location.x, obj.location.y, obj.location.z],
                        'type': 'door' if 'door' in obj_name else 'opening'
                    }
                    building_info['doors'].append(door_info)
                
                elif 'exit' in obj_name or 'emergency_exit' in obj_name:
                    exit_info = {
                        'name': obj.name,
                        'position': [obj.location.x, obj.location.y, obj.location.z],
                        'type': 'emergency_exit' if 'emergency' in obj_name else 'exit'
                    }
                    building_info['exits'].append(exit_info)
            
            # If no explicit exits, use doors near edges as exits
            if not building_info['exits'] and building_info['doors']:
                for door in building_info['doors'][:2]:  # Use first 2 doors as exits
                    building_info['exits'].append({
                        'name': f"Exit_{door['name']}",
                        'position': door['position'],
                        'type': 'implied_exit'
                    })
        
        except Exception as e:
            print(f"Error extracting building features: {e}")
        
        return building_info
    
    def _get_world_bbox(self, obj):
        """Get world-space bounding box as (min_x, max_x, min_y, max_y)."""
        if not obj.data.vertices:
            return (obj.location.x, obj.location.x, obj.location.y, obj.location.y)
        
        coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
        xs = [c.x for c in coords]
        ys = [c.y for c in coords]
        return (min(xs), max(xs), min(ys), max(ys))
    
    def _get_dimensions(self, obj):
        """Get object dimensions (width, depth, height)."""
        bbox = self._get_world_bbox(obj)
        min_z = min([obj.matrix_world[2][3] + v.co.z for v in obj.data.vertices]) if obj.data.vertices else 0
        max_z = max([obj.matrix_world[2][3] + v.co.z for v in obj.data.vertices]) if obj.data.vertices else 3
        
        return {
            'width': bbox[1] - bbox[0],
            'depth': bbox[3] - bbox[2],
            'height': max_z - min_z
        }
    
    def _get_floor_area(self, obj):
        """Calculate floor area of room."""
        dims = self._get_dimensions(obj)
        return dims['width'] * dims['depth']
    
    def _classify_room_type(self, obj_name):
        """Classify room type from object name."""
        name_lower = obj_name.lower()
        if 'kitchen' in name_lower:
            return 'kitchen'
        elif 'bed' in name_lower:
            return 'bedroom'
        elif 'bath' in name_lower:
            return 'bathroom'
        elif 'living' in name_lower or 'lounge' in name_lower:
            return 'living'
        elif 'garage' in name_lower:
            return 'garage'
        elif 'storage' in name_lower or 'closet' in name_lower:
            return 'storage'
        elif 'hall' in name_lower or 'corridor' in name_lower:
            return 'hallway'
        return 'unknown'
    
    def _detect_material(self, obj):
        """Detect building material from object properties or name."""
        obj_name = obj.name.lower()
        
        if any(x in obj_name for x in ['concrete', 'cement']):
            return 'concrete'
        elif any(x in obj_name for x in ['wood', 'timber']):
            return 'wood'
        elif any(x in obj_name for x in ['brick', 'masonry']):
            return 'masonry'
        elif any(x in obj_name for x in ['steel', 'iron']):
            return 'steel'
        
        return 'unknown'
    
    def build_navigation_grid(self, building_info, resolution=0.5):
        """
        Build a navigable grid from building info.
        
        Returns:
            2D array where 0=obstacle, 1=walkable floor, 2=hazard zone
        """
        if not building_info['rooms']:
            return None
        
        # Find bounds
        all_xs = []
        all_ys = []
        
        for room in building_info['rooms']:
            center = room['center']
            dims = room['dimensions']
            all_xs.extend([center[0] - dims['width']/2, center[0] + dims['width']/2])
            all_ys.extend([center[1] - dims['depth']/2, center[1] + dims['depth']/2])
        
        min_x, max_x = min(all_xs), max(all_xs)
        min_y, max_y = min(all_ys), max(all_ys)
        
        cols = int((max_x - min_x) / resolution) + 1
        rows = int((max_y - min_y) / resolution) + 1
        grid = [[1] * cols for _ in range(rows)]  # Start with walkable
        
        # Mark room positions as walkable, outside as obstacles
        for r in range(rows):
            for c in range(cols):
                wx = min_x + c * resolution
                wy = min_y + r * resolution
                
                # Check if point is in any room
                in_room = False
                for room in building_info['rooms']:
                    center = room['center']
                    dims = room['dimensions']
                    if (abs(wx - center[0]) < dims['width']/2 and 
                        abs(wy - center[1]) < dims['depth']/2):
                        in_room = True
                        break
                
                if not in_room:
                    grid[r][c] = 0  # Obstacle
        
        self.building_grid = grid
        self.grid_bounds = (min_x, max_x, min_y, max_y)
        return grid
    
    def optimize_evacuation_with_qlearning(self, building_info, start_pos, 
                                          disaster_zones, n_training_episodes=50):
        """
        Train Q-Learning model and find optimal evacuation path.
        
        Args:
            building_info: Building structure information
            start_pos: Starting position (x, y)
            disaster_zones: List of (center_x, center_y, radius, intensity)
            n_training_episodes: Number of training episodes
        
        Returns:
            Optimal path coordinates
        """
        if not self.use_qlearning:
            return None
        
        # Build navigation grid
        self.build_navigation_grid(building_info)
        
        # Extract start and exit positions
        exit_positions = [(e['position'][0], e['position'][1]) for e in building_info['exits']]
        if not exit_positions:
            # Use room centers as exits
            exit_positions = [(r['center'][0], r['center'][1]) for r in building_info['rooms'][:2]]
        
        start_positions = [start_pos] + exit_positions  # Use exits as learning targets
        
        # Train Q-Learning model
        print("Training Q-Learning evacuation model...")
        self.qlearner.train_episodes(
            building_grid=self.building_grid,
            disaster_zones=disaster_zones,
            exit_positions=exit_positions,
            start_positions=start_positions,
            num_episodes=n_training_episodes
        )
        
        # Find optimal path
        if exit_positions:
            optimal_exit = min(exit_positions, 
                              key=lambda e: np.sqrt((start_pos[0]-e[0])**2 + (start_pos[1]-e[1])**2))
            path = self.qlearner.find_path(self.building_grid, start_pos, optimal_exit, disaster_zones)
            print(f"Found optimal path with {len(path)} waypoints")
            return path
        
        return None
    
    def predict_area_damage(self, room_info: Dict, disaster_type: str, 
                           disaster_intensity: float, distance_to_epicenter: float) -> Dict:
        """
        Predict damage for a specific area/room.
        
        Args:
            room_info: Room information dict
            disaster_type: Type of disaster
            disaster_intensity: Intensity of disaster (0-100)
            distance_to_epicenter: Distance from disaster origin
        
        Returns:
            Damage prediction dict
        """
        if not self.use_damage_prediction:
            return {}
        
        dims = room_info.get('dimensions', {})
        
        prediction = self.damage_predictor.predict_damage(
            area_width=dims.get('width', 5),
            area_depth=dims.get('depth', 5),
            area_height=dims.get('height', 3),
            room_type=room_info.get('type', 'unknown'),
            building_material=room_info.get('material', 'unknown'),
            distance_to_epicenter=distance_to_epicenter,
            disaster_type=disaster_type,
            disaster_intensity=disaster_intensity
        )
        
        return prediction
    
    def predict_building_damage(self, building_info: Dict, disaster_type: str,
                               disaster_intensity: float, disaster_center: Tuple) -> Dict:
        """
        Predict damage for entire building.
        
        Args:
            building_info: Building information
            disaster_type: Type of disaster
            disaster_intensity: Intensity of disaster (0-100)
            disaster_center: (x, y) center of disaster
        
        Returns:
            Comprehensive damage report
        """
        if not self.use_damage_prediction:
            return {}
        
        damage_report = {
            'disaster_type': disaster_type,
            'disaster_intensity': disaster_intensity,
            'disaster_center': disaster_center,
            'rooms': [],
            'summary': {
                'total_rooms': len(building_info['rooms']),
                'critical_damage_count': 0,
                'high_damage_count': 0,
                'average_severity': 0,
                'evacuation_risk': 'Low'
            }
        }
        
        severities = []
        
        for room in building_info['rooms']:
            center = room['center']
            distance = np.sqrt((center[0] - disaster_center[0])**2 + 
                             (center[1] - disaster_center[1])**2)
            
            damage_pred = self.predict_area_damage(
                room, disaster_type, disaster_intensity, distance
            )
            
            damage_pred['room_name'] = room['name']
            damage_report['rooms'].append(damage_pred)
            
            severity = damage_pred.get('damage_severity', 0)
            severities.append(severity)
            
            if damage_pred.get('damage_class', 0) >= 3:
                damage_report['summary']['critical_damage_count'] += 1
            elif damage_pred.get('damage_class', 0) >= 2:
                damage_report['summary']['high_damage_count'] += 1
        
        # Calculate summary statistics
        if severities:
            avg_severity = np.mean(severities)
            damage_report['summary']['average_severity'] = float(avg_severity)
            
            if avg_severity >= 80:
                damage_report['summary']['evacuation_risk'] = 'Critical'
            elif avg_severity >= 60:
                damage_report['summary']['evacuation_risk'] = 'High'
            elif avg_severity >= 40:
                damage_report['summary']['evacuation_risk'] = 'Moderate'
            else:
                damage_report['summary']['evacuation_risk'] = 'Low'
        
        return damage_report
    
    def generate_evacuation_recommendations(self, building_info: Dict, 
                                           damage_report: Dict) -> Dict:
        """
        Generate evacuation recommendations based on damage predictions.
        
        Args:
            building_info: Building structure
            damage_report: Damage predictions
        
        Returns:
            Evacuation strategy recommendations
        """
        recommendations = {
            'priority_level': damage_report['summary']['evacuation_risk'],
            'critical_areas': [],
            'safe_zones': [],
            'evacuation_order': []
        }
        
        # Identify critical and safe areas
        for room_damage in damage_report['rooms']:
            damage_class = room_damage.get('damage_class', 0)
            room_name = room_damage.get('room_name', 'Unknown')
            
            if damage_class >= 3:
                recommendations['critical_areas'].append(room_name)
            elif damage_class == 0:
                recommendations['safe_zones'].append(room_name)
        
        # Generate evacuation order (prioritize high-damage areas)
        sorted_rooms = sorted(damage_report['rooms'], 
                            key=lambda x: x.get('damage_severity', 0), reverse=True)
        recommendations['evacuation_order'] = [
            r.get('room_name', 'Unknown') for r in sorted_rooms[:5]
        ]
        
        return recommendations
    
    def save_all_models(self):
        """Save trained ML models."""
        if self.use_qlearning and self.qlearner:
            self.qlearner.save_model()
        if self.use_damage_prediction and self.damage_predictor:
            self.damage_predictor.save_model()
    
    def load_all_models(self):
        """Load trained ML models."""
        if self.use_qlearning and self.qlearner:
            try:
                self.qlearner.load_model()
            except FileNotFoundError:
                print("Q-Learning model not found, will need training")
        
        if self.use_damage_prediction and self.damage_predictor:
            try:
                self.damage_predictor.load_model()
            except FileNotFoundError:
                print("Damage predictor not found, will need training")


if __name__ == "__main__":
    print("Building Analyzer & ML Integration Module")
    print("Import this module to use in your scripts")
