import os

def remove_json_files(root_dir: str) -> None:
    """Recursively remove all .json files from the root directory and its subdirectories."""
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".json"):
                file_path = os.path.join(root, file)
                os.remove(file_path)

if __name__ == "__main__":
    root_dir = "qxZap_MoreTuning_P"
    remove_json_files(root_dir)