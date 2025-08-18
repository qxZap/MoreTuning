import json

# Load the original transmissions JSON
with open('tras.json', 'r') as f:
    transmissions = json.load(f)

# Sort transmissions by 'weight'
sorted_transmissions = dict(sorted(transmissions.items(), key=lambda item: item[1].get('weight', float('inf'))))

# Save sorted transmissions to new file
with open('tras_s.json', 'w') as f:
    json.dump(sorted_transmissions, f, indent=2)

print("Transmissions sorted by weight and saved to tras_s.json")
