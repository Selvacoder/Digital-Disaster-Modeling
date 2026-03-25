"""
Q-Learning Based Pathfinding for Optimal Evacuation Routes
Learns optimal evacuation paths considering disaster zones and exit accessibility.

Author: ML Integration Module
"""

import numpy as np
import json
import os
from collections import defaultdict
import pickle


class QLearningPathfinder:
    """
    Q-Learning based pathfinder that learns optimal evacuation routes.
    
    State: (x, y, disaster_proximity_zone)
    Actions: 8 directional movements (4 cardinal + 4 diagonal)
    Rewards: 
        - Moving toward exit: +1
        - Moving away from hazard: +0.5
        - Safe area reached: +100
        - Obstacle collision: -10
        - Hazard zone entry: -50
    """
    
    def __init__(self, grid_resolution=0.5, learning_rate=0.1, discount_factor=0.9, 
                 epsilon=0.1, cache_dir="Models/qlearning_qtables"):
        """
        Initialize Q-Learning pathfinder.
        
        Args:
            grid_resolution: Size of grid cells in meters
            learning_rate: Alpha parameter for Q-learning (0-1)
            discount_factor: Gamma parameter for future reward (0-1)
            epsilon: Exploration rate for epsilon-greedy strategy
            cache_dir: Directory to save/load Q-tables
        """
        self.grid_resolution = grid_resolution
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.epsilon = epsilon
        self.cache_dir = cache_dir
        
        # Action set: 8 directions
        self.actions = [
            (0, 1),    # Right
            (0, -1),   # Left
            (1, 0),    # Up
            (-1, 0),   # Down
            (1, 1),    # Diagonal up-right
            (1, -1),   # Diagonal up-left
            (-1, 1),   # Diagonal down-right
            (-1, -1),  # Diagonal down-left
        ]
        
        # Q-table: maps state -> action -> Q-value
        self.q_table = defaultdict(lambda: defaultdict(float))
        self.visit_counts = defaultdict(int)
        self.episodes_trained = 0
        
        # Create cache directory if needed
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
    
    def _discretize_position(self, x, y):
        """Convert continuous coordinates to grid indices."""
        return (int(x / self.grid_resolution), int(y / self.grid_resolution))
    
    def _create_state(self, x, y, disaster_zones):
        """
        Create state tuple from position and disaster info.
        disaster_zones: list of (center_x, center_y, radius, intensity)
        """
        grid_x, grid_y = self._discretize_position(x, y)
        
        # Determine proximity zone (0=far, 1=medium, 2=close)
        min_distance = float('inf')
        for dz_x, dz_y, dz_radius, _ in disaster_zones:
            dist = np.sqrt((x - dz_x)**2 + (y - dz_y)**2)
            min_distance = min(min_distance, dist - dz_radius)
        
        if min_distance > 10:
            proximity = 0  # Safe distance
        elif min_distance > 2:
            proximity = 1  # Medium risk
        else:
            proximity = 2  # High risk
        
        return (grid_x, grid_y, proximity)
    
    def _get_best_action(self, state):
        """Get best action for state (epsilon-greedy)."""
        if np.random.random() < self.epsilon:
            return np.random.choice(len(self.actions))
        
        q_values = [self.q_table[state][a] for a in range(len(self.actions))]
        return np.argmax(q_values)
    
    def _calculate_reward(self, current_pos, next_pos, grid, disaster_zones, exit_pos, goal_reached=False):
        """
        Calculate reward for transition.
        
        Args:
            current_pos: (x, y) current position
            next_pos: (x, y) next position
            grid: navigation grid (0=obstacle, 1=walkable, 2=hazard)
            disaster_zones: list of active disaster zones
            exit_pos: (x, y) nearest exit/safe zone
            goal_reached: whether exit was reached
        
        Returns:
            reward value
        """
        reward = 0
        
        # Collision penalty
        try:
            gx, gy = self._discretize_position(next_pos[0], next_pos[1])
            if grid[gy][gx] == 0:  # Obstacle
                return -10
        except (IndexError, TypeError):
            pass
        
        # Goal reached (huge reward)
        if goal_reached:
            return 100
        
        # Distance to exit
        dist_reduction = (
            np.sqrt((current_pos[0] - exit_pos[0])**2 + (current_pos[1] - exit_pos[1])**2) -
            np.sqrt((next_pos[0] - exit_pos[0])**2 + (next_pos[1] - exit_pos[1])**2)
        )
        reward += dist_reduction * 0.5  # Reward moving toward exit
        
        # Hazard avoidance
        for dz_x, dz_y, dz_radius, intensity in disaster_zones:
            dist_to_hazard = np.sqrt((next_pos[0] - dz_x)**2 + (next_pos[1] - dz_y)**2)
            if dist_to_hazard < dz_radius:
                reward += -50  # Heavy penalty for entering hazard
            elif dist_to_hazard < dz_radius + 5:
                reward += -10 * (1 - (dist_to_hazard - dz_radius) / 5)  # Proximity penalty
            else:
                reward += 0.2  # Small reward for being away from hazard
        
        return reward
    
    def train_episodes(self, building_grid, disaster_zones, exit_positions, 
                      start_positions, num_episodes=100):
        """
        Train Q-learning model with simulated evacuation scenarios.
        
        Args:
            building_grid: 2D array of obstacle map
            disaster_zones: list of (center_x, center_y, radius, intensity)
            exit_positions: list of (x, y) safe exit coordinates
            start_positions: list of (x, y) starting positions
            num_episodes: number of training episodes
        """
        print(f"Training Q-Learning model for {num_episodes} episodes...")
        
        for episode in range(num_episodes):
            # Random starting position and exit
            start_pos = start_positions[np.random.randint(len(start_positions))]
            exit_pos = exit_positions[np.random.randint(len(exit_positions))]
            
            current_pos = start_pos
            state = self._create_state(current_pos[0], current_pos[1], disaster_zones)
            
            # Episode simulation
            for step in range(100):  # Max 100 steps per episode
                action = self._get_best_action(state)
                dx, dy = self.actions[action]
                next_x = current_pos[0] + dx * self.grid_resolution
                next_y = current_pos[1] + dy * self.grid_resolution
                next_pos = (next_x, next_y)
                
                # Check if goal reached
                goal_reached = (
                    np.sqrt((next_x - exit_pos[0])**2 + (next_y - exit_pos[1])**2) < 1.0
                )
                
                # Calculate reward
                reward = self._calculate_reward(current_pos, next_pos, building_grid, 
                                              disaster_zones, exit_pos, goal_reached)
                
                # Get next state
                next_state = self._create_state(next_x, next_y, disaster_zones)
                
                # Q-Learning update: Q(s,a) = Q(s,a) + α[r + γ max Q(s',a') - Q(s,a)]
                old_q = self.q_table[state][action]
                max_next_q = max([self.q_table[next_state][a] for a in range(len(self.actions))], 
                                default=0)
                new_q = old_q + self.learning_rate * (reward + self.discount_factor * max_next_q - old_q)
                self.q_table[state][action] = new_q
                
                current_pos = next_pos
                state = next_state
                self.visit_counts[state] += 1
                
                if goal_reached:
                    break
            
            self.episodes_trained += 1
            if (episode + 1) % 10 == 0:
                print(f"  Episode {episode + 1}/{num_episodes} completed")
    
    def find_path(self, building_grid, start_pos, exit_pos, disaster_zones, max_steps=200):
        """
        Find optimal path from start to exit using trained Q-values.
        
        Args:
            building_grid: 2D array of obstacle map
            start_pos: (x, y) starting position
            exit_pos: (x, y) target exit
            disaster_zones: list of active disaster zones
            max_steps: maximum path length
        
        Returns:
            List of (x, y) coordinates for optimal path
        """
        if self.episodes_trained == 0:
            raise ValueError("Model not trained! Call train_episodes() first.")
        
        path = [start_pos]
        current_pos = start_pos
        state = self._create_state(current_pos[0], current_pos[1], disaster_zones)
        
        for _ in range(max_steps):
            # Use greedy policy (no exploration during inference)
            old_epsilon = self.epsilon
            self.epsilon = 0
            action = self._get_best_action(state)
            self.epsilon = old_epsilon
            
            dx, dy = self.actions[action]
            next_x = current_pos[0] + dx * self.grid_resolution
            next_y = current_pos[1] + dy * self.grid_resolution
            next_pos = (next_x, next_y)
            
            path.append(next_pos)
            current_pos = next_pos
            
            # Check if reached goal
            if np.sqrt((next_x - exit_pos[0])**2 + (next_y - exit_pos[1])**2) < 1.0:
                break
            
            state = self._create_state(next_x, next_y, disaster_zones)
        
        return path
    
    def save_model(self, filepath=None):
        """Save Q-table and parameters to file."""
        if filepath is None:
            filepath = os.path.join(self.cache_dir, "qlearning_model.pkl")
        
        model_data = {
            'q_table': dict(self.q_table),
            'visit_counts': dict(self.visit_counts),
            'episodes_trained': self.episodes_trained,
            'learning_rate': self.learning_rate,
            'discount_factor': self.discount_factor,
            'epsilon': self.epsilon,
            'grid_resolution': self.grid_resolution,
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        print(f"Model saved to {filepath}")
    
    def load_model(self, filepath=None):
        """Load Q-table and parameters from file."""
        if filepath is None:
            filepath = os.path.join(self.cache_dir, "qlearning_model.pkl")
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"No model found at {filepath}")
        
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)
        
        self.q_table = defaultdict(lambda: defaultdict(float), model_data['q_table'])
        self.visit_counts = defaultdict(int, model_data['visit_counts'])
        self.episodes_trained = model_data['episodes_trained']
        self.learning_rate = model_data['learning_rate']
        self.discount_factor = model_data['discount_factor']
        self.epsilon = model_data['epsilon']
        self.grid_resolution = model_data['grid_resolution']
        
        print(f"Model loaded from {filepath} (trained for {self.episodes_trained} episodes)")
    
    def get_model_stats(self):
        """Return statistics about the trained model."""
        return {
            'states_explored': len(self.q_table),
            'episodes_trained': self.episodes_trained,
            'avg_q_value': np.mean([q for state_dict in self.q_table.values() 
                                    for q in state_dict.values()]) if self.q_table else 0,
            'learning_rate': self.learning_rate,
            'discount_factor': self.discount_factor,
        }


if __name__ == "__main__":
    # Example usage
    print("Q-Learning Pathfinder Module")
    print("Import this module to use in Blender or Flask server")
