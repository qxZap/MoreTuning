import os
import argparse

def delete_bak_files(root_dir):
    deleted_files = 0
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.lower().endswith('.bak'):
                file_path = os.path.join(dirpath, filename)
                try:
                    os.remove(file_path)
                    print(f"Deleted: {file_path}")
                    deleted_files += 1
                except Exception as e:
                    print(f"Failed to delete {file_path}: {e}")
    print(f"\nTotal .bak files deleted: {deleted_files}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recursively delete .bak files.")
    parser.add_argument("target", help="Path to the directory to clean .bak files from")

    args = parser.parse_args()
    target_dir = os.path.abspath(args.target)

    if not os.path.isdir(target_dir):
        print(f"Error: '{target_dir}' is not a valid directory.")
    else:
        delete_bak_files(target_dir)
