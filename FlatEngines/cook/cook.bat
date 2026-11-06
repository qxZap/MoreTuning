@echo off
rem Recook MoreTuning's synthesised engine sounds. Run from anywhere.
rem   1 render layers (Docker, rust:1)   2 16-bit wavs levelled to vanilla   3 editor import   4 cook
rem   5 copy+verify into the mod   6 EngineSoundData assets   7 decode the shipped waves and check loudness
setlocal
set UE=D:\Program Files\Epic Games\UE_5.5\Engine\Binaries\Win64\UnrealEditor-Cmd.exe
set PROJ=D:\MT\SoundCook\MTEngineSounds\MTEngineSounds.uproject
cd /d %~dp0
python layers.py || exit /b 1
if not exist ref_lufs.json python loudness.py refs || exit /b 1
python prep_wavs.py || exit /b 1
"%UE%" "%PROJ%" -run=pythonscript -script="%~dp0ue_import.py" -unattended -nosplash -nullrhi || exit /b 1
"%UE%" "%PROJ%" -run=Cook -TargetPlatform=Windows -unversioned -unattended -nosplash || exit /b 1
python copy_cooked.py || exit /b 1
python make_data.py || exit /b 1
python loudness.py verify || exit /b 1
