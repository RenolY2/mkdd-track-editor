@echo off
"%~dp0SuperBMD.exe" %1 --bdl
IF %ERRORLEVEL% NEQ 0 pause