# Placeholder for __init__.py files to make directories packages
import os
from pathlib import Path

def create_inits(root: str):
    for path, dirs, files in os.walk(root):
        if "__pycache__" in path: continue
        init_file = Path(path) / "__init__.py"
        if not init_file.exists():
            with open(init_file, "w") as f:
                pass

if __name__ == "__main__":
    create_inits("app")
