import os
import re
import time
import copy
import json
import shutil
import subprocess
from pathlib import Path
from datetime import timedelta

TESTING = False # wanna test just a tailed number of attachments?
TESTING_GAP = 10 # how many?
CREATE_ACTORS = True #create actors? 
CLEAN_ACTORS = True #clean all actors on run?
DELTA_ONLY_ACTORS = True #create only missing actors

MESH_ID_TO_USE = -283

paid_icon_index = None

KNOWN_PART_ICONS = {
  "Bonnet": 0,
  "Fender": 0,
  "FrontBumper": 0,
  "FrontSpoiler": 0,
  "FrontWindowSunVisor": 0,
  "RearBumper": 0,
  "RearSpoiler": 0,
  "RearWindowLouvers": 0,
  "RearWing": 0,
  "Roof": 0,
  "SideSkirt": 0,
  "Trunk": 0,
  "Wheels":0,
  "ControlPanel":0,
  "Utility":0,
  "Winch":0
}

def clean_part_name(ugly_str):
    """
    Cleans strings by replacing separators with spaces and 
    removing leading zeros from numbers.
    Example: Vista_FrontBumper_04 -> Vista Front Bumper 4
    """
    # 1. Replace underscores and hyphens with spaces
    # This also handles 'FrontBumper' if it were 'Front-Bumper'
    cleaned = re.sub(r'[_,-]', ' ', ugly_str)
    
    # 2. Add spaces between CamelCase words (e.g., FrontBumper -> Front Bumper)
    # This looks for a lowercase letter followed by an uppercase letter
    cleaned = re.sub(r'([a-z])([A-Z])', r'\1 \2', cleaned)
    
    # 3. Remove leading zeros from numbers (e.g., 04 -> 4)
    # \b0+ looks for a word boundary followed by one or more zeros
    cleaned = re.sub(r'\b0+(\d+)', r'\1', cleaned)
    
    # 4. Strip extra whitespace and return
    return ' '.join(cleaned.split())

def load_json_from_path(path):
    data = None
    with open(path, 'r') as f:
        data = json.loads(f.read())

    if not data:
        print(f"Error reading from {path} !!")
    
    return data

def get_x_bounding(mesh_data):
    for export in mesh_data["Exports"]:
        for row in export["Data"]:
            if row.get("Name") == "ExtendedBounds":
                for subrow in row["Value"]:
                    if subrow["Name"] == "Origin":
                        for subsubrow in subrow["Value"]:
                            if subsubrow["Name"] == "Origin":
                                return (subsubrow["Value"]["X"],subsubrow["Value"]["Y"],subsubrow["Value"]["Z"])

    return "+0"

def quick_copy(src, dst):
    shutil.copy(src, dst)

def write_json_at_path(json_data, save_path):
    try:
        with open(save_path, "w+", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Failed to write file: {e}")

def copy_and_rename(source_path, destination_path):
    """
    Copies a file from source_path to destination_path.
    destination_path should include the new filename.
    """
    try:
        # Convert strings to Path objects
        src = Path(source_path)
        dest = Path(destination_path)

        # Create the destination folders if they don't exist
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Copy the file (shutil.copy2 preserves metadata)
        shutil.copy2(src, dest)
        
        return True

    except FileNotFoundError:
        print(f"Error: The source file '{source_path}' was not found.")
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False

def run_uassetgui(json_path, output_path, game_name="MotorTown718"):
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

def run_uassetgui_uasset_to_json(uasset_path, json_path, game_name="MotorTown718"):
    try:
        subprocess.run([
            "..\\UAssetGUI.exe",
            "tojson",
            uasset_path,
            json_path,
            'VER_UE5_5',
            game_name
        ], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Command failed with return code {e.returncode}")
        return False
    except FileNotFoundError:
        print("UAssetGUI.exe not found. Check the path.")

def open_uasset_gui_target(json_path):
    try:
        subprocess.run([
            "..\\UAssetGUI.exe",
            json_path,
        ], check=True)
        return True
    except Exception as e:
        pass

def file_exists(filepath):
    return os.path.isfile(filepath)

def remove_file_if_exists(filepath):
    if file_exists(filepath):
        os.remove(filepath)

def convert_and_delete(json_path):
    run_uassetgui(json_path, json_path.replace(".json",".uasset"))
    remove_file_if_exists(json_path)

def convert_to_json(uasset_path):
    run_uassetgui_uasset_to_json(uasset_path, uasset_path.replace('.uasset', '.json'))

def save_at_path_and_convert_clean(json_data, save_path, sike=False):
    write_json_at_path(json_data, save_path)
    if not sike:
        convert_and_delete(save_path)

# EXAMPLE
# {
#       "$type": "UAssetAPI.Import, UAssetAPI",
#       "ObjectName": "Default__OversizeLoad_Sign_7_C",
#       "OuterIndex": -172,
#       "ClassPackage": "/Game/Objects/VehicleAttachment/OversizeLoadSigns/OversizeLoad_Sign_7",
#       "ClassName": "OversizeLoad_Sign_7_C",
#       "PackageName": null,
#       "bImportOptional": false
#     }
def new_package_import(object_name, outer_index, class_package, class_name):
    return {
      "$type": "UAssetAPI.Import, UAssetAPI",
      "ObjectName": object_name,
      "OuterIndex": outer_index,
      "ClassPackage": class_package,
      "ClassName": class_name,
      "PackageName": None,
      "bImportOptional": False
    }

def new_actor_import(actor_name, outer_index):
    return new_package_import(actor_name, outer_index, "/Script/Engine", "BlueprintGeneratedClass")

# For mesh
def new_u_object_package_import(object_name):
    return new_package_import(object_name, 0, "/Script/CoreUObject", "Package")

def new_static_mesh(object_name, outer_index):
    return new_package_import(object_name, outer_index, "/Script/Engine", "StaticMesh")

def new_texture_import(object_name, outer_index):
    return {
      "$type": "UAssetAPI.Import, UAssetAPI",
      "ObjectName": object_name,
      "OuterIndex": outer_index,
      "ClassPackage": "/Script/Engine",
      "ClassName": "Texture2D",
      "PackageName": None,
      "bImportOptional": False
    }

def game_to_mt_path(path):
    return path.replace('/Game/', '/MotorTown/Content/')

IN_FILE = "AeroParts.json"

data = None
with open(IN_FILE, "r") as f:
    data = json.loads(f.read())


if not data:
    print(f"No {IN_FILE} found in the current folder! ")
    exit()


NEW_TATTACHMENT_TEMPLATE_PATH = "NEW_ATTACHMENT_PART.json"
new_attachment_template = None
with open(NEW_TATTACHMENT_TEMPLATE_PATH, "r") as f:
    new_attachment_template = json.loads(f.read())

if not new_attachment_template:
    print(f"No {NEW_TATTACHMENT_TEMPLATE_PATH} found in the current folder! It's required to create new attachments!")
    exit()

def make_new_attachment(attachment_id, attachment_name, cost, mass, actor_index, mesh_index, icon_index, part_type, is_premium):
    # TODO: attachment_name << nice format required 
    new_attachment = copy.deepcopy(new_attachment_template)
    new_attachment["Name"] = attachment_id
    
    for row in new_attachment["Value"]:
        if row["Name"] == 'ItemName':
            row["Value"] = attachment_name

        if row["Name"] == "ItemNameTexts":
            row["Value"] = [
                  {
                    "$type": "UAssetAPI.PropertyTypes.Objects.ArrayPropertyData, UAssetAPI",
                    "ArrayType": "TextProperty",
                    "Name": "Texts",
                    "ArrayIndex": 0,
                    "IsZero": False,
                    "PropertyTagFlags": "None",
                    "PropertyTypeName": None,
                    "PropertyTagExtensions": "NoExtension",
                    "Value": [
                      {
                        "$type": "UAssetAPI.PropertyTypes.Objects.TextPropertyData, UAssetAPI",
                        "Flags": 0,
                        "HistoryType": "None",
                        "Namespace": None,
                        "CultureInvariantString": clean_part_name(part_type) + ' ' + clean_part_name(attachment_name).replace(f' {part_type} ', ' ').replace( f' {clean_part_name(part_type)} ',' '),
                        "SourceFmt": None,
                        "Arguments": None,
                        "ArgumentsData": None,
                        "TransformType": "ToLower",
                        "SourceValue": None,
                        "FormatOptions": None,
                        "TargetCulture": None,
                        "Name": "0",
                        "ArrayIndex": 0,
                        "IsZero": False,
                        "PropertyTagFlags": "None",
                        "PropertyTypeName": None,
                        "PropertyTagExtensions": "NoExtension",
                        "Value": None
                      }
                    ]
                  }
                ]
            
        if row["Name"] == "bNotForSale":
            if is_premium:
                row["Value"] = True
        
        if row["Name"] == "Cost":
            row["Value"] = cost
        if row["Name"] == "MassKg":
            row["Value"] = mass if mass else 0
        if row["Name"] == "MaxStack":
            row["Value"] = 9
        if row["Name"] == "AttachmentPartActorClass":
            row["Value"] = actor_index
        if row["Name"] == "StaticMesh":
            row["Value"] = MESH_ID_TO_USE
        
        if row["Name"] == "IconTexture":
            if is_premium and paid_icon_index:
                row["Value"] = paid_icon_index
            else:
                if part_type in KNOWN_PART_ICONS:
                    if KNOWN_PART_ICONS[part_type]!=0:
                        row["Value"] = KNOWN_PART_ICONS[part_type]
                    else:
                        row["Value"] = icon_index
                else:
                    row["Value"] = icon_index

    return new_attachment


NEW_ACTOR_PATH = "ACTOR_TEMPLATE.json"
new_actor_template = None
with open(NEW_ACTOR_PATH, "r") as f:
    new_actor_template = f.read()

if not new_actor_template:
    print(f"No {NEW_ACTOR_PATH} found in the current folder! It's required to create new attachments!")
    exit()

# def make_new_actor(path_base, actor_name, mesh_name, mesh_path):
    
#     new_actor = copy.deepcopy(new_actor_template)
#     new_actor = new_actor.replace("/Game/Objects/VehicleAttachment/OversizeLoadSigns",path_base)
#     new_actor = new_actor.replace("OversizeLoad_Sign_7_C", actor_name+"_C")
#     new_actor = new_actor.replace("/Game/Objects/VehicleAttachment/OversizeLoadSigns/Sign_7", mesh_path+"/"+mesh_name)
#     new_actor = new_actor.replace("Sign_7", mesh_name)
#     # new_actor = new_actor.replace("Default__MagisWing_C", "Default__"+actor_name+"_C")
#     # new_actor = new_actor.replace("MagisWing_C", actor_name+"_C")
#     # new_actor = new_actor.replace("MagisWing_GEN_VARIABLE", actor_name+"_GEN_VARIABLE")
#     # new_actor = new_actor.replace("MagisWing", actor_name)
#     # new_actor = new_actor.replace("/Game/Objects/VehicleAttachment/MoreAttachmentsZS/Blueprints/RearWing/TypeA", mesh_path+"/"+mesh_name)
#     # new_actor = new_actor.replace("/Game/Cars/Parts/RearWing/Magis", mesh_path)
#     # new_actor = new_actor.replace("Magis", mesh_name)

#     data = json.loads(new_actor)
#     data["FolderName"] = path_base+"/"+actor_name
#     for new_name in [mesh_path+"/"+mesh_name, mesh_name]:
#         if new_name not in data["NameMap"]:
#             data["NameMap"].append(new_name)
    
#     return data

def make_new_actor(path_base, actor_name, mesh_name, mesh_path, mesh_bounding):
    
    new_actor = copy.deepcopy(new_actor_template)

    # new_actor = new_actor.replace("/Game/Objects/VehicleAttachment/OversizeLoadSigns",path_base)
    # new_actor = new_actor.replace("OversizeLoad_Sign_7_C", actor_name+"_C")
    # new_actor = new_actor.replace("/Game/Objects/VehicleAttachment/OversizeLoadSigns/Sign_7", mesh_path)
    # new_actor = new_actor.replace("Sign_7", mesh_name)

    new_actor = new_actor.replace("Neutz_SSCustomL_C", actor_name+"_C")
    new_actor = new_actor.replace("/Game/Objects/VehicleAttachment/MajasDetailWorks/Meshes/SideskirtCustomVeryLong", mesh_path)
    new_actor = new_actor.replace("SideskirtCustomVeryLong", mesh_name)

    x = 0.0
    y = 0.0
    z = 0.0

    try:
        x = float(mesh_bounding[0])
    except Exception:
        pass

    try:
        y = float(mesh_bounding[1])
    except Exception:
        pass

    try:
        z = float(mesh_bounding[2])
    except Exception:
        pass

    new_actor = new_actor.replace("-0.96961", str(x))
    new_actor = new_actor.replace("-0.96962", str(y))
    new_actor = new_actor.replace("-0.96963", str(z))


    data = json.loads(new_actor)
    data["FolderName"] = path_base+"/"+actor_name
    data["NameMap"].append(mesh_path)
    data["NameMap"].append(mesh_name)

    return data

VENDOR_FILE_PATH = "Vendor_Garage.json"
vendor_data = None
with open(VENDOR_FILE_PATH, "r") as f:
    vendor_data = json.loads(f.read())

if not vendor_data:
    print(f"No {VENDOR_FILE_PATH} found in the current folder! It's required to create new attachments!")
    exit()



# Logic Start

# Clean up previously generated files
output_content_dir = Path("../qxZap_MoreAttachments_P/MotorTown/Content/Objects/MoreAttachments")
if output_content_dir.exists() and CLEAN_ACTORS:
    shutil.rmtree(output_content_dir)
    print(f"Cleaned up {output_content_dir}")
output_content_dir.mkdir(parents=True, exist_ok=True)

aero_attachments = []

part_names = data.get("NameMap")
previous_parts = data.get("Exports")[0].get("Table").get("Data")

imports = data.get("Imports")

parts = data.get("Exports")[0].get("Table").get("Data")

for part in parts:
    part_id = part.get("Name")
    part_name = part.get("Value")[0].get("CultureInvariantString")

    mesh_index_for_part = None
    MassKg = None
    Cost = None
    PartType = None

    current_part = copy.deepcopy(part)

    for i in range(0, len(current_part["Value"])):
        current_line_json = current_part["Value"][i]

        field_name = current_line_json.get("Name")
        field_value = current_line_json.get("Value")

        if field_name == "Aero":
            for aero_row in field_value:
                if aero_row.get("Name") == "Mesh":
                    mesh_index_for_part = aero_row.get("Value")

        if field_name == "MassKg":
            MassKg = field_value
        if field_name == "PartType":
            PartType = field_value

        if field_name == "Cost":
            Cost = field_value

    part_import = imports[(-1) * mesh_index_for_part - 1]
    ObjectName = part_import.get("ObjectName")
    OuterIndex = part_import.get("OuterIndex")

    package_import = imports[(-1) * OuterIndex - 1]

    PackageObjectName = package_import.get("ObjectName")

    aero_attachments.append(
        {
            "part_id": part_id,
            "mesh_path": PackageObjectName,
            "mesh_id": ObjectName,
            "price": Cost,
            "mass": MassKg,
            "part_type": PartType if PartType else ""
        }
    )

aero_attachments.sort(key=lambda x: x["part_type"])

unique_types = sorted(list(set(item["part_type"] for item in aero_attachments)))

# print("--- Unique Part Types ---")
# for p_type in unique_types:
#     print(f"- {p_type if p_type else '[Empty/None]'}")

# print(aero_attachments)
# this is where the processing of the new attachment is done

ITEM_ATTACHMENTS_FILE = "Items_AttachmentPart.json"
OUTPUT_FILE = "NEW_Items_AttachmentPart.json"

data = None
with open(ITEM_ATTACHMENTS_FILE, "r") as f:
    data = json.loads(f.read())


if not data:
    print(f"No {ITEM_ATTACHMENTS_FILE} found in the current folder! \nThis is required for generation of attachments!")
    exit()


part_names = data.get("NameMap")
previous_parts = data.get("Exports")[0].get("Table").get("Data")

imports = data.get("Imports")

parts = data.get("Exports")[0].get("Table").get("Data")
for part in parts:
    part_id = part.get("Name", "???")
    part_name = part.get("Value", [{}])[0].get("CultureInvariantString", "unknown")

    # print(f"  {part_id} ({part_name})")

    value_list = part.get("Value", [])

    for field in value_list:
        field_name = field.get("Name")

        if field_name == "AttachmentScaleMin":
            old = field.get("Value")
            field["Value"] = 0.25

        elif field_name == "AttachmentScaleMax":
            old = field.get("Value")
            field["Value"] = 2.75


# Template here
# {
            # "part_id": part_id,
            # "mesh_path": PackageObjectName,
            # "mesh_id": ObjectName,
            # "price": Cost,
            # "mass": MassKg,
            #  "part_type": "???"
#         }

# Add extra attachments by had here.

EXTRA_ATTACHMENTS_FILE = "ExtraAttachments.json"

extra_data = None
with open(EXTRA_ATTACHMENTS_FILE, "r") as f:
    extra_data = json.loads(f.read())


if not extra_data:
    print(f"No {EXTRA_ATTACHMENTS_FILE} found in the current folder! \nThis is required for generation of attachments!")
    exit()

if TESTING:
    aero_attachments = aero_attachments[:TESTING_GAP]
    print(f"[TESTING] Limited to only {TESTING_GAP} attachments")

# Extras but no specifics really!

subparts = ["Wheels", "ControlPanel","Utility", "Winch"]
for subpart in subparts:
    fresh_new_parts_ids = [ file_path for file_path in os.listdir(f'../../Output/Exports/MotorTown/Content/Cars/Parts/{subpart}') if '.' in file_path]
    fresh_new_parts_ids = sorted(list(set([fresh_new_part_id.split('.')[0] for fresh_new_part_id in fresh_new_parts_ids])))

    for fresh_new_part_id in fresh_new_parts_ids:
        aero_attachments.append({
            "part_id": fresh_new_part_id,
            "mesh_path": f"/Game/Cars/Parts/{subpart}/{fresh_new_part_id}",
            "mesh_id": fresh_new_part_id,
            "price": 2000,
            "mass": 50,
            "part_type": subpart
        })

for new_attachment in extra_data:
    aero_attachments.append(new_attachment)


vendor_last_id = int(vendor_data["Exports"][8]["Data"][0]["Value"][-1]["Name"])+1
vendor_premium_last_id = vendor_last_id


# Default IMPORT for texture i guess. 
index = len(data["Imports"])

DEFAULT_IMPORT_PATH = "/Game/UI/Icons/Item/Ornament"
DEFAULT_IMPORT_TEXTURE = "Ornament"

data["Imports"].append(new_texture_import(DEFAULT_IMPORT_TEXTURE,(-1)*index-2 ))
data["Imports"].append(new_u_object_package_import(DEFAULT_IMPORT_PATH))

icon_index = (-1)*index-1

data["Exports"][0]["CreateBeforeSerializationDependencies"].append((-1)*index-2)

data["NameMap"].append(DEFAULT_IMPORT_TEXTURE)
data["NameMap"].append(DEFAULT_IMPORT_PATH)

index = len(data["Imports"])

# Premium content (paid one)
index = len(data["Imports"])

DEFAULT_IMPORT_PATH = "/Game/UI/Icons/GoldStar"
DEFAULT_IMPORT_TEXTURE = "GoldStar"

data["Imports"].append(new_texture_import(DEFAULT_IMPORT_TEXTURE,(-1)*index-2 ))
data["Imports"].append(new_u_object_package_import(DEFAULT_IMPORT_PATH))

paid_icon_index = (-1)*index-1

data["Exports"][0]["CreateBeforeSerializationDependencies"].append((-1)*index-2)

data["NameMap"].append(DEFAULT_IMPORT_TEXTURE)
data["NameMap"].append(DEFAULT_IMPORT_PATH)

index = len(data["Imports"])

for new_icon_key in KNOWN_PART_ICONS.keys():
    import_path = f"/Game/UI/MoreAttachments/{new_icon_key}"

    data["NameMap"].append(new_icon_key)
    data["NameMap"].append(import_path)

    new_icon_index = (-1)*index-2

    KNOWN_PART_ICONS[new_icon_key] = new_icon_index+1

    data["Imports"].append(new_texture_import(new_icon_key, new_icon_index))
    data["Imports"].append(new_u_object_package_import(import_path))

    data["Exports"][0]["CreateBeforeSerializationDependencies"].append(new_icon_index)

    index +=2

attachments_count = len(aero_attachments)
current_index = 1
start_time = time.time()

premium_data = data["Exports"][0]["Table"]["Data"]

vendor_premium_listing = copy.deepcopy(vendor_data["Exports"][8]["Data"][0]["Value"])
vendor_premium_names = copy.deepcopy(vendor_data["NameMap"])

for aero_attachment in aero_attachments:
    # Your real work here
    # time.sleep(0.3)          # ← only for demonstration

    elapsed = time.time() - start_time
    progress = current_index / attachments_count
    percent = int(progress * 100)

    if current_index > 1:  # avoid division by zero at first iteration
        eta_seconds = (elapsed / (current_index - 1)) * (attachments_count - current_index + 1)
        eta_str = str(timedelta(seconds=int(eta_seconds)))
    else:
        eta_str = "--:--:--"

    print(
        f"\t{current_index}/{attachments_count} ~ {percent}%   ETA: {eta_str}",
        end="\r"   # ← overwrite same line (clean terminal look)
    )

    current_index += 1

    part_id = aero_attachment.get("part_id")
    mesh_path = aero_attachment.get("mesh_path")
    mesh_id = aero_attachment.get("mesh_id")
    price = aero_attachment.get("price")
    mass = aero_attachment.get("mass")
    part_type = aero_attachment.get("part_type")
    is_premium = aero_attachment.get("premium", False)

    name_part_id = 'Attachment_'+part_id

    premium_entry = {
        "$type": "UAssetAPI.PropertyTypes.Objects.NamePropertyData, UAssetAPI",
        "Name": str(vendor_premium_last_id),
        "ArrayIndex": 0,
        "IsZero": False,
        "PropertyTagFlags": "None",
        "PropertyTypeName": None,
        "PropertyTagExtensions": "NoExtension",
        "Value": name_part_id
    }

    # Premium list gets EVERYTHING
    vendor_premium_listing.append(premium_entry)
    vendor_premium_names.append(name_part_id)

    vendor_premium_last_id += 1  # ALWAYS increment

    # Default list gets ONLY non-premium
    if not is_premium:
        default_entry = {
            "$type": "UAssetAPI.PropertyTypes.Objects.NamePropertyData, UAssetAPI",
            "Name": str(vendor_last_id),
            "ArrayIndex": 0,
            "IsZero": False,
            "PropertyTagFlags": "None",
            "PropertyTypeName": None,
            "PropertyTagExtensions": "NoExtension",
            "Value": name_part_id
        }

        vendor_data["Exports"][8]["Data"][0]["Value"].append(default_entry)
        vendor_data["NameMap"].append(name_part_id)

        vendor_last_id += 1  # ONLY increment here

    # data["NameMap"].append(name_part_id)
    # data["NameMap"].append('/Game/Objects/MoreAttachments/'+name_part_id)
    # data["NameMap"].append(mesh_id)
    # data["NameMap"].append(mesh_path)

    for new_name in [name_part_id, '/Game/Objects/MoreAttachments/'+name_part_id, mesh_id, mesh_path, name_part_id+"_C"]:
        if new_name not in data["NameMap"]:
            data["NameMap"].append(new_name)

    data["Imports"].append(new_actor_import(name_part_id+"_C", (-1)*index-2))
    actor_index = (-1)*index-1
    index+=2
    data["Imports"].append(new_u_object_package_import('/Game/Objects/MoreAttachments/'+name_part_id))


    # data["Imports"].append(new_static_mesh(mesh_id, (-1)*index-2))
    mesh_index = (-1)*index-1
    # index+=2
    # data["Imports"].append(new_u_object_package_import(mesh_path))


    data["Exports"][0]["Table"]["Data"].append(make_new_attachment(name_part_id, part_id, price, mass, actor_index, mesh_index, icon_index, part_type, is_premium))
    premium_data.append(make_new_attachment(name_part_id, part_id, price, mass, actor_index, mesh_index, icon_index, part_type, False))
    data["Exports"][0]["CreateBeforeSerializationDependencies"].append(actor_index)
    # data["Exports"][0]["CreateBeforeSerializationDependencies"].append(mesh_index)

    # Every new actor requires relative location
    # print("../../Output/Exports"+game_to_mt_path(mesh_path))
    if CREATE_ACTORS:
        new_actor_path_json = f"../qxZap_MoreAttachments_P/MotorTown/Content/Objects/MoreAttachments/{name_part_id}.json"
        if DELTA_ONLY_ACTORS and file_exists(new_actor_path_json.replace('.json', '.uasset')) and file_exists(new_actor_path_json.replace('.json', '.uexp')):
            continue

        uasset_exported_path = "../../Output/Exports"+game_to_mt_path(mesh_path)+'.uasset'
        convert_to_json(uasset_exported_path)
        mesh_data = load_json_from_path(uasset_exported_path.replace('.uasset','.json'))
        mesh_bounding = [(-1)*bounding for bounding in get_x_bounding(mesh_data)]

        new_actor = make_new_actor('/Game/Objects/MoreAttachments', name_part_id, mesh_id, mesh_path, mesh_bounding)
        
        save_at_path_and_convert_clean(new_actor, new_actor_path_json)
        # write_json_at_path(new_actor, f"../qxZap_MoreAttachments_P/MotorTown/Content/Objects/MoreAttachments/{name_part_id}.json")

# Save result

copy_base_bps_from = '../../Output/Exports/MotorTown/Content/Characters'
copy_base_bps_to = '../qxZap_MoreAttachments_P/MotorTown/Content/Characters'

files = ['MotorTownCharacterBP', 'MTAICharacter', 'MTPlayerCharacter']
extensions = ['.uasset','.uexp']

copied = []

for file in files:
    for extension in extensions:
        copy_from = f'{copy_base_bps_from}/{file}{extension}'
        copy_to = f'{copy_base_bps_to}/{file}{extension}'

        # Free mod
        quick_copy(copy_from, copy_to)
        copied.append(copy_to)

        # Paid mod
        new_one = copy_to.replace('qxZap_MoreAttachments_P','qxZap_MoreAttachments_Premium_P')
        quick_copy(copy_from, new_one)
        copied.append(new_one)

# Free mod
save_at_path_and_convert_clean(data, "../qxZap_MoreAttachments_P/MotorTown/Content/DataAsset/Items/Items_AttachmentPart.json")

# Paid mod
premium_mod_data = copy.deepcopy(data)
premium_mod_data["Exports"][0]["Table"]["Data"]=premium_data
save_at_path_and_convert_clean(premium_mod_data, "../qxZap_MoreAttachments_Premium_P/MotorTown/Content/DataAsset/Items/Items_AttachmentPart.json")

# write_json_at_path(data,  "../qxZap_MoreAttachments_P/MotorTown/Content/DataAsset/Items/Items_AttachmentPart.json")

# Free mod
save_at_path_and_convert_clean(vendor_data, "../qxZap_MoreAttachments_P/MotorTown/Content/Characters/NPC/Vendor_Garage.json")

# Paid mode
premium_vendor_data = copy.deepcopy(vendor_data)
premium_vendor_data["NameMap"] = vendor_premium_names
premium_vendor_data["Exports"][8]["Data"][0]["Value"]=vendor_premium_listing

save_at_path_and_convert_clean(premium_vendor_data, "../qxZap_MoreAttachments_Premium_P/MotorTown/Content/Characters/NPC/Vendor_Garage.json")


for copied_file in copied:
    remove_file_if_exists(copied_file)
