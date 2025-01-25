"""
Configuration loading and validation
"""

import os
import yaml
from typing import Dict, Any

class Config:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.config = self._load_config()
        
        # Set up paths
        self.log_dir = os.path.join(self.base_dir, 'logs')
        self.state_file = os.path.join(self.base_dir, 'state', 'processed_files.json')
        self.credentials_path = os.path.join(self.base_dir, self.config['credentials']['service_account_path'])
        
        # Get folder mappings
        self.folder_mappings = {
            folder_config['google_drive_id']: folder_config['local_path']
            for folder_config in self.config['folders'].values()
        }

    def _load_config(self) -> Dict[str, Any]:
        """Load and validate configuration"""
        try:
            with open(os.path.join(self.base_dir, 'config.yaml'), 'r') as f:
                config = yaml.safe_load(f)
                self._validate_config(config)
                return config
        except FileNotFoundError:
            raise FileNotFoundError("config.yaml not found. Please copy config.example.yaml to config.yaml and update with your settings.")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing config.yaml: {e}")

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate configuration structure"""
        required_keys = ['credentials', 'folders']
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required config key: {key}")
        
        if 'service_account_path' not in config['credentials']:
            raise ValueError("Missing service_account_path in credentials config")

        for folder_name, folder_config in config['folders'].items():
            if 'google_drive_id' not in folder_config:
                raise ValueError(f"Missing google_drive_id for folder {folder_name}")
            if 'local_path' not in folder_config:
                raise ValueError(f"Missing local_path for folder {folder_name}")

    def create_directories(self) -> None:
        """Create necessary directories"""
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        for path in self.folder_mappings.values():
            os.makedirs(path, exist_ok=True)
