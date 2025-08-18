import json
import copy

IN_FILE = 'input.json'

data = None
with open(IN_FILE, 'r') as f:
    data = json.loads(f.read())

if data:
    part_names = data.get('NameMap')
    previous_parts = data.get('Exports')[0].get('Table').get('Data')

    parts = data.get('Exports')[0].get('Table').get('Data')

    extract = {}

    for part in parts:
        part_name = part.get("Name")
        part_list_name = part["Value"][0].get("CultureInvariantString")

        extract[part_name] = part_list_name
        
    with open('extract.json', 'w+') as f:
        f.write(json.dumps(extract, indent=4))