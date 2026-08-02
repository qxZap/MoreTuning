
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Rebase'))
from rebase import fname_base, fnames_in  # noqa: E402

NEW_TRANS_FOLDERS = 'new_trans'

# Since 0.7.19 the table points at transmission assets by soft path, so the
# vanilla export can be used as the base directly -- no import table surgery,
# and vanilla's own balance changes come along for free. See Rebase/rebase.py.
VANILLA_TABLE = r'D:\MT\Output\Exports\MotorTown\Content\DataAsset\VehicleParts\Transmissions.uasset'
MAPPINGS = 'MotorTown719'
TRANSMISSION_DIR = '/Game/Cars/Parts/Transmission/'

# NOT the ..\UAssetGUI.exe next to this repo -- that one is v1.0.4 and writes an
# older JSON schema, so anything it exports fails to build again on 0.7.19.
UASSETGUI = r'D:\MT\UAssetGUI.exe'

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
            row['CultureInvariantString'] = transmission_name
        if row_name == 'Desciption':
            row['CultureInvariantString'] = description
        if row_name == 'Cost':
            row['Value'] = price
        if row_name == 'MassKg':
            row['Value'] = weight
        if row_name == 'LevelRequirementToBuy':
            row['Value'][0][1]['Value'] = req
        if row_name == 'TransmissionAsset':
            row['Value'] = soft_object_path(transmission_id)

    return data


def soft_object_path(asset_name):
    return {
        "$type": "UAssetAPI.PropertyTypes.Objects.FSoftObjectPath, UAssetAPI",
        "AssetPath": {
            "$type": "UAssetAPI.PropertyTypes.Objects.FTopLevelAssetPath, UAssetAPI",
            "PackageName": get_transmission_package_path(asset_name),
            "AssetName": asset_name,
        },
        "SubPathString": None,
    }

def get_enum_p(name, enum_type, value):
   return {
              "$type": "UAssetAPI.PropertyTypes.Objects.EnumPropertyData, UAssetAPI",
              "EnumType": enum_type,
              "InnerType": "ByteProperty",
              "Name": name,
              "ArrayIndex": 0,
              "IsZero": False,
              "PropertyTagFlags": "None",
              "PropertyTagExtensions": "NoExtension",
              "Value": value
            }


# Two separate enums, and vanilla sets both where it matters:
#   ClutchType (EMTTransmissionClutchType): MultiPlateClutch | TorqueConvertorV2
#   Type       (EMTTransmissionType):       CVT | EatonFuller13 | EatonFuller18
# Type is what gives a box its shift model -- the range + splitter handling on
# the Eaton twin-countershaft gearboxes. Leave it off and an 18 speed is just
# 18 sequential gears. Set it via "type" on the entry in tras_s.json.
def get_type_properties(clutch_type, shift_type):
   props = []
   if shift_type:
      props.append(get_enum_p('Type', 'EMTTransmissionType', shift_type))
   if clutch_type:
      props.append(get_enum_p('ClutchType', 'EMTTransmissionClutchType', clutch_type))
   return props

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

def run_uassetgui(json_path, output_path, game_name=MAPPINGS):
    # UAssetGUI is a WinForms app: it exits 0 whether or not it wrote anything,
    # so the only reliable success check is the output file existing.
    remove_file_if_exists(output_path)
    try:
        subprocess.run([UASSETGUI, "fromjson", json_path, output_path, game_name], check=True)
    except FileNotFoundError:
        raise SystemExit(f"{UASSETGUI} not found. Check the path.")
    return os.path.exists(output_path)

def get_transmission_package_path(asset_name):
    return TRANSMISSION_DIR + asset_name

def load_vanilla_table():
    """Freshly exported vanilla Transmissions table, as JSON."""
    out = 'Transmissions_vanilla.json'
    remove_file_if_exists(out)
    subprocess.run([UASSETGUI, "tojson", VANILLA_TABLE, out, "VER_UE5_4", MAPPINGS],
                   check=True)
    if not os.path.exists(out):
        raise SystemExit(f"could not read {VANILLA_TABLE} with mappings {MAPPINGS}")
    with open(out, 'r') as f:
        data = json.loads(f.read())
    remove_file_if_exists(out)
    if data['Exports'][0]['$type'].startswith('UAssetAPI.ExportTypes.RawExport'):
        raise SystemExit(f"{VANILLA_TABLE} did not parse as a DataTable -- wrong usmap")
    return data


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


# The gear list runs shallowest reverse first down to the deepest, then N, then
# the forward gears -- same as vanilla's Eaton boxes. R is the deepest reverse,
# R2 the next, and so on.
#
# This used to name them by the keys in tras_s.json ("1" -> R, "2" -> R2), which
# silently produced a wrong box whenever an entry listed its reverses the other
# way round: Allison 4700 RDS had "1": 4.8, "2": 17.12, so R was the shallow
# ratio and R2 the deep one, in the wrong order. Deriving both from the ratios
# means the key numbering no longer has to be right.
def reverse_gears(r_ratios):
    deepest_first = sorted((abs(float(r)) for r in r_ratios.values()), reverse=True)
    return [(-ratio, 100, r_name_keys[str(depth)])
            for depth, ratio in reversed(list(enumerate(deepest_first, start=1)))]


assert reverse_gears({"1": 4.8, "2": 17.12}) == [(-4.8, 100, "R2"), (-17.12, 100, "R")]
assert reverse_gears({"1": 17.12, "2": 4.8}) == [(-4.8, 100, "R2"), (-17.12, 100, "R")]
assert reverse_gears({"1": 4.82, "2": 2.41}) == [(-2.41, 100, "R2"), (-4.82, 100, "R")]
assert reverse_gears({"1": 2.857}) == [(-2.857, 100, "R")]
assert [g[2] for g in reverse_gears({"1": 15.05, "2": 12.85, "3": 4.02, "4": 3.43})] == \
    ["R4", "R3", "R2", "R"]

transmission_asset = load_vanilla_table()

NameMap = transmission_asset['NameMap']
parts = transmission_asset['Exports'][0]['Table']['Data']
vanilla_rows = {row['Name'] for row in parts}
new_names = []


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

      ratios.extend(reverse_gears(transmission.get('r_ratios', {})))
      ratios.append((0, 100, 'N'))

      for gear_index in transmission.get('f_ratios'):
          gear_ratio = transmission.get('f_ratios')[gear_index]
          ratios.append((gear_ratio,100,gear_index))

    # Determine default gear index
    for index in range(0,len(ratios)):
       if 'N' in ratios[index]:
          def_gear = index

    new_transmission_json = load_new_transmission(trans_key, transmission_name)
    transmission_values = []
    
    if type_t == 'CVT':
        transmission_values.extend(get_type_properties(None, 'CVT'))
    else:
        transmission_values.extend(get_type_properties(type_t, transmission.get('type')))
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

        if trans_key in vanilla_rows:
            print(f'skipping {trans_key}: vanilla already ships a row with that key')
            continue

        new_row = load_new_transmission_part(trans_key, transmission_name, weight, price,
                                             lvl_req, None, description)
        parts.append(new_row)
        # Every FName the row touches has to be in the map or UAssetGUI writes
        # nothing at all. Only the base goes in: "Foo_12" is stored as "Foo" + 12.
        new_names += [fname_base(n) for n in (trans_key, *fnames_in(new_row))]

    else:
        print(f'issue with {trans_key}')

# New names belong in the block the header counts as referenced by export data,
# which vanilla keeps at the front of the map.
boundary = transmission_asset['NamesReferencedFromExportDataCount']
fresh = [n for n in dict.fromkeys(new_names) if n not in set(NameMap)]
transmission_asset['NameMap'] = NameMap[:boundary] + fresh + NameMap[boundary:]
transmission_asset['NamesReferencedFromExportDataCount'] = boundary + len(fresh)
transmission_asset['Exports'][0]['Table']['Data'] = parts

with open('Transmissions.json', 'w+') as f:
    f.write(json.dumps(transmission_asset, indent=4))
    # f.write(json.dumps(transmission_asset))