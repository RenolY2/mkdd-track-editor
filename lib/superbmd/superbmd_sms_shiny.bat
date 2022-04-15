@echo off
"%~dp0SuperBMD.exe" %1 --mat "%~dp0material_presets/shiny.json"
IF %ERRORLEVEL% NEQ 0 pause