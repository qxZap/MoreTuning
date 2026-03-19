import os
import copy
import json
import shutil
import subprocess
from pathlib import Path

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

def remove_file_if_exists(filepath):
    if os.path.isfile(filepath):
        os.remove(filepath)

def convert_and_delete(json_path):
    run_uassetgui(json_path, json_path.replace(".json",".uasset"))
    remove_file_if_exists(json_path)

def save_at_path_and_convert_clean(json_data, save_path):
    write_json_at_path(json_data, save_path)
    convert_and_delete(save_path)


# 130/kg real => 650c /kg real
# Weight /2 , then apply 650c/kg

IN_FILE = "AeroParts.json"
# OUT_FILE = 'output.json'

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

def make_new_attachment(attachment_id, attachment_name, cost, mass):
    
    new_attachment = copy.deepcopy(new_attachment_template)
    new_attachment["Name"] = attachment_id
    
    for row in new_attachment["Value"]:
        if row["Name"] == 'ItemName':
            row["Value"] = attachment_name
        if row["Name"] == "Cost":
            row["Value"] = cost
        if row["Name"] == "MassKg":
            row["Value"] = mass if mass else 0
        if row["Name"] == "MaxStack":
            row["Value"] = 9
    
    return new_attachment



NEW_ACTOR_PATH = "ACTOR_TEMPLATE.json"
new_actor_template = None
with open(NEW_ACTOR_PATH, "r") as f:
    new_actor_template = f.read()

if not new_actor_template:
    print(f"No {NEW_ACTOR_PATH} found in the current folder! It's required to create new attachments!")
    exit()

def make_new_actor(path_base, actor_name, mesh_name):
    
    new_actor = copy.deepcopy(new_actor_template)
    new_actor = new_actor.replace("/Game/Objects/VehicleAttachment/OversizeLoadSigns",path_base)
    new_actor = new_actor.replace("OversizeLoad_Sign_7_C", actor_name+"_C")
    new_actor = new_actor.replace("Sign_7", mesh_name)

    data = json.loads(new_actor)
    data["FolderName"] = path_base+"/"+actor_name
    
    return data


# Logic Start


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
        }
    )

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
            field["Value"] = 5.0


# Template here
# {
#             "part_id": part_id,
#             "mesh_path": PackageObjectName,
#             "mesh_id": ObjectName,
#             "price": Cost,
#             "mass": MassKg,
#         }
for aero_attachment in aero_attachments:

    part_id = aero_attachment.get("part_id")
    mesh_path = aero_attachment.get("mesh_path")
    mesh_id = aero_attachment.get("mesh_id")
    price = aero_attachment.get("price")
    mass = aero_attachment.get("mass")

    name_part_id = 'Attachment_'+part_id

    data["Exports"][0]["Table"]["Data"].append(make_new_attachment(name_part_id, part_id, price, mass))

    data["NameMap"].append(name_part_id)


    new_actor = make_new_actor('/Game/Objects/MoreAttachments', name_part_id, mesh_id)
    save_at_path_and_convert_clean(new_actor, f"../MoreAttachments_P/MotorTown/Content/Objects/MoreAttachments/{name_part_id}.json")

    # TODO: CreateBeforeSerializationDependencies, import actor and mesh
    # creation of actors
    # conversion of actors
    # conversion of newparts

# Save result

save_at_path_and_convert_clean(data, "../MoreAttachments_P/MotorTown/Content/DataAsset/Items/Items_AttachmentPart.json")