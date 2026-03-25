@echo off
setlocal enabledelayedexpansion
set "zipfile=release.zip"

if exist "%zipfile%" del "%zipfile%"

powershell -ExecutionPolicy Bypass -File build.ps1 -ZipFile "%zipfile%"
echo Zipped to %zipfile%