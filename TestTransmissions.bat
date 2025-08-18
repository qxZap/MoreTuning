@echo off

echo Running transmissions.bat...
call transmissions.bat

echo.
echo Running MoreTuning.bat...
call MoreTuning.bat

echo.
echo All scripts finished!

echo Launching Steam game...
start steam://run/1369670
