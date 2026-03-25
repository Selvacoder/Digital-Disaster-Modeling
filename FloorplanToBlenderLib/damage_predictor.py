"""
Random Forest Based Building Damage Prediction
Predicts structural damage probability and severity for building areas based on disaster characteristics.

Author: ML Integration Module
"""

import numpy as np
import json
import os
import pickle
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, mean_squared_error


class BuildingDamagePredictor:
    """
    Random Forest based damage prediction system.
    
    Predicts:
    1. Damage Classification: No Damage (0), Minor (1), Moderate (2), Severe (3), Catastrophic (4)
    2. Damage Severity: Numerical score 0-100
    
    Features:
    - Area dimensions (width, depth, height)
    - Building material (concrete=1, wood=2, masonry=3, steel=4)
    - Distance from disaster epicenter
    - Structural fragility index (0-1)
    - Wall material quality (0-1)
    - Number of openings (doors, windows)
    - Disaster type (fire=0, flood=1, earthquake=2)
    - Disaster intensity (0-100)
    """
    
    # Building material encoding
    MATERIALS = {
        'concrete': 1,
        'wood': 2,
        'masonry': 3,
        'steel': 4,
        'brick': 3,
        'unknown': 0
    }
    
    # Disaster type encoding
    DISASTER_TYPES = {
        'fire': 0,
        'flood': 1,
        'earthquake': 2,
        'wind': 3,
        'other': 4
    }
    
    # Damage classification labels
    DAMAGE_CLASSES = {
        0: 'No Damage',
        1: 'Minor',
        2: 'Moderate',
        3: 'Severe',
        4: 'Catastrophic'
    }

    MATERIAL_BASE_VULNERABILITY = {
        1: 0.7,
        2: 1.05,
        3: 0.85,
        4: 0.55,
        0: 0.9,
    }

    DISASTER_DISTANCE_SCALE = {
        0: 13.5,  # fire spreads through connected compartments
        1: 17.0,  # flood water impacts broad areas
        2: 8.0,   # earthquake strong gradient around fault/epicenter proxy
        3: 11.0,
        4: 10.0,
    }
    
    def __init__(self, n_trees=100, model_dir="Models"):
        """
        Initialize damage predictor with Random Forest models.
        
        Args:
            n_trees: Number of trees in random forest
            model_dir: Directory to save/load trained models
        """
        self.n_trees = n_trees
        self.model_dir = model_dir
        
        # Random Forest models
        self.damage_classifier = RandomForestClassifier(
            n_estimators=n_trees,
            max_depth=15,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        )
        
        self.damage_regressor = RandomForestRegressor(
            n_estimators=n_trees,
            max_depth=15,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        )
        
        self.feature_scaler = StandardScaler()
        self.feature_names = [
            'area_width', 'area_depth', 'area_height',
            'building_material', 'distance_to_epicenter',
            'fragility_index', 'wall_quality', 'num_openings',
            'disaster_type', 'disaster_intensity'
        ]
        
        self.is_trained = False
        
        # Create model directory if needed
        if not os.path.exists(model_dir):
            os.makedirs(model_dir)
    
    def _create_feature_vector(self, area_width, area_depth, area_height,
                              building_material, distance_to_epicenter, fragility_index,
                              wall_quality, num_openings, disaster_type, disaster_intensity):
        """Create feature vector for a single prediction."""
        material_code = self.MATERIALS.get(building_material.lower(), 0)
        disaster_code = self.DISASTER_TYPES.get(disaster_type.lower(), 4)
        
        return np.array([[
            area_width,
            area_depth,
            area_height,
            material_code,
            distance_to_epicenter,
            fragility_index,
            wall_quality,
            num_openings,
            disaster_code,
            disaster_intensity
        ]], dtype=float)
    
    def generate_synthetic_training_data(self, n_samples=1000):
        """
        Generate synthetic training data for initial model training.
        
        Args:
            n_samples: Number of training samples to generate
        
        Returns:
            X: Feature matrix (n_samples, n_features)
            y_class: Damage class labels (0-4)
            y_severity: Damage severity scores (0-100)
        """
        print(f"Generating {n_samples} synthetic training samples...")
        
        X = []
        y_class = []
        y_severity = []
        
        for _ in range(n_samples):
            # Random features
            area_width = np.random.uniform(2, 15)  # meters
            area_depth = np.random.uniform(2, 15)
            area_height = np.random.uniform(2.5, 4.5)
            material = np.random.choice(list(self.MATERIALS.values()))
            distance = np.random.exponential(10)  # Closer to epicenter more likely
            fragility = np.random.uniform(0.2, 1.0)
            wall_quality = np.random.uniform(0.2, 1.0)
            num_openings = np.random.randint(0, 8)
            disaster = np.random.choice(list(self.DISASTER_TYPES.values()))
            intensity = np.random.uniform(20, 100)
            
            X.append([
                area_width, area_depth, area_height, material,
                distance, fragility, wall_quality, num_openings, disaster, intensity
            ])
            
            damage_score = self._physics_severity_estimate(
                material_code=material,
                distance_to_epicenter=distance,
                fragility_index=fragility,
                wall_quality=wall_quality,
                num_openings=num_openings,
                disaster_code=disaster,
                disaster_intensity=intensity,
            )
            damage_score = float(np.clip(damage_score + np.random.normal(0.0, 4.5), 0.0, 100.0))
            
            # Classification: 0-20 = No Damage, 20-40 = Minor, 40-60 = Moderate, 60-80 = Severe, 80+ = Catastrophic
            if damage_score < 15:
                damage_class = 0
            elif damage_score < 35:
                damage_class = 1
            elif damage_score < 55:
                damage_class = 2
            elif damage_score < 75:
                damage_class = 3
            else:
                damage_class = 4
            
            y_class.append(damage_class)
            y_severity.append(damage_score)
        
        return np.array(X), np.array(y_class), np.array(y_severity)
    
    def train(self, X_train=None, y_class_train=None, y_severity_train=None, 
             generate_synthetic=True, n_synthetic=1000, test_size=0.2):
        """
        Train Random Forest models.
        
        Args:
            X_train: Feature matrix (if None, generates synthetic data)
            y_class_train: Class labels
            y_severity_train: Severity scores
            generate_synthetic: Whether to generate synthetic data if none provided
            n_synthetic: Number of synthetic samples
            test_size: Test set size for evaluation
        """
        if X_train is None:
            if not generate_synthetic:
                raise ValueError("Provide training data or set generate_synthetic=True")
            
            X_train, y_class_train, y_severity_train = self.generate_synthetic_training_data(n_synthetic)
        
        # Split data
        X_train_split, X_test, y_class_train_split, y_class_test, y_sev_train_split, y_sev_test = \
            train_test_split(X_train, y_class_train, y_severity_train, test_size=test_size, random_state=42)
        
        # Scale features
        X_train_scaled = self.feature_scaler.fit_transform(X_train_split)
        X_test_scaled = self.feature_scaler.transform(X_test)
        
        # Train classifier
        print("Training damage classifier...")
        self.damage_classifier.fit(X_train_scaled, y_class_train_split)
        class_accuracy = self.damage_classifier.score(X_test_scaled, y_class_test)
        print(f"  Classifier accuracy on test set: {class_accuracy:.4f}")
        
        # Train regressor
        print("Training damage regressor...")
        self.damage_regressor.fit(X_train_scaled, y_sev_train_split)
        regressor_rmse = np.sqrt(mean_squared_error(y_sev_test, self.damage_regressor.predict(X_test_scaled)))
        print(f"  Regressor RMSE on test set: {regressor_rmse:.4f}")
        
        self.is_trained = True
        
        # Feature importance
        print("\nFeature Importance (Classification):")
        for name, importance in sorted(zip(self.feature_names, self.damage_classifier.feature_importances_), 
                                      key=lambda x: x[1], reverse=True):
            print(f"  {name}: {importance:.4f}")
    
    def predict_damage(self, area_width, area_depth, area_height,
                      building_material, distance_to_epicenter, fragility_index=0.7,
                      wall_quality=0.7, num_openings=2, disaster_type='fire', disaster_intensity=70):
        """
        Predict damage for a building area.
        
        Args:
            area_width: Width in meters
            area_depth: Depth in meters
            area_height: Height in meters
            building_material: Material type (string)
            distance_to_epicenter: Distance from disaster center in meters
            fragility_index: Structural fragility (0-1, higher = more fragile)
            wall_quality: Wall quality (0-1, higher = better)
            num_openings: Number of doors/windows
            disaster_type: Type of disaster
            disaster_intensity: Disaster intensity (0-100)
        
        Returns:
            dict with predictions
        """
        if not self.is_trained:
            raise ValueError("Model not trained! Call train() first.")
        
        X = self._create_feature_vector(area_width, area_depth, area_height,
                                        building_material, distance_to_epicenter, fragility_index,
                                        wall_quality, num_openings, disaster_type, disaster_intensity)
        
        X_scaled = self.feature_scaler.transform(X)
        
        # Predict class
        damage_class = self.damage_classifier.predict(X_scaled)[0]
        damage_prob = self.damage_classifier.predict_proba(X_scaled)[0]
        
        # Predict severity
        damage_severity = self.damage_regressor.predict(X_scaled)[0]
        damage_severity = self._calibrate_severity(
            rf_severity=damage_severity,
            building_material=building_material,
            distance_to_epicenter=distance_to_epicenter,
            fragility_index=fragility_index,
            wall_quality=wall_quality,
            num_openings=num_openings,
            disaster_type=disaster_type,
            disaster_intensity=disaster_intensity,
        )
        
        return {
            'damage_class': int(damage_class),
            'damage_class_name': self.DAMAGE_CLASSES[int(damage_class)],
            'damage_severity': float(damage_severity),
            'class_probabilities': {
                self.DAMAGE_CLASSES[i]: float(prob)
                for i, prob in enumerate(damage_prob)
            },
            'risk_level': self._get_risk_level(damage_severity)
        }

    def _get_disaster_material_multiplier(self, disaster_code, material_code):
        """Return material vulnerability multiplier adjusted by disaster type."""
        if disaster_code == self.DISASTER_TYPES.get('fire', 0):
            return {
                1: 0.85,
                2: 1.35,
                3: 1.0,
                4: 0.75,
                0: 1.0,
            }.get(material_code, 1.0)

        if disaster_code == self.DISASTER_TYPES.get('flood', 1):
            return {
                1: 0.95,
                2: 1.2,
                3: 1.05,
                4: 0.9,
                0: 1.0,
            }.get(material_code, 1.0)

        if disaster_code == self.DISASTER_TYPES.get('earthquake', 2):
            return {
                1: 1.05,
                2: 0.95,
                3: 1.35,
                4: 0.72,
                0: 1.0,
            }.get(material_code, 1.0)

        if disaster_code == self.DISASTER_TYPES.get('wind', 3):
            return {
                1: 1.0,
                2: 1.1,
                3: 1.0,
                4: 0.85,
                0: 1.0,
            }.get(material_code, 1.0)

        return 1.0

    def _physics_severity_estimate(
        self,
        material_code,
        distance_to_epicenter,
        fragility_index,
        wall_quality,
        num_openings,
        disaster_code,
        disaster_intensity,
    ):
        """Estimate severity from engineered risk terms used for synthetic labels and calibration."""
        intensity_norm = np.clip(disaster_intensity / 100.0, 0.0, 1.0)
        if disaster_code == self.DISASTER_TYPES.get('earthquake', 2):
            hazard = intensity_norm ** 1.22
        elif disaster_code == self.DISASTER_TYPES.get('flood', 1):
            hazard = intensity_norm ** 1.12
        elif disaster_code == self.DISASTER_TYPES.get('fire', 0):
            hazard = intensity_norm ** 1.08
        else:
            hazard = intensity_norm ** 1.45

        distance = max(0.0, float(distance_to_epicenter))
        dist_scale = self.DISASTER_DISTANCE_SCALE.get(int(disaster_code), 10.0)
        proximity = 1.0 / (1.0 + (distance / max(1.0, dist_scale)) ** 1.55)

        material_base = self.MATERIAL_BASE_VULNERABILITY.get(int(material_code), 0.9)
        material_disaster = self._get_disaster_material_multiplier(disaster_code, int(material_code))

        fragility = np.clip(float(fragility_index), 0.0, 1.0)
        wall_q = np.clip(float(wall_quality), 0.0, 1.0)
        fragility_term = 0.5 + 0.8 * fragility
        quality_term = 1.2 - 0.6 * wall_q
        openings_term = 0.9 + 0.045 * np.clip(float(num_openings), 0.0, 10.0)

        if disaster_code == self.DISASTER_TYPES.get('earthquake', 2):
            fragility_term = 0.6 + 1.05 * fragility
            quality_term = 1.35 - 0.78 * wall_q
            openings_term = 0.96 + 0.02 * np.clip(float(num_openings), 0.0, 10.0)
        elif disaster_code == self.DISASTER_TYPES.get('fire', 0):
            fragility_term = 0.58 + 0.95 * fragility
            quality_term = 1.3 - 0.75 * wall_q
            openings_term = 0.95 + 0.05 * np.clip(float(num_openings), 0.0, 10.0)
            hazard *= (0.84 + 0.48 * np.sqrt(intensity_norm))
        elif disaster_code == self.DISASTER_TYPES.get('flood', 1):
            fragility_term = 0.55 + 0.9 * fragility
            quality_term = 1.28 - 0.72 * wall_q
            openings_term = 0.92 + 0.035 * np.clip(float(num_openings), 0.0, 10.0)
            hazard *= (0.82 + 0.52 * (intensity_norm ** 0.7))
        elif disaster_code == self.DISASTER_TYPES.get('earthquake', 2):
            hazard *= (0.86 + 0.46 * (intensity_norm ** 0.65))

        severity = 100.0 * hazard * proximity * material_base * material_disaster * fragility_term * quality_term * openings_term
        return float(np.clip(severity, 0.0, 100.0))

    def _calibrate_severity(
        self,
        rf_severity,
        building_material,
        distance_to_epicenter,
        fragility_index,
        wall_quality,
        num_openings,
        disaster_type,
        disaster_intensity,
    ):
        """Blend RF output with physics prior so high-intensity scenarios are not systematically underpredicted."""
        material_code = self.MATERIALS.get(str(building_material).lower(), 0)
        disaster_code = self.DISASTER_TYPES.get(str(disaster_type).lower(), 4)

        physics_prior = self._physics_severity_estimate(
            material_code=material_code,
            distance_to_epicenter=distance_to_epicenter,
            fragility_index=fragility_index,
            wall_quality=wall_quality,
            num_openings=num_openings,
            disaster_code=disaster_code,
            disaster_intensity=disaster_intensity,
        )

        intensity_norm = np.clip(float(disaster_intensity) / 100.0, 0.0, 1.0)
        if disaster_code == self.DISASTER_TYPES.get('earthquake', 2):
            blend_weight = 0.5 + 0.5 * intensity_norm
        elif disaster_code == self.DISASTER_TYPES.get('fire', 0):
            blend_weight = 0.4 + 0.65 * intensity_norm
        elif disaster_code == self.DISASTER_TYPES.get('flood', 1):
            blend_weight = 0.4 + 0.62 * intensity_norm
        else:
            blend_weight = 0.35 + 0.55 * intensity_norm
        blend_weight = float(np.clip(blend_weight, 0.25, 0.95))
        calibrated = (1.0 - blend_weight) * float(rf_severity) + blend_weight * physics_prior

        if intensity_norm >= 0.70 and float(distance_to_epicenter) <= 10.0:
            floor = 28.0 + 28.0 * float(fragility_index) - 12.0 * float(wall_quality) + 35.0 * (intensity_norm - 0.70)
            calibrated = max(calibrated, floor)

        if disaster_code in (self.DISASTER_TYPES.get('fire', 0), self.DISASTER_TYPES.get('flood', 1)) and intensity_norm >= 0.68:
            distance = max(0.0, float(distance_to_epicenter))
            dist_scale = self.DISASTER_DISTANCE_SCALE.get(int(disaster_code), 12.0)
            spread = 1.0 / (1.0 + (distance / max(1.0, dist_scale * 1.25)) ** 1.1)
            base_floor = 32.0 + 32.0 * float(fragility_index) - 14.0 * float(wall_quality) + 32.0 * (intensity_norm - 0.68)
            calibrated = max(calibrated, base_floor * (0.7 + 0.45 * spread))

        if disaster_code == self.DISASTER_TYPES.get('earthquake', 2) and intensity_norm >= 0.70:
            distance = max(0.0, float(distance_to_epicenter))
            dist_scale = self.DISASTER_DISTANCE_SCALE.get(int(disaster_code), 8.0)
            eq_spread = 0.38 + 0.82 / (1.0 + (distance / max(1.0, dist_scale * 1.25)) ** 1.1)
            eq_floor = 35.0 + 35.0 * float(fragility_index) - 15.0 * float(wall_quality) + 32.0 * (intensity_norm - 0.70)
            calibrated = max(calibrated, eq_floor * eq_spread)

        if disaster_code == self.DISASTER_TYPES.get('earthquake', 2):
            if intensity_norm < 0.14:      # Micro / Minor
                band_floor = 8.0
            elif intensity_norm < 0.24:    # Minor / Light
                band_floor = 14.0
            elif intensity_norm < 0.40:    # Light
                band_floor = 22.0
            elif intensity_norm < 0.55:    # Moderate
                band_floor = 34.0
            elif intensity_norm < 0.72:    # Strong
                band_floor = 48.0
            elif intensity_norm < 0.88:    # Major
                band_floor = 63.0
            else:                           # Great
                band_floor = 78.0
            distance = max(0.0, float(distance_to_epicenter))
            dist_scale = self.DISASTER_DISTANCE_SCALE.get(int(disaster_code), 8.0)
            band_spread = 0.32 + 0.84 / (1.0 + (distance / max(1.0, dist_scale * 1.35)) ** 1.15)
            band_floor += 18.0 * float(fragility_index) - 8.0 * float(wall_quality)
            calibrated = max(calibrated, band_floor * band_spread)

        if disaster_code == self.DISASTER_TYPES.get('fire', 0) and intensity_norm >= 0.75:
            distance = max(0.0, float(distance_to_epicenter))
            dist_scale = self.DISASTER_DISTANCE_SCALE.get(int(disaster_code), 13.5)
            d_amp = 0.45 + 0.75 / (1.0 + (distance / max(1.0, dist_scale * 1.35)) ** 1.0)
            fire_floor = 50.0 + 26.0 * float(fragility_index) - 14.0 * float(wall_quality) + 20.0 * (intensity_norm - 0.75)
            calibrated = max(calibrated, fire_floor * d_amp)

        if disaster_code == self.DISASTER_TYPES.get('flood', 1) and intensity_norm >= 0.72:
            distance = max(0.0, float(distance_to_epicenter))
            dist_scale = self.DISASTER_DISTANCE_SCALE.get(int(disaster_code), 17.0)
            d_amp = 0.5 + 0.7 / (1.0 + (distance / max(1.0, dist_scale * 1.4)) ** 0.95)
            flood_floor = 46.0 + 24.0 * float(fragility_index) - 12.0 * float(wall_quality) + 18.0 * (intensity_norm - 0.72)
            calibrated = max(calibrated, flood_floor * d_amp)

        if intensity_norm >= 0.90:
            distance = max(0.0, float(distance_to_epicenter))
            dist_scale = self.DISASTER_DISTANCE_SCALE.get(int(disaster_code), 10.0)
            distance_factor = 0.35 + 0.8 / (1.0 + (distance / max(1.0, dist_scale * 1.8)) ** 0.9)
            global_floor = 42.0 + 30.0 * float(fragility_index) - 16.0 * float(wall_quality) + 18.0 * (intensity_norm - 0.90)
            calibrated = max(calibrated, global_floor * distance_factor)

        return float(np.clip(calibrated, 0.0, 100.0))
    
    def predict_batch(self, areas_data):
        """
        Predict damage for multiple areas.
        
        Args:
            areas_data: List of dicts with area parameters
        
        Returns:
            List of prediction results
        """
        results = []
        for area in areas_data:
            result = self.predict_damage(
                area_width=area.get('width', 5),
                area_depth=area.get('depth', 5),
                area_height=area.get('height', 3),
                building_material=area.get('material', 'unknown'),
                distance_to_epicenter=area.get('distance', 10),
                fragility_index=area.get('fragility', 0.7),
                wall_quality=area.get('wall_quality', 0.7),
                num_openings=area.get('openings', 2),
                disaster_type=area.get('disaster_type', 'fire'),
                disaster_intensity=area.get('intensity', 70)
            )
            results.append(result)
        return results
    
    def _get_risk_level(self, severity):
        """Convert severity score to risk level."""
        if severity < 20:
            return 'Low'
        elif severity < 40:
            return 'Moderate'
        elif severity < 60:
            return 'High'
        elif severity < 80:
            return 'Very High'
        else:
            return 'Critical'
    
    def save_model(self, filepath_prefix=None):
        """Save trained models to file."""
        if filepath_prefix is None:
            filepath_prefix = os.path.join(self.model_dir, "damage_predictor")
        
        classifier_path = filepath_prefix + "_classifier.pkl"
        regressor_path = filepath_prefix + "_regressor.pkl"
        scaler_path = filepath_prefix + "_scaler.pkl"
        
        with open(classifier_path, 'wb') as f:
            pickle.dump(self.damage_classifier, f)
        
        with open(regressor_path, 'wb') as f:
            pickle.dump(self.damage_regressor, f)
        
        with open(scaler_path, 'wb') as f:
            pickle.dump(self.feature_scaler, f)
        
        print(f"Models saved to {filepath_prefix}*")
    
    def load_model(self, filepath_prefix=None):
        """Load trained models from file."""
        if filepath_prefix is None:
            filepath_prefix = os.path.join(self.model_dir, "damage_predictor")
        
        classifier_path = filepath_prefix + "_classifier.pkl"
        regressor_path = filepath_prefix + "_regressor.pkl"
        scaler_path = filepath_prefix + "_scaler.pkl"
        
        with open(classifier_path, 'rb') as f:
            self.damage_classifier = pickle.load(f)
        
        with open(regressor_path, 'rb') as f:
            self.damage_regressor = pickle.load(f)
        
        with open(scaler_path, 'rb') as f:
            self.feature_scaler = pickle.load(f)
        
        self.is_trained = True
        print(f"Models loaded from {filepath_prefix}*")
    
    def get_model_info(self):
        """Return information about trained model."""
        return {
            'is_trained': self.is_trained,
            'n_trees': self.n_trees,
            'n_features': len(self.feature_names),
            'feature_names': self.feature_names,
            'damage_classes': self.DAMAGE_CLASSES
        }


if __name__ == "__main__":
    print("Building Damage Predictor Module")
    print("Import this module to use in Blender or Flask server")
