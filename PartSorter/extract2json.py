import json
import copy

IN_FILE = 'input.json'
OUT_FILE = 'output.json'

data = None
extract_data = None
with open(IN_FILE, 'r') as f:
    data = json.loads(f.read())

with open('extract.json', 'r') as f:
    extract_data = json.loads(f.read())

if data:
    part_names = data.get('NameMap')
    previous_parts = data.get('Exports')[0].get('Table').get('Data')

    parts = data.get('Exports')[0].get('Table').get('Data')

    final_parts = []

    for extract_data_metadata in extract_data:
        for part in parts:
            part_name = part.get("Name")
            part_list_name = part["Value"][0].get("CultureInvariantString")

            if part_name == extract_data_metadata and extract_data[extract_data_metadata] == part_list_name:
                final_parts.append(part)


    with open(OUT_FILE, 'w+') as f:
        data['Exports'][0]['Table']['Data'] = final_parts
            
        f.write(json.dumps(data, indent=4))