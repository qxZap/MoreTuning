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

:: Run UAssetGUI -- D:\MT\UAssetGUI.exe (v1.1.1), NOT the v1.0.4 copy in this
:: folder, and the 0.7.19 mappings. The old pair writes files the game ignores.
del /Q .\Transmissions.uasset 2>nul
"D:\MT\UAssetGUI.exe" fromjson .\Transmissions.json .\Transmissions.uasset MotorTown719
if not exist .\Transmissions.uasset (
    echo Error: UAssetGUI wrote nothing - table not rebuilt.
    exit /b 1
)

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
