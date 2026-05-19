@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================================
REM InvestNet — one-click build for Windows 10/11 x64
REM Requires (only on this build machine): Python 3.11, Node.js 20+, ~6 GB free
REM Output: bin\InvestNet\ — portable folder; bin\InvestNet-portable.zip — archive
REM ============================================================================

set "ROOT=%~dp0.."
pushd "%ROOT%"

echo.
echo [1/6] Checking prerequisites...
where python >nul 2>&1
if errorlevel 1 (
  echo  ERROR: python not found in PATH. Install Python 3.11 from python.org.
  popd & exit /b 1
)
where node >nul 2>&1
if errorlevel 1 (
  echo  ERROR: node not found in PATH. Install Node.js 20+ from nodejs.org.
  popd & exit /b 1
)
where npm >nul 2>&1
if errorlevel 1 (
  echo  ERROR: npm not found in PATH.
  popd & exit /b 1
)

echo.
echo [2/6] Setting up Python venv and dependencies...
if not exist "backend\.venv\Scripts\python.exe" (
  python -m venv backend\.venv || goto :err
)
call backend\.venv\Scripts\activate.bat
python -m pip install --upgrade pip wheel >nul
pip install -r backend\requirements.txt || goto :err
pip install pyinstaller==6.11.1 || goto :err

echo.
echo [3/6] Building backend.exe with PyInstaller...
if exist "backend-dist" rmdir /s /q backend-dist
pushd backend
pyinstaller --noconfirm --distpath ..\backend-dist --workpath ..\backend-build backend.spec || (popd & goto :err)
popd
if not exist "backend-dist\backend\backend.exe" (
  echo  ERROR: backend.exe was not produced.
  goto :err
)

echo.
echo [4/6] Installing frontend dependencies...
pushd frontend
call npm install || (popd & goto :err)

echo.
echo [5/6] Building renderer + Electron app...
call npm run build || (popd & goto :err)
popd

echo.
echo [6/6] Collecting final portable folder...
if exist "bin\InvestNet" rmdir /s /q bin\InvestNet
mkdir bin\InvestNet 2>nul

REM electron-builder produces `bin\win-unpacked\` with the unpacked app — use it as portable folder.
if exist "bin\win-unpacked" (
  xcopy /e /i /y /q "bin\win-unpacked\*" "bin\InvestNet\" >nul
) else (
  echo  ERROR: bin\win-unpacked not found. Check electron-builder output.
  goto :err
)

REM Create a zip archive of the portable folder.
where powershell >nul 2>&1
if not errorlevel 1 (
  if exist "bin\InvestNet-portable.zip" del /q "bin\InvestNet-portable.zip"
  powershell -NoProfile -Command "Compress-Archive -Path 'bin\InvestNet\*' -DestinationPath 'bin\InvestNet-portable.zip' -Force" || goto :err
)

echo.
echo ===============================================================
echo  BUILD COMPLETE
echo  Portable folder:    bin\InvestNet\InvestNet.exe
echo  Portable archive:   bin\InvestNet-portable.zip
echo  NSIS installer:     bin\InvestNet-1.0.0-setup.exe (if produced)
echo ===============================================================
popd
endlocal
exit /b 0

:err
echo.
echo  BUILD FAILED.
popd
endlocal
exit /b 1
