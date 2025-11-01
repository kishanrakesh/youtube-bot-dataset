import json
import os

def ensure_folder_exists(folder_path):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)


def load_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return None


def save_json(filepath, data):
    ensure_folder_exists(os.path.dirname(filepath))
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)