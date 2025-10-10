import os
import subprocess
import json
import shutil

# Constants
GAME_ROOT = r'D:\MT\Output\Exports\MotorTown'
MOD_FOLDER_NAME = 'qxZap_SirensUnlocked_P'
UASSET_GUI_PATH = 'UAssetGUI.exe'
REPACK_PATH = 'repak.exe'  # Not used in this script, but defined as per request
UE_VER = 'VER_UE5_5'
MAPPINGS = 'MotorTown'
LOG_FILE = 'conversion_log.txt'  # Define a log file path
HERE = 'D:\MT\MoreTuning\\'

def get_siren():
    return {
        "$type": "UAssetAPI.PropertyTypes.Objects.SetPropertyData, UAssetAPI",
        "ArrayType": "EnumProperty",
        "Name": "DefaultVehicleFeatures",
        "ArrayIndex": 0,
        "IsZero": False,
        "PropertyTagFlags": "None",
        "PropertyTagExtensions": "NoExtension",
        "Value": [
            {
                "$type": "UAssetAPI.PropertyTypes.Objects.EnumPropertyData, UAssetAPI",
                "EnumType": "EMTVehicleFeature",
                "InnerType": "ByteProperty",
                "Name": "0",
                "ArrayIndex": 0,
                "IsZero": False,
                "PropertyTagFlags": "None",
                "PropertyTagExtensions": "NoExtension",
                "Value": "VF_Siren"
            }
        ]
    }

# Function to convert uasset to json at original location
def run_uasset_tojson(uasset_path):
    json_output = uasset_path.replace('.uasset', '.json')
    cmd = [
        UASSET_GUI_PATH,
        'tojson',
        uasset_path,
        json_output,
        UE_VER,
        MAPPINGS
    ]
    log_file = os.path.join(LOG_FILE)
    with open(log_file, "a") as log:
        try:
            log.write(f"[UAssetGUI] Running: {' '.join(cmd)}\n")
            subprocess.run(cmd, check=True, stdout=log, stderr=log)
            log.write(f"[UAssetGUI] Created JSON for {uasset_path}\n")
        except subprocess.CalledProcessError as e:
            log.write(f"[UAssetGUI] Failed {uasset_path} with code {e.returncode}\n")
            raise
    return json_output

# Function to convert json to uasset
def run_fromjson_to_uasset(json_path):
    json_path = json_path.replace(HERE,'')
    uasset_output = json_path.replace('.json', '.uasset')
    cmd = [
        UASSET_GUI_PATH,
        'fromjson',
        json_path,
        uasset_output,
        MAPPINGS
    ]
    log_file = os.path.join(LOG_FILE)
    with open(log_file, "a") as log:
        try:
            log.write(f"[UAssetGUI] Running: {' '.join(cmd)}\n")
            subprocess.run(cmd, check=True, stdout=log, stderr=log)
            log.write(f"[UAssetGUI] Created Uasset for {json_path}\n")
        except subprocess.CalledProcessError as e:
            log.write(f"[UAssetGUI] Failed {json_path} with code {e.returncode}\n")
            raise

def run_fromjson_to_uasset_advanced(json_path, uasset_path):
    cmd = [
        UASSET_GUI_PATH,
        'fromjson',
        json_path,
        uasset_path,
        MAPPINGS
    ]
    log_file = os.path.join(LOG_FILE)
    with open(log_file, "a") as log:
        try:
            log.write(f"[UAssetGUI] Running: {' '.join(cmd)}\n")
            subprocess.run(cmd, check=True, stdout=log, stderr=log)
            log.write(f"[UAssetGUI] Created Uasset for {json_path}\n")
        except subprocess.CalledProcessError as e:
            log.write(f"[UAssetGUI] Failed {json_path} with code {e.returncode}\n")
            raise

# Function to process JSON data
def process_json_data(json_data):
    """
    Process the JSON data and return the modified version.
    """
    modified_data = json_data
    export_index = 0
    for export in json_data.get('Exports', []):
        export_data_all = export.get('Data', [])
        vehicle_details_found = False
        def_veh_feature_found = False

        for export_data in export_data_all:
            row_name = export_data.get('Name')
            if row_name in ['ExControls', 'BodyMaterialName', 'BodyMaterialNames']:
                vehicle_details_found = True
            if row_name == 'DefaultVehicleFeatures':
                def_veh_feature_found = True

        if vehicle_details_found and not def_veh_feature_found:
            modified_data['Exports'][export_index]['Data'] = [get_siren()] + export_data_all
            break

        export_index += 1

    print(f"Number of exports: {export_index}")
    return modified_data, export_index

ct = 10
ca = 0

# Main script logic
def main():
    global ca,ct
    # Ensure log file exists
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w') as f:
            pass

    # Current directory
    current_dir = os.getcwd()

    # Path to models directory
    models_dir = os.path.join(GAME_ROOT, 'Content', 'Cars', 'Models')

    # List all car folders
    car_folders = [f for f in os.listdir(models_dir) if os.path.isdir(os.path.join(models_dir, f))]
    print(f"Found car folders: {car_folders}")

    for car_folder in car_folders:
        car_dir = os.path.join(models_dir, car_folder)

        # Find qualifying uasset files
        for car_folder in car_folders:
            car_dir = os.path.join(models_dir, car_folder)

            for file_name in os.listdir(car_dir):
                if not file_name.endswith('.uasset'):
                    continue

                base_name = os.path.splitext(file_name)[0]
                uasset_path = os.path.join(car_dir, file_name)
                uexp_path = os.path.join(car_dir, base_name + '.uexp')
                ubulk_path = os.path.join(car_dir, base_name + '.ubulk')

                # Only process files that have .uasset + .uexp but no .ubulk
                if not (os.path.exists(uexp_path) and not os.path.exists(ubulk_path)):
                    continue

                print(f"\n[PROCESSING] {file_name}...")

                json_path = run_uasset_tojson(uasset_path)

                modified_data = {}
                with open(json_path, 'r') as jf:
                    data = json.load(jf)
                    modified_data, export_count = process_json_data(data)

                if modified_data != {}:
                    with open(json_path, 'w+') as jf:
                        json.dump(modified_data, jf, indent=4)

                print(json_path)
                copied_uasset = os.path.join(current_dir, file_name)
                print(copied_uasset)

                ca+=1
                if ca>ct:
                    return 0

                # copied_uasset = os.path.join(current_dir, file_name)
                # copied_uexp = os.path.join(current_dir, base_name + '.uexp')
                # copied_json = os.path.join(current_dir, base_name + '.json')

                # try:
                #     # Step 1: Convert original uasset → json in-place
                #     json_path = run_uasset_tojson(uasset_path)

                #     # Step 2: Copy uasset + uexp + json to current dir
                #     # shutil.copy(uasset_path, copied_uasset)
                #     # shutil.copy(uexp_path, copied_uexp)
                #     shutil.copy(json_path, copied_json)

                #     # Step 3: Process JSON data
                #     with open(copied_json, 'r') as jf:
                #         data = json.load(jf)

                #     modified_data = process_json_data(data)

                #     with open(copied_json, 'w') as jf:
                #         json.dump(modified_data, jf, indent=4)

                #     # Step 4: Convert JSON → UAsset in CURRENT directory
                #     run_fromjson_to_uasset(copied_json)

                #     # Step 5: Prepare mod folder path
                #     rel_path = os.path.relpath(car_dir, os.path.dirname(GAME_ROOT))
                #     mod_car_dir = os.path.join(MOD_FOLDER_NAME, rel_path)
                #     os.makedirs(mod_car_dir, exist_ok=True)

                #     # Step 6: Move new uasset + uexp + json to mod folder
                #     mod_uasset_path = os.path.join(mod_car_dir, file_name)
                #     mod_uexp_path = os.path.join(mod_car_dir, base_name + '.uexp')
                #     shutil.move(copied_uasset, mod_uasset_path)
                #     shutil.move(copied_uexp, mod_uexp_path)
                #     print(f"[SUCCESS] Moved {file_name} + .uexp to {mod_car_dir}")

                #     # Step 7: Cleanup JSON files (optional)
                #     if os.path.exists(copied_json):
                #         os.remove(copied_json)
                #     if os.path.exists(json_path):
                #         os.remove(json_path)

                # except Exception as e:
                #     print(f"[ERROR] Processing {file_name}: {str(e)}")

                #     # Cleanup partial files on failure
                #     for path in [copied_json, copied_uasset, copied_uexp]:
                #         if os.path.exists(path):
                #             os.remove(path)
                #             print(f"[CLEANUP] Removed {path}")

                #     continue

                # finally:
                #     # Cleanup leftover copies in current directory (if any remain)
                #     for path in [copied_json, copied_uasset, copied_uexp]:
                #         if os.path.exists(path):
                #             os.remove(path)
                #             print(f"[FINAL CLEANUP] Removed {path}")

if __name__ == "__main__":
    main()