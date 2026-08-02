
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Rebase'))
from rebase import fname_base, fnames_in  # noqa: E402

NEW_ENG_FOLDER = 'new_eng'

# NOT the ..\UAssetGUI.exe next to this repo -- that one is v1.0.4 and writes an
# older JSON schema, so anything it exports fails to build again on 0.7.19.
UASSETGUI = r'D:\MT\UAssetGUI.exe'
MAPPINGS = 'MotorTown719'

# Since 0.7.19 the table points at engine assets by soft path -- no import table
# surgery. EnginesIN.json is the mod's engine table minus the EV rows this
# script adds; regenerate it with Rebase/rebuild.py after a game update.
ENGINE_DIR = '/Game/Cars/Parts/Engine/'

def create_folder_if_not_exists(path):
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"Created folder: {path}")
    else:
        print(f"Folder already exists: {path}")

def get_weight(hp_count):
    if hp>=1010:
        return int(49/670*hp_count)
    if hp>=670:
        return int(150/670*hp_count)
    if hp>=300:
        return int(130/300*hp_count)
    return int(60/130*hp_count)

def get_level_req(hp_count):
    return 1+int(hp_count/3)

def get_base_motor(name):
    base_file = None
    with open('Electric_670HP.json', 'r') as f:
        base_file = f.read()
    if base_file:
        base_file = base_file.replace('Electric_670HP', name)
        return json.loads(base_file)
    
def get_level_req_row(level):
    return {
                "$type": "UAssetAPI.PropertyTypes.Objects.MapPropertyData, UAssetAPI",
                "Value": [
                  [
                    {
                      "$type": "UAssetAPI.PropertyTypes.Objects.EnumPropertyData, UAssetAPI",
                      "EnumType": None,
                      "InnerType": None,
                      "Name": "LevelRequirementToBuy",
                      "ArrayIndex": 0,
                      "IsZero": False,
                      "PropertyTagFlags": "None",
                      "PropertyTagExtensions": "NoExtension",
                      "Value": "CL_Driver"
                    },
                    {
                      "$type": "UAssetAPI.PropertyTypes.Objects.IntPropertyData, UAssetAPI",
                      "Name": "LevelRequirementToBuy",
                      "ArrayIndex": 0,
                      "IsZero": False,
                      "PropertyTagFlags": "None",
                      "PropertyTagExtensions": "NoExtension",
                      "Value": level
                    }
                  ]
                ],
                "KeysToRemove": [],
                "Name": "LevelRequirementToBuy",
                "ArrayIndex": 0,
                "IsZero": False,
                "PropertyTagFlags": "None",
                "PropertyTagExtensions": "NoExtension"
              }

def get_engine_package_path(asset_name):
    return ENGINE_DIR + asset_name

def soft_object_path(asset_name):
    return {
        "$type": "UAssetAPI.PropertyTypes.Objects.FSoftObjectPath, UAssetAPI",
        "AssetPath": {
            "$type": "UAssetAPI.PropertyTypes.Objects.FTopLevelAssetPath, UAssetAPI",
            "PackageName": get_engine_package_path(asset_name),
            "AssetName": asset_name,
        },
        "SubPathString": None,
    }

def save_engine(path, content):
    with open(path, 'w+') as f:
       f.write(json.dumps(content, indent=4))

def copy_all_files(src_folder, dest_folder):
    """
    Copy all files from src_folder to dest_folder.
    If dest_folder does not exist, it will be created.
    Existing files with the same name will be overwritten.
    """
    # Ensure source exists
    if not os.path.exists(src_folder):
        raise FileNotFoundError(f"Source folder not found: {src_folder}")

    # Create destination folder if it doesn't exist
    os.makedirs(dest_folder, exist_ok=True)

    # Iterate and copy
    for filename in os.listdir(src_folder):
        src_path = os.path.join(src_folder, filename)
        dest_path = os.path.join(dest_folder, filename)

        if os.path.isfile(src_path):  # only copy files
            shutil.copy2(src_path, dest_path)
            print(f"Copied: {src_path} -> {dest_path}")


def remove_file_if_exists(filepath):
    if os.path.isfile(filepath):
        os.remove(filepath)

def run_uassetgui(json_path, output_path, game_name=MAPPINGS):
    # UAssetGUI is a WinForms app: it exits 0 whether or not it wrote anything,
    # so the only reliable success check is the output file existing.
    remove_file_if_exists(output_path)
    try:
        subprocess.run([UASSETGUI, "fromjson", json_path, output_path, game_name], check=True)
    except FileNotFoundError:
        raise SystemExit(f"{UASSETGUI} not found. Check the path.")
    return os.path.exists(output_path)

def load_new_engine_part(transmission_id, engine_name, weight, price, req, index, description):
    data = {}
    with open('NEW_ENGINE.json','r') as f:
        data = json.loads(f.read())
    
    data["Name"] = transmission_id
    for row in data['Value']:
        row_name = row.get("Name")
        row_value = row.get("Value")

        if row_name == 'Name':
            row['CultureInvariantString'] = engine_name
        if row_name == 'Desciption':
            row['CultureInvariantString'] = description
        if row_name == 'Cost':
            row['Value'] = price
        if row_name == 'MassKg':
            row['Value'] = weight
        if row_name == 'LevelRequirementToBuy':
            row['Value'] = get_level_req_row(req)['Value']
        if row_name == 'EngineAsset':
            row['Value'] = soft_object_path(transmission_id)

    return data

engine_listing_asset = {}
create_folder_if_not_exists(NEW_ENG_FOLDER)

with open('EnginesIN.json', 'r') as f:
    engine_listing_asset = json.loads(f.read())

NameMap = engine_listing_asset['NameMap']
parts = engine_listing_asset['Exports'][0]['Table']['Data']
existing_rows = {row['Name'] for row in parts}
new_names = []

motors = None
with open('motors.json', 'r') as f:
    motors = json.loads(f.read())

if motors:
    motors = {k: v for k, v in motors.items() if "EV" in k}
    motors = dict(sorted(motors.items(), key=lambda x: x[1]["hp"]))

    for motor_key in motors:
        new_engine_path = NEW_ENG_FOLDER + '/' + motor_key + '.json'

        motor = motors[motor_key]
        hp = motor.get("hp")
        name = motor.get("name")

        # if name.startswith('EV '):
        #     name = name[3:]

        name_parts = name.split(',')
        name = f'{name_parts[0]} {name_parts[1].upper()}'
        
        while '  ' in name:
            name = name.replace('  ',' ')

        Inertia = float(int(3000/670*hp))
        StarterTorque = 0
        StarterRPM = 0

        MaxTorque = float(int(9020000/670*hp/21000*20000))
        MaxRPM = float(int(20000))

        FrictionCoulombCoeff = 100
        FrictionViscosityCoeff = 100
        IdleThrottle = 0

        extra_weight = 0
        range_gain = 0

        description = 'EV Engine'

        FuelConsumptionCoef = 1.0
        if 'FuelConsumptionCoef' in motor:
            FuelConsumptionCoef = motor['FuelConsumptionCoef']
            extra_weight = (1 - FuelConsumptionCoef) * 500
            range_gain = (1 / FuelConsumptionCoef - 1) * 100
        
        if range_gain:
            description = f'EV Engine +{int(range_gain)}% Range'

        FuelConsumption = float(int(hp/3*FuelConsumptionCoef))
        BlipThrottle = 0
        MaxRegenTorqueRatio = 0.3
        MotorMaxPower = float(int(5050000/670*hp))
        MotorMaxVoltage = float(int(6700000/670*hp))

        hp_price_mult = 1
        if hp>2000:
            hp_price_mult = 5.2
        elif hp > 1000:
            hp_price_mult = 3.1
        elif hp>500:
            hp_price_mult = 1.9

        price = int((Inertia*10 + MotorMaxPower/10000 + MotorMaxVoltage/10000 + hp*100)*hp_price_mult )

        new_engine_json = get_base_motor(motor_key)
        for row in new_engine_json['Exports'][0]['Data'][0]['Value']:
            row_name = row.get("Name")
            row_val = row.get('Value')

            if row_name == 'Inertia':
                row["Value"] = Inertia

            if row_name == 'MaxTorque':
                row["Value"] = MaxTorque

            if row_name == 'MaxRPM':
                row["Value"] = MaxRPM

            if row_name == 'FuelConsumption':
                row["Value"] = FuelConsumption

            if row_name == 'MaxRegenTorqueRatio':
                row["Value"] = MaxRegenTorqueRatio

            if row_name == 'MotorMaxPower':
                row["Value"] = MotorMaxPower

            if row_name == 'MotorMaxVoltage':
                row["Value"] = MotorMaxVoltage
        
        save_engine(new_engine_path, new_engine_json)
        conversion = run_uassetgui(new_engine_path, new_engine_path.replace('.json', '.uasset'))
        if conversion:
            remove_file_if_exists(new_engine_path)

            if motor_key in existing_rows:
                print(f'skipping {motor_key}: EnginesIN.json already has that row')
                continue

            new_row = load_new_engine_part(motor_key, name, get_weight(hp)+extra_weight, price,
                                           get_level_req(hp), None, description)
            parts.append(new_row)
            # Every FName the row touches has to be in the map or UAssetGUI writes
            # nothing at all. Only the base goes in: "Foo_12" is stored as "Foo" + 12.
            new_names += [fname_base(n) for n in (motor_key, *fnames_in(new_row))]

        else:
            print(f'issue with {motor_key}')

# New names belong in the block the header counts as referenced by export data,
# which vanilla keeps at the front of the map.
boundary = engine_listing_asset['NamesReferencedFromExportDataCount']
fresh = [n for n in dict.fromkeys(new_names) if n not in set(NameMap)]
engine_listing_asset['NameMap'] = NameMap[:boundary] + fresh + NameMap[boundary:]
engine_listing_asset['NamesReferencedFromExportDataCount'] = boundary + len(fresh)
engine_listing_asset['Exports'][0]['Table']['Data'] = parts

with open('Engines.json', 'w+') as f:
    f.write(json.dumps(engine_listing_asset, indent=4))

copy_all_files(
    r"new_eng",
    r"..\qxZap_MoreTuning_P\MotorTown\Content\Cars\Parts\Engine"
)
shutil.rmtree('new_eng')


