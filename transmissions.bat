@echo off
setlocal

:: Go into TransmissionGenerator
cd /d TransmissionGenerator

:: Run Python script
python run.py

:: Move Transmissions.json up one level
move /Y Transmissions.json ..\Transmissions.json

:: Go back to root
cd ..

:: Run UAssetGUI
UAssetGUI.exe fromjson .\Transmissions.json .\Transmissions.uasset MotorTown

:: Move generated files into VehicleParts
move /Y Transmissions.uasset .\qxZap_MoreTuning_P\MotorTown\Content\DataAsset\VehicleParts\Transmissions.uasset
move /Y Transmissions.uexp .\qxZap_MoreTuning_P\MotorTown\Content\DataAsset\VehicleParts\Transmissions.uexp

:: Set source and destination
set "src=TransmissionGenerator\new_trans"
set "dst=qxZap_MoreTuning_P\MotorTown\Content\Cars\Parts\Transmission"

:: Ensure destination exists
if not exist "%dst%" (
    echo Creating destination folder...
    mkdir "%dst%"
)

:: Move files
echo Moving files from "%src%" to "%dst%" ...
move /Y "%src%\*" "%dst%\"
del /Q .\Transmissions.json

echo Done!
