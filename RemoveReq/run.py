import json
import copy

#130/kg real => 650c /kg real
# Weight /2 , then apply 650c/kg 

IN_FILE = 'input.json'
OUT_FILE = 'output.json'

data = None
with open(IN_FILE, 'r') as f:
    data = json.loads(f.read())


def price_and_weight(weight):
    weight = int(weight)
    return round(weight/2*650),round(weight/2,1)


def get_vehicle_tag_query():
    return [
                  {
                    "$type": "UAssetAPI.PropertyTypes.Objects.IntPropertyData, UAssetAPI",
                    "Name": "TokenStreamVersion",
                    "ArrayIndex": 0,
                    "IsZero": True,
                    "PropertyTagFlags": "None",
                    "PropertyTagExtensions": "NoExtension",
                    "Value": 0
                  },
                  {
                    "$type": "UAssetAPI.PropertyTypes.Objects.ArrayPropertyData, UAssetAPI",
                    "ArrayType": "StructProperty",
                    "DummyStruct": None,
                    "Name": "TagDictionary",
                    "ArrayIndex": 0,
                    "IsZero": False,
                    "PropertyTagFlags": "None",
                    "PropertyTagExtensions": "NoExtension",
                    "Value": []
                  },
                  {
                    "$type": "UAssetAPI.PropertyTypes.Objects.ArrayPropertyData, UAssetAPI",
                    "ArrayType": "ByteProperty",
                    "DummyStruct": None,
                    "Name": "QueryTokenStream",
                    "ArrayIndex": 0,
                    "IsZero": False,
                    "PropertyTagFlags": "None",
                    "PropertyTagExtensions": "NoExtension",
                    "Value": []
                  },
                  {
                    "$type": "UAssetAPI.PropertyTypes.Objects.StrPropertyData, UAssetAPI",
                    "Name": "UserDescription",
                    "ArrayIndex": 0,
                    "IsZero": False,
                    "PropertyTagFlags": "None",
                    "PropertyTagExtensions": "NoExtension",
                    "Value": None
                  },
                  {
                    "$type": "UAssetAPI.PropertyTypes.Objects.StrPropertyData, UAssetAPI",
                    "Name": "AutoDescription",
                    "ArrayIndex": 0,
                    "IsZero": False,
                    "PropertyTagFlags": "None",
                    "PropertyTagExtensions": "NoExtension",
                    "Value": None
                  }
                ]

def namerow(part_name):
    return {
                                "$type": "UAssetAPI.PropertyTypes.Objects.TextPropertyData, UAssetAPI",
                                "Flags": "CultureInvariant",
                                "HistoryType": "None",
                                "Namespace": None,
                                "CultureInvariantString": part_name,
                                "SourceFmt": None,
                                "Arguments": None,
                                "ArgumentsData": None,
                                "TransformType": "ToLower",
                                "SourceValue": None,
                                "FormatOptions": None,
                                "TargetCulture": None,
                                "Name": "Name",
                                "ArrayIndex": 0,
                                "IsZero": False,
                                "PropertyTagFlags": "None",
                                "PropertyTagExtensions": "NoExtension",
                                "Value": None
                            }

if data:
    part_names = data.get('NameMap')
    previous_parts = data.get('Exports')[0].get('Table').get('Data')

    parts = data.get('Exports')[0].get('Table').get('Data')

    new_parts = []
    new_part_exportids = []

    clean_parts = []

    for part in parts:
        part_id = part.get('Name')
        part_name = part.get('Value')[0].get('CultureInvariantString')
        current_part = copy.deepcopy(part)


        price_index = None
        weight_index = None
        type_index = None
        vehicle_keys_index = None
        VehicleRowGameplayTagQuery_index = None
        truck_keys_value = None

        for i in range(0, len(current_part['Value'])):
            current_line_json = current_part['Value'][i]
            if current_line_json.get('Name') == 'Cost':
                price_index = i
            if current_line_json.get('Name') == 'MassKg':
                weight_index = i
            if current_line_json.get('Name') == 'VehicleTypes':
                type_index = i
            if current_line_json.get('Name') == 'VehicleKeys':
                vehicle_keys_index = i
            if current_line_json.get('Name') == 'TruckClasses':
                truck_keys_value = i
            if current_line_json.get('Name') == 'VehicleRowGameplayTagQuery':
                VehicleRowGameplayTagQuery_index = i


        if price_index and weight_index:
            new_price,new_weight = price_and_weight(current_part['Value'][weight_index]['Value'])

            current_part['Value'][type_index]['Value'] = []
            current_part['Value'][vehicle_keys_index]['Value'] = []
            current_part['Value'][truck_keys_value]['Value'] = []
            current_part['Value'][VehicleRowGameplayTagQuery_index]['Value'] = get_vehicle_tag_query()
            new_parts.append(current_part)
        
        part['Value'][type_index]['Value'] = []
        part['Value'][vehicle_keys_index]['Value'] = []
        clean_parts.append(part)
        

    with open(OUT_FILE, 'w+') as f:
        data['Exports'][0]['Table']['Data'] = new_parts
            
        f.write(json.dumps(data, indent=4))
    