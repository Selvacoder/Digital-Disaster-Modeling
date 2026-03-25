"""
ML Integration Example & Setup Script
Demonstrates how to use Q-Learning and Random Forest with the Blueprint-to-3D project.

Usage:
    python ml_integration_example.py --mode train    # Train all models
    python ml_integration_example.py --mode predict  # Make predictions
    python ml_integration_example.py --mode demo     # Run full demo
"""

import sys
import os
import numpy as np
import json
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from FloorplanToBlenderLib.qlearning_pathfinder import QLearningPathfinder
from FloorplanToBlenderLib.damage_predictor import BuildingDamagePredictor
from FloorplanToBlenderLib.building_analyzer import BuildingAnalyzer


def create_sample_building():
    """Create a sample building structure for demonstration."""
    building_info = {
        'rooms': [
            {
                'name': 'Kitchen',
                'type': 'kitchen',
                'center': (5, 5),
                'dimensions': {'width': 4, 'depth': 3, 'height': 3},
                'area': 12,
                'material': 'concrete'
            },
            {
                'name': 'Living Room',
                'type': 'living',
                'center': (10, 8),
                'dimensions': {'width': 6, 'depth': 5, 'height': 3},
                'area': 30,
                'material': 'concrete'
            },
            {
                'name': 'Bedroom 1',
                'type': 'bedroom',
                'center': (3, 12),
                'dimensions': {'width': 4, 'depth': 4, 'height': 3},
                'area': 16,
                'material': 'wood'
            },
            {
                'name': 'Bedroom 2',
                'type': 'bedroom',
                'center': (12, 12),
                'dimensions': {'width': 4, 'depth': 4, 'height': 3},
                'area': 16,
                'material': 'wood'
            },
            {
                'name': 'Bathroom',
                'type': 'bathroom',
                'center': (8, 3),
                'dimensions': {'width': 2, 'depth': 2.5, 'height': 3},
                'area': 5,
                'material': 'masonry'
            },
        ],
        'walls': [
            {'name': 'Wall1', 'position': (5, 0, 0), 'material': 'concrete'},
            {'name': 'Wall2', 'position': (0, 8, 0), 'material': 'concrete'},
        ],
        'doors': [
            {'name': 'Door1', 'position': (0, 5, 0), 'type': 'door'},
        ],
        'exits': [
            {'name': 'Exit1', 'position': (0, 5, 0), 'type': 'emergency_exit'},
            {'name': 'Exit2', 'position': (15, 5, 0), 'type': 'emergency_exit'},
        ],
        'total_area': 79
    }
    return building_info


def train_models():
    """Train both ML models."""
    print("=" * 80)
    print("TRAINING ML MODELS")
    print("=" * 80)
    
    # Create Models directory
    os.makedirs("Models", exist_ok=True)
    
    # ==================== TRAIN DAMAGE PREDICTOR ====================
    print("\n[1/2] Training Damage Prediction Model (Random Forest)...")
    print("-" * 80)
    
    damage_predictor = BuildingDamagePredictor(n_trees=100)
    
    # Generate synthetic training data
    X, y_class, y_severity = damage_predictor.generate_synthetic_training_data(n_samples=2000)
    
    # Train the model
    damage_predictor.train(X, y_class, y_severity, test_size=0.2)
    
    # Save trained model
    damage_predictor.save_model()
    
    print("\nDamage Predictor Training Complete!")
    print(f"Model Info: {damage_predictor.get_model_info()}")
    
    # ==================== TRAIN Q-LEARNING ====================
    print("\n[2/2] Training Q-Learning Path Optimizer...")
    print("-" * 80)
    
    qlearner = QLearningPathfinder(
        grid_resolution=0.5,
        learning_rate=0.1,
        discount_factor=0.9,
        epsilon=0.2
    )
    
    # Create sample grid (20x20)
    building_grid = [[1 if (5 <= i <= 15 and 5 <= j <= 15) else 0 
                      for j in range(20)] for i in range(20)]
    
    # Disaster zones (x, y, radius, intensity)
    disaster_zones = [(10, 10, 3, 80)]
    
    # Exit positions
    exit_positions = [(2, 2), (17, 17)]
    
    # Start positions
    start_positions = [(10, 10), (7, 7), (12, 12)]
    
    # Train with episodes
    qlearner.train_episodes(
        building_grid=building_grid,
        disaster_zones=disaster_zones,
        exit_positions=exit_positions,
        start_positions=start_positions,
        num_episodes=100
    )
    
    # Save trained model
    qlearner.save_model()
    
    print("\nQ-Learning Training Complete!")
    print(f"Model Stats: {qlearner.get_model_stats()}")
    
    print("\n" + "=" * 80)
    print("TRAINING COMPLETE - Models saved to ./Models/")
    print("=" * 80)


def make_predictions():
    """Make predictions using trained models."""
    print("\n" + "=" * 80)
    print("MAKING ML PREDICTIONS")
    print("=" * 80)
    
    # Load models
    damage_predictor = BuildingDamagePredictor()
    qlearner = QLearningPathfinder()
    
    try:
        damage_predictor.load_model()
        qlearner.load_model()
    except FileNotFoundError as e:
        print(f"Error loading models: {e}")
        print("Please train models first with: python ml_integration_example.py --mode train")
        return
    
    # ==================== DAMAGE PREDICTION ====================
    print("\n[1/2] Damage Prediction for Sample Areas")
    print("-" * 80)
    
    areas = [
        {
            'name': 'Living Room',
            'width': 6, 'depth': 5, 'height': 3,
            'room_type': 'living',
            'material': 'concrete',
            'distance': 5,
            'intensity': 70
        },
        {
            'name': 'Bedroom (Wood)',
            'width': 4, 'depth': 4, 'height': 3,
            'room_type': 'bedroom',
            'material': 'wood',
            'distance': 8,
            'intensity': 70
        },
        {
            'name': 'Kitchen',
            'width': 4, 'depth': 3, 'height': 3,
            'room_type': 'kitchen',
            'material': 'concrete',
            'distance': 15,
            'intensity': 70
        },
    ]
    
    for area in areas:
        print(f"\n  {area['name']}:")
        prediction = damage_predictor.predict_damage(
            area_width=area['width'],
            area_depth=area['depth'],
            area_height=area['height'],
            room_type=area['room_type'],
            building_material=area['material'],
            distance_to_epicenter=area['distance'],
            disaster_type='fire',
            disaster_intensity=area['intensity']
        )
        
        print(f"    Damage Class: {prediction['damage_class_name']}")
        print(f"    Damage Severity: {prediction['damage_severity']:.1f}%")
        print(f"    Risk Level: {prediction['risk_level']}")
        print(f"    Probabilities: {json.dumps(prediction['class_probabilities'], indent=6)}")
    
    # ==================== EVACUATION PATH OPTIMIZATION ====================
    print("\n[2/2] Evacuation Path Optimization (Q-Learning)")
    print("-" * 80)
    
    # Create simple grid
    building_grid = [[1 if (5 <= i <= 15 and 5 <= j <= 15) else 0 
                      for j in range(20)] for i in range(20)]
    
    start_pos = (7, 7)
    exit_pos = (2, 2)
    disaster_zones = [(10, 10, 3, 80), (12, 12, 2, 60)]
    
    # Find optimal path
    path = qlearner.find_path(building_grid, start_pos, exit_pos, disaster_zones)
    
    print(f"\n  Start Position: {start_pos}")
    print(f"  Target Exit: {exit_pos}")
    print(f"  Disaster Zones: {len(disaster_zones)}")
    print(f"  Path Length: {len(path)} waypoints")
    print(f"  First 5 waypoints: {path[:5]}")
    print(f"  Last 5 waypoints: {path[-5:]}")
    
    print("\n" + "=" * 80)


def run_full_demo():
    """Run full demonstration of all components."""
    print("\n" + "=" * 80)
    print("RUNNING FULL ML INTEGRATION DEMO")
    print("=" * 80)
    
    # Get or create models
    os.makedirs("Models", exist_ok=True)
    
    # Initialize analyzer
    analyzer = BuildingAnalyzer(use_qlearning=True, use_damage_prediction=True)
    
    # Create sample building
    print("\n[1/5] Creating Sample Building...")
    building_info = create_sample_building()
    print(f"      Rooms: {len(building_info['rooms'])}")
    for room in building_info['rooms']:
        print(f"        - {room['name']} ({room['type']}): {room['area']:.1f} m²")
    
    # Train damage predictor
    print("\n[2/5] Training Damage Predictor...")
    analyzer.damage_predictor.train(generate_synthetic=True, n_synthetic=1000)
    
    # Build navigation grid
    print("\n[3/5] Building Navigation Grid...")
    grid = analyzer.build_navigation_grid(building_info, resolution=0.5)
    print(f"      Grid Size: {len(grid)}x{len(grid[0])}")
    
    # Predict building damage
    print("\n[4/5] Predicting Damage from Fire Disaster...")
    disaster_center = (10, 8)
    damage_report = analyzer.predict_building_damage(
        building_info,
        disaster_type='fire',
        disaster_intensity=75,
        disaster_center=disaster_center
    )
    
    print(f"      Average Severity: {damage_report['summary']['average_severity']:.1f}%")
    print(f"      Evacuation Risk: {damage_report['summary']['evacuation_risk']}")
    print(f"      Critical Rooms: {damage_report['summary']['critical_damage_count']}")
    print(f"      High Damage Rooms: {damage_report['summary']['high_damage_count']}")
    
    # Show detailed room predictions
    print("\n      Room-by-Room Damage Predictions:")
    for room_damage in damage_report['rooms'][:3]:
        print(f"        - {room_damage['room_name']}: {room_damage['damage_class_name']} "
              f"({room_damage['damage_severity']:.1f}%)")
    
    # Generate evacuation recommendations
    print("\n[5/5] Generating Evacuation Recommendations...")
    recommendations = analyzer.generate_evacuation_recommendations(
        building_info, damage_report
    )
    
    print(f"      Priority Level: {recommendations['priority_level']}")
    print(f"      Safe Zones: {', '.join(recommendations['safe_zones']) or 'None'}")
    print(f"      Evacuation Order: {', '.join(recommendations['evacuation_order'])}")
    
    # Save models
    print("\n[Saving] Persisting Models...")
    analyzer.save_all_models()
    
    print("\n" + "=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description='ML Integration Example for Blueprint-to-3D Project'
    )
    parser.add_argument(
        '--mode',
        choices=['train', 'predict', 'demo'],
        default='demo',
        help='Execution mode (default: demo)'
    )
    
    args = parser.parse_args()
    
    if args.mode == 'train':
        train_models()
    elif args.mode == 'predict':
        make_predictions()
    elif args.mode == 'demo':
        # Train then predict
        train_models()
        make_predictions()
        # Also run full integration demo
        input("\nPress Enter to run full integration demo...")
        run_full_demo()


if __name__ == "__main__":
    main()
