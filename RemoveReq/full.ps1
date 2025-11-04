mv .\AeroParts.json input.json
python run.py
mv .\output.json AeroParts.json
rm input.json

mv .\Headlights.json input.json
python run.py
mv .\output.json Headlights.json
rm input.json

mv .\Wheels.json input.json
python run.py
mv .\output.json Wheels.json
rm input.json