@echo off
"%~dp0SuperBMD.exe" %1 --mat "%~dp0material_presets/toonshading.json"
IF %ERRORLEVEL% NEQ 0 pause