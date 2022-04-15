@echo off
"%~dp0SuperBMD.exe" %1 --mat "%~dp0material_presets/simpleshading.json" --rotate
IF %ERRORLEVEL% NEQ 0 pause