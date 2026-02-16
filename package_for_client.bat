@echo off
REM ============================================================
REM  Package IB-Grade DCF Engine for Client Delivery
REM  Creates a clean /dist folder with only deliverable files
REM ============================================================
setlocal

set DIST=dist\dcf_engine_v10

echo.
echo ── Cleaning previous build...
if exist dist rmdir /s /q dist

echo ── Creating delivery folder: %DIST%
mkdir "%DIST%"
mkdir "%DIST%\src\dcf_engine\comps"
mkdir "%DIST%\src\dcf_engine\ingestion"
mkdir "%DIST%\src\dcf_engine\output"
mkdir "%DIST%\src\dcf_engine\schedules"
mkdir "%DIST%\src\dcf_engine\statements"
mkdir "%DIST%\src\dcf_engine\valuation"
mkdir "%DIST%\templates"
mkdir "%DIST%\data"
mkdir "%DIST%\api"
mkdir "%DIST%\configs"

echo ── Copying core engine...
xcopy /q "src\dcf_engine\*.py"           "%DIST%\src\dcf_engine\"       >nul
xcopy /q "src\dcf_engine\comps\*.py"     "%DIST%\src\dcf_engine\comps\" >nul
xcopy /q "src\dcf_engine\ingestion\*.py" "%DIST%\src\dcf_engine\ingestion\" >nul
xcopy /q "src\dcf_engine\output\*.py"    "%DIST%\src\dcf_engine\output\"    >nul
xcopy /q "src\dcf_engine\schedules\*.py" "%DIST%\src\dcf_engine\schedules\" >nul
xcopy /q "src\dcf_engine\statements\*.py" "%DIST%\src\dcf_engine\statements\" >nul
xcopy /q "src\dcf_engine\valuation\*.py" "%DIST%\src\dcf_engine\valuation\"  >nul
copy /y "src\__init__.py"                "%DIST%\src\" >nul

echo ── Copying dashboard + templates...
copy /y "dashboard_api.py"               "%DIST%\" >nul
copy /y "templates\dashboard.html"       "%DIST%\templates\" >nul

echo ── Copying sample data + configs...
copy /y "data\*.csv"                     "%DIST%\data\" >nul
copy /y "config.example.json"            "%DIST%\configs\" >nul
copy /y "config.asian_street_ib_grade.json" "%DIST%\configs\" >nul

echo ── Copying deployment files...
copy /y "requirements.txt"               "%DIST%\" >nul
copy /y "run_dashboard.bat"              "%DIST%\" >nul
copy /y "vercel.json"                    "%DIST%\" >nul
copy /y "api\index.py"                   "%DIST%\api\" >nul

echo ── Copying documentation...
copy /y "CLIENT_README.md"               "%DIST%\README.md" >nul

echo.
echo ============================================================
echo  DONE — Delivery package ready at: %DIST%\
echo.
echo  Contents:
echo    src\          Engine source code
echo    templates\    Dashboard UI
echo    data\         Sample financial data
echo    configs\      Preset configurations
echo    api\          Vercel serverless entry
echo    README.md     Client-facing documentation
echo ============================================================
echo.
pause
