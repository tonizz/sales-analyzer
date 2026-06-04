@echo off
REM ============================================================
REM Build script untuk BundleAnalyzer.exe
REM Usage:  build.bat
REM Output: dist\BundleAnalyzer.exe
REM ============================================================

echo.
echo === Build BundleAnalyzer.exe ===
echo.

REM Bersihkan build lama
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist BundleAnalyzer.spec del BundleAnalyzer.spec

REM Install dependencies kalau belum
python -m pip install --quiet pandas openpyxl matplotlib pyinstaller

REM Build .exe (windowed, single file, embed PANDUAN.md)
python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "BundleAnalyzer" ^
    --add-data "PANDUAN.md;." ^
    --clean ^
    --noconfirm ^
    bundle_analyzer.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo *** BUILD GAGAL ***
    exit /b %ERRORLEVEL%
)

echo.
echo === BUILD SUKSES ===
echo Output: dist\BundleAnalyzer.exe
echo Ukuran:
for %%A in (dist\BundleAnalyzer.exe) do echo    %%~zA bytes (%%~zA / 1048576 MB)
echo.
echo Cara distribusi: copy file dist\BundleAnalyzer.exe ke komputer lain.
echo.
pause
