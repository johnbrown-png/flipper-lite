"""
Shared utility functions for both pipeline and search app
"""
import json
from pathlib import Path
from typing import List, Dict


def load_json_file(file_path: Path) -> Dict:
    """Load and return JSON file contents"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {file_path}: {e}")
        return {}


def save_json_file(data: Dict, file_path: Path):
    """Save data to JSON file"""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_all_json_files(directory: Path, pattern: str = "*.json") -> List[Path]:
    """Get all JSON files from a directory"""
    if not directory.exists():
        return []
    return list(directory.glob(pattern))


def format_duration(seconds: int) -> str:
    """Format duration in seconds to MM:SS format"""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def format_timestamp(seconds: float) -> str:
    """Format timestamp for video display"""
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
