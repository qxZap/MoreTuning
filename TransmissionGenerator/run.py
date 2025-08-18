
import json
import os
import subprocess

NEW_TRANS_FOLDERS = 'new_trans'

def create_folder_if_not_exists(path):
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"Created folder: {path}")
    else:
        print(f"Folder already exists: {path}")

def remove_file_if_exists(filepath):
    if os.path.isfile(filepath):
        os.remove(filepath)

def load_new_transmission(transmission_id, transmission_name):
    data = {}
    with open('NEW_TRANSMISSION.json', 'r') as f:
        data = json.loads(f.read().replace('NEW_TRANSMISSION', transmission_id).replace("new qxZap Transmission", "new qxZap Transmission "+transmission_name))
    return data

def save_transmission(path, content):
    with open(path, 'w+') as f:
       f.write(json.dumps(content, indent=4))

# Name map 2 (asset name + asset path)
# Index 2 (asset and package)
# Serialization too
def load_new_transmission_part(transmission_id, transmission_name, weight, price, req, index, description):
    data = {}
    with open('tranmission_part.json','r') as f:
        data = json.loads(f.read())
    
    data["Name"] = transmission_id
    for row in data['Value']:
        row_name = row.get("Name")
        row_value = row.get("Value")

        if row_name == 'Name':
            row['CultureInvariantString'] = '[MOD] Z> '+transmission_name
        if row_name == 'Desciption':
            row['CultureInvariantString'] = description
        if row_name == 'Cost':
            row['Value'] = price
        if row_name == 'MassKg':
            row['Value'] = weight
        if row_name == 'LevelRequirementToBuy':
            row['Value'][0][1]['Value'] = req
        if row_name == 'TransmissionAsset':
            row['Value'] = index

    return data

# To be used with type_t
def get_clutch_type(clutch_type):
#   ClutchType EMTTransmissionClutchType MultiPlateClutch
#   Type EMTTransmissionType MultiPlateClutch
#   ClutchType EMTTransmissionClutchType TorqueConvertorV2
    clutch_type_name = 'ClutchType'
    enum_type = 'EMTTransmissionClutchType'
    if clutch_type not in ['TorqueConvertorV2', 'MultiPlateClutch']:
        clutch_type_name = 'Type'
        enum_type = 'EMTTransmissionType'
    return {
              "$type": "UAssetAPI.PropertyTypes.Objects.EnumPropertyData, UAssetAPI",
              "EnumType": enum_type,
              "InnerType": "ByteProperty",
              "Name": clutch_type_name,
              "ArrayIndex": 0,
              "IsZero": False,
              "PropertyTagFlags": "None",
              "PropertyTagExtensions": "NoExtension",
              "Value": clutch_type
            }

# 3 (3.5, 100, 4)
def new_gear(index_gear, gear_data):
   ratio, inertia, text = gear_data
   return {
                  "$type": "UAssetAPI.PropertyTypes.Structs.StructPropertyData, UAssetAPI",
                  "StructType": "MHTransmissionGear",
                  "SerializeNone": True,
                  "StructGUID": "{00000000-0000-0000-0000-000000000000}",
                  "SerializationControl": "NoExtension",
                  "Operation": "None",
                  "Name": str(index_gear),
                  "ArrayIndex": 0,
                  "IsZero": True,
                  "PropertyTagFlags": "None",
                  "PropertyTagExtensions": "NoExtension",
                  "Value": [
                    {
                      "$type": "UAssetAPI.PropertyTypes.Objects.FloatPropertyData, UAssetAPI",
                      "Value": ratio,
                      "Name": "GearRatio",
                      "ArrayIndex": 0,
                      "IsZero": False,
                      "PropertyTagFlags": "None",
                      "PropertyTagExtensions": "NoExtension"
                    },
                    {
                      "$type": "UAssetAPI.PropertyTypes.Objects.FloatPropertyData, UAssetAPI",
                      "Value": float(inertia),
                      "Name": "Inertia",
                      "ArrayIndex": 0,
                      "IsZero": False,
                      "PropertyTagFlags": "None",
                      "PropertyTagExtensions": "NoExtension"
                    },
                    {
                      "$type": "UAssetAPI.PropertyTypes.Objects.StrPropertyData, UAssetAPI",
                      "Name": "Name",
                      "ArrayIndex": 0,
                      "IsZero": False,
                      "PropertyTagFlags": "None",
                      "PropertyTagExtensions": "NoExtension",
                      "Value": text
                    }
                  ]
                }


def get_gears(ratios):
   gears = []
   index = 0
   for ratio in ratios:
      gears.append(new_gear(index, ratio))
      index+=1

   return {
              "$type": "UAssetAPI.PropertyTypes.Objects.ArrayPropertyData, UAssetAPI",
              "ArrayType": "StructProperty",
              "Name": "Gears",
              "ArrayIndex": 0,
              "IsZero": False,
              "PropertyTagFlags": "None",
              "PropertyTagExtensions": "NoExtension",
              "Value": gears
   }

def get_def_gear_index(def_index):
   return {
              "$type": "UAssetAPI.PropertyTypes.Objects.IntPropertyData, UAssetAPI",
              "Name": "DefaultGearIndex",
              "ArrayIndex": 0,
              "IsZero": False,
              "PropertyTagFlags": "None",
              "PropertyTagExtensions": "NoExtension",
              "Value": def_index
            }

# TorqueConvertorStallRatioPower 2.0
def get_float_p(name, value):
   return {
              "$type": "UAssetAPI.PropertyTypes.Objects.FloatPropertyData, UAssetAPI",
              "Value": float(value),
              "Name": name,
              "ArrayIndex": 0,
              "IsZero": False,
              "PropertyTagFlags": "None",
              "PropertyTagExtensions": "NoExtension"
            }

def get_transmission_grind():
   return {
              "$type": "UAssetAPI.PropertyTypes.Objects.ObjectPropertyData, UAssetAPI",
              "Name": "GearGrindingSound",
              "ArrayIndex": 0,
              "IsZero": False,
              "PropertyTagFlags": "None",
              "PropertyTagExtensions": "NoExtension",
              "Value": -5
            }

def get_shift_row(shift_time):
   return get_float_p('ShiftTimeSeconds', shift_time)


def get_cvt_input_range(x,y):
   return {
              "$type": "UAssetAPI.PropertyTypes.Structs.StructPropertyData, UAssetAPI",
              "StructType": "Vector2D",
              "SerializeNone": True,
              "StructGUID": "{00000000-0000-0000-0000-000000000000}",
              "SerializationControl": "NoExtension",
              "Operation": "None",
              "Name": "CVT_InputRPMRange",
              "ArrayIndex": 0,
              "IsZero": False,
              "PropertyTagFlags": "None",
              "PropertyTagExtensions": "NoExtension",
              "Value": [
                {
                  "$type": "UAssetAPI.PropertyTypes.Structs.Vector2DPropertyData, UAssetAPI",
                  "Name": "CVT_InputRPMRange",
                  "ArrayIndex": 0,
                  "IsZero": False,
                  "PropertyTagFlags": "None",
                  "PropertyTagExtensions": "NoExtension",
                  "Value": {
                    "$type": "UAssetAPI.UnrealTypes.FVector2D, UAssetAPI",
                    "X": float(x),
                    "Y": float(y)
                  }
                }
              ]
            }

def get_cvt_gear_ratios(x,y):
   return {
              "$type": "UAssetAPI.PropertyTypes.Structs.StructPropertyData, UAssetAPI",
              "StructType": "Vector2D",
              "SerializeNone": True,
              "StructGUID": "{00000000-0000-0000-0000-000000000000}",
              "SerializationControl": "NoExtension",
              "Operation": "None",
              "Name": "CVT_GearRatios",
              "ArrayIndex": 0,
              "IsZero": False,
              "PropertyTagFlags": "None",
              "PropertyTagExtensions": "NoExtension",
              "Value": [
                {
                  "$type": "UAssetAPI.PropertyTypes.Structs.Vector2DPropertyData, UAssetAPI",
                  "Name": "CVT_GearRatios",
                  "ArrayIndex": 0,
                  "IsZero": False,
                  "PropertyTagFlags": "None",
                  "PropertyTagExtensions": "NoExtension",
                  "Value": {
                    "$type": "UAssetAPI.UnrealTypes.FVector2D, UAssetAPI",
                    "X": float(x),
                    "Y": float(y)
                  }
                }
              ]
            }

def run_uassetgui(json_path, output_path, game_name="MotorTown"):
    try:
        subprocess.run([
            "..\\UAssetGUI.exe",
            "fromjson",
            json_path,
            output_path,
            game_name
        ], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Command failed with return code {e.returncode}")
        return False
    except FileNotFoundError:
        print("UAssetGUI.exe not found. Check the path.")

def new_transmission_asset(index, asset_name):
    return {
      "$type": "UAssetAPI.Import, UAssetAPI",
      "ObjectName": asset_name,
      "OuterIndex": index,
      "ClassPackage": "/Script/MotorTown",
      "ClassName": "MTTransmissionDataAsset",
      "PackageName": None,
      "bImportOptional": False
    }

def get_transmission_package_path(asset_name):
    return "/Game/Cars/Parts/Transmission/"+asset_name

def new_package_import(asset_name):
    return {
      "$type": "UAssetAPI.Import, UAssetAPI",
      "ObjectName": get_transmission_package_path(asset_name),
      "OuterIndex": 0,
      "ClassPackage": "/Script/CoreUObject",
      "ClassName": "Package",
      "PackageName": None,
      "bImportOptional": False
    }


transmissions = {}

create_folder_if_not_exists(NEW_TRANS_FOLDERS)

# TorqueConvertorStallRatioPower 1 on default cvt
# TorqueConvertorStallRatioPower 2 on luxury
# TorqueConvertorStallRatioPower 3 on truck

with open('tras_s.json','r') as f:
    transmissions = json.loads(f.read())

r_name_keys ={
    "1":"R",
    "2":"R2",
    "3":"R3",
    "4":"R4",
    "5":"R5",
    "6":"R6",
    "7":"R7",
    "8":"R8"
}

transmission_asset = {}

with open('Transmissions2.json', 'r') as f:
    transmission_asset = json.loads(f.read())

start_index = len(transmission_asset['Imports'])*(-1)-1

imports = transmission_asset['Imports']
NameMap = transmission_asset['NameMap']
CreateBeforeSerializationDependencies = transmission_asset['Exports'][0]['CreateBeforeSerializationDependencies']
parts = transmission_asset['Exports'][0]['Table']['Data']


for trans_key in transmissions:
    new_transmission_path = NEW_TRANS_FOLDERS + '/' + trans_key + '.json'

    transmission = transmissions[trans_key]
    transmission_name = transmission.get('name').replace("_",' ')
    transmission_weight = transmission.get('weight')
    shift_time = transmission.get('shift_time')
    description = transmission.get('desc')

    price = transmission.get('price')
    weight = transmission.get('weight')
    lvl_req = transmission.get('lvl_req')

    TorqueConvertorStallRatioPower = transmission.get('TorqueConvertorStallRatioPower')
    AutoShiftComportRPM = transmission.get('AutoShiftComportRPM')
    TorqueConvertorStallRPM = transmission.get('TorqueConvertorStallRPM')
    TorqueConvertorTorqueRate = transmission.get('TorqueConvertorTorqueRate')
    
    is_auto = False
    if 'auto' in description.lower():
       is_auto = True
    
    is_truck = False
    
    if transmission_weight>120:
        is_truck = True
        TorqueConvertorStallRatioPower = 3
        AutoShiftComportRPM = 1500
        TorqueConvertorTorqueRate = 80
        TorqueConvertorStallRPM = 2000
    else:
        if is_auto:
          TorqueConvertorStallRatioPower = 2
        else:
          TorqueConvertorStallRatioPower = 3
        # TorqueConvertorStallRPM = 7000

    def_gear = 1
    ratios = []

    cvt_imputs = []
    CVT_ClutchCurvePow = None
    cvt_ratios = []

    type_t = None
    
    if 'CVT_ClutchCurvePow' in transmission:
      CVT_ClutchCurvePow = transmission.get('CVT_ClutchCurvePow')
      TorqueConvertorStallRatioPower = 1
      # This might need to be removd  ^^^^

      type_t = 'CVT'
      ratios = [(-1, 100, 'R'),(0,100,'N'),(1,100,'D')]

      CVT_InputRPMRange = transmission.get('CVT_InputRPMRange').replace("_","-")
      cvt_imputs = [int(val) for val in CVT_InputRPMRange.split('-')]

      CVT_GearRatios = transmission.get('CVT_GearRatios').replace("_","-")
      cvt_ratios = [float(val) for val in CVT_GearRatios.split('-')]
    else:
      # could be MultiPlateClutch (lambo transmission DCT) only at cars
      # MultiPlateClutch not at trucks at all??? 
      # TorqueConvertorV2 for TQ
      if TorqueConvertorStallRatioPower == 3:
         type_t = 'MultiPlateClutch'
      if TorqueConvertorStallRatioPower == 2:
         type_t = 'TorqueConvertorV2'

      gear_index = 0      
      for r_ratio in sorted(transmission.get('r_ratios', {}), reverse=True):
          ratio = transmission.get('r_ratios')[r_ratio]
          if ratio>0:
              ratio = ratio*(-1)
          ratios.append((ratio, 100, r_name_keys[r_ratio] ))
          gear_index+=1

      ratios.append((0, 100, 'N'))
      gear_index+=1

      for gear_index in transmission.get('f_ratios'):
          gear_ratio = transmission.get('f_ratios')[gear_index]
          ratios.append((gear_ratio,100,gear_index))

    # Determine default gear index
    for index in range(0,len(ratios)):
       if 'N' in ratios[index]:
          def_gear = index

    new_transmission_json = load_new_transmission(trans_key, transmission_name)
    transmission_values = []
    
    transmission_values.append(get_clutch_type(type_t))
    transmission_values.append(get_gears(ratios))
    transmission_values.append(get_def_gear_index(def_gear))
    transmission_values.append(get_float_p('ShiftTimeSeconds', shift_time))
    
    if AutoShiftComportRPM:
        transmission_values.append(get_float_p('AutoShiftComportRPM', AutoShiftComportRPM))


    if TorqueConvertorStallRPM:
        transmission_values.append(get_float_p('TorqueConvertorStallRPM', TorqueConvertorStallRPM))
    if TorqueConvertorStallRatioPower:
        transmission_values.append(get_float_p('TorqueConvertorStallRatioPower', TorqueConvertorStallRatioPower))
    if TorqueConvertorTorqueRate:
        transmission_values.append(get_float_p('TorqueConvertorTorqueRate', TorqueConvertorTorqueRate))

    if type_t == 'CVT':
        transmission_values.append(get_cvt_input_range(cvt_imputs[0], cvt_imputs[1]))
        transmission_values.append(get_float_p('CVT_ClutchCurvePow', CVT_ClutchCurvePow))
        transmission_values.append(get_cvt_gear_ratios(cvt_ratios[0], cvt_ratios[1]))
    
    transmission_values.append(get_transmission_grind())

    new_transmission_json['Exports'][0]['Data'][0]['Value'] = transmission_values

    save_transmission(new_transmission_path, new_transmission_json)

    conversion = run_uassetgui(new_transmission_path, new_transmission_path.replace('.json', '.uasset'))
    if conversion:
        remove_file_if_exists(new_transmission_path)

        
        new_transmission_asset_to_add = new_transmission_asset(start_index-1, trans_key)
        CreateBeforeSerializationDependencies.append(start_index)
        parts.append(load_new_transmission_part(trans_key, transmission_name,weight, price, lvl_req,start_index, description))
        start_index-=1
        new_import = new_package_import(trans_key)
        start_index-=1

        imports.append(new_transmission_asset_to_add)
        imports.append(new_import)

        NameMap.append(trans_key)
        NameMap.append(get_transmission_package_path(trans_key))

    else:
        print(f'issue with {trans_key}')
    
# NameMap.append('CL_Driver')
# NameMap.append('LevelRequirementToBuy')
transmission_asset['Imports'] = imports
transmission_asset['NameMap'] = NameMap
transmission_asset['Exports'][0]['CreateBeforeSerializationDependencies'] = CreateBeforeSerializationDependencies
transmission_asset['Exports'][0]['Table']['Data'] = parts

with open('Transmissions.json', 'w+') as f:
    f.write(json.dumps(transmission_asset, indent=4))
    # f.write(json.dumps(transmission_asset))