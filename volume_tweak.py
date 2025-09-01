import os
import subprocess
import json

MULTIPLIER = 0.5  # Static multiplier for tweaking sounds; adjust as needed

def get_subfolders(base_dir: str) -> list[str]:
    """Retrieve a list of subfolder names in the given base directory."""
    return [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]

def find_uasset_files(folder_path: str, prefix: str = None) -> list[str]:
    """
    Find .uasset files in the given folder.
    If prefix is provided, only files starting with that prefix are returned.
    Otherwise, all .uasset files are returned.
    """
    if prefix:
        return [f for f in os.listdir(folder_path) if f.startswith(prefix) and f.endswith(".uasset")]
    else:
        return [f for f in os.listdir(folder_path) if f.endswith(".uasset")]

def convert_uasset_to_json(input_path: str, output_path: str) -> None:
    """Run the UAssetGUI.exe command to convert a .uasset file to .json."""
    command = [".\\UAssetGUI.exe", "tojson", input_path, output_path, "VER_UE5_5", "MotorTown"]
    subprocess.run(command, check=True)

def convert_json_to_uasset(input_path: str, output_path: str) -> None:
    """Run the UAssetGUI.exe command to convert a .json file back to .uasset."""
    command = [".\\UAssetGUI.exe", "fromjson", input_path, output_path, "MotorTown"]
    subprocess.run(command, check=True)

def load_json(file_path: str) -> dict:
    """Load JSON data from a file."""
    with open(file_path, 'r') as f:
        return json.load(f)

def save_json(data: dict, file_path: str) -> None:
    """Save JSON data to a file."""
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

def modify_json(data: dict, multiplier: float) -> dict:
    """Modify the JSON data by adjusting or adding VolumeMultiplier in each export's Data."""
    exports = data.get('Exports', [])
    for export in exports:
        export_data = export.get('Data', [])
        volume_index = None
        first_node_index = None
        for i, prop in enumerate(export_data):
            if 'Name' in prop and prop['Name'] == 'VolumeMultiplier':
                volume_index = i
            if 'Name' in prop and prop['Name'] == 'FirstNode':
                first_node_index = i
        
        if volume_index is not None:
            export_data[volume_index]['Value'] *= multiplier
        elif first_node_index is not None:
            new_prop = {
                "$type": "UAssetAPI.PropertyTypes.Objects.FloatPropertyData, UAssetAPI",
                "Value": 1.0 * multiplier,
                "Name": "VolumeMultiplier",
                "ArrayIndex": 0,
                "IsZero": False if multiplier != 0 else True,
                "PropertyTagFlags": "None",
                "PropertyTagExtensions": "NoExtension"
            }
            export_data.insert(first_node_index + 1, new_prop)
    
    return data

def process_folders(base_dir: str, multiplier: float) -> None:
    """Process all subfolders in the base directory: convert to JSON, modify, and convert back to .uasset."""
    subfolders = get_subfolders(base_dir)
    for subfolder in subfolders:
        subfolder_path = os.path.join(base_dir, subfolder)
        if subfolder == "Bike":
            uasset_files = find_uasset_files(subfolder_path)
        else:
            uasset_files = find_uasset_files(subfolder_path, "SC_")
        
        for uasset_file in uasset_files:
            input_path = os.path.join(subfolder_path, uasset_file)
            output_json_path = input_path.replace(".uasset", ".json")
            output_uasset_path = input_path
            
            # Convert .uasset to .json
            convert_uasset_to_json(input_path, output_json_path)
            
            # Modify the JSON
            json_data = load_json(output_json_path)
            modified_data = modify_json(json_data, multiplier)
            save_json(modified_data, output_json_path)
            
            # Convert modified .json back to .uasset
            convert_json_to_uasset(output_json_path, output_uasset_path)

if __name__ == "__main__":
    base_dir = r"qxZap_MoreTuning_P\MotorTown\Content\Cars\Parts\Engine\Sound"
    process_folders(base_dir, MULTIPLIER)