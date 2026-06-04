@echo off
setlocal EnableDelayedExpansion

REM ============================================================
REM  Bundle Sales Analyzer - Web Edition
REM  Auto-detect Python yang punya streamlit terinstall.
REM  Double-click file ini. Browser akan terbuka otomatis.
REM ============================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo  Bundle Sales Analyzer - Web Edition
echo  Lokasi: %cd%
echo ============================================================
echo.

REM Cari Python yang punya streamlit terinstall
set "PYTHON_EXE="
set "PYTHON_SOURCE="

REM Opsi 1: python di PATH (skip Microsoft Store stub)
for /f "delims=" %%P in ('where python 2^>nul') do (
    REM Skip Microsoft Store stub di WindowsApps
    echo %%P | findstr /i "WindowsApps" >nul
    if errorlevel 1 (
        REM Test apakah python ini bisa import streamlit
        "%%P" -c "import streamlit" >nul 2>&1
        if not errorlevel 1 (
            set "PYTHON_EXE=%%P"
            set "PYTHON_SOURCE=ditemukan di PATH (punya streamlit)"
            goto :python_found
        )
    )
)

REM Opsi 2: cari di AppData\Local\Python
for /d %%D in ("%LOCALAPPDATA%\Python\pythoncore-*") do (
    if exist "%%D\python.exe" (
        "%%D\python.exe" -c "import streamlit" >nul 2>&1
        if not errorlevel 1 (
            set "PYTHON_EXE=%%D\python.exe"
            set "PYTHON_SOURCE=ditemukan di AppData\Local\Python (punya streamlit)"
            goto :python_found
        )
    )
)

REM Opsi 3: cari di Program Files
for /d %%D in ("%ProgramFiles%\Python*") do (
    if exist "%%D\python.exe" (
        "%%D\python.exe" -c "import streamlit" >nul 2>&1
        if not errorlevel 1 (
            set "PYTHON_EXE=%%D\python.exe"
            set "PYTHON_SOURCE=ditemukan di Program Files (punya streamlit)"
            goto :python_found
        )
    )
)

echo [ERROR] Tidak ada Python dengan streamlit terinstall ditemukan.
echo.
echo Coba install manual:
echo   python -m pip install streamlit plotly openpyxl
echo.
echo Atau pakai versi desktop: dist\BundleAnalyzer.exe
echo.
pause
exit /b 1

:python_found
echo [INFO] Python: !PYTHON_EXE!
echo       !PYTHON_SOURCE!
echo.

echo [1/3] Verifikasi dependencies...
"!PYTHON_EXE!" -c "import streamlit, plotly, pandas, openpyxl" 2>nul
if errorlevel 1 (
    echo [INFO] Install dependencies...
    "!PYTHON_EXE!" -m pip install --disable-pip-version-check streamlit plotly openpyxl
    if errorlevel 1 (
        echo [ERROR] Gagal install dependencies.
        pause
        exit /b 1
    )
)
echo       OK.
echo.

REM Disable streamlit telemetry & email prompt (mencegah hang di non-interactive)
set "STREAMLIT_DIR=%USERPROFILE%\.streamlit"
if not exist "!STREAMLIT_DIR!" mkdir "!STREAMLIT_DIR!" >nul 2>&1
(
    echo [browser]
    echo gatherUsageStats = false
    echo.
    echo [server]
    echo headless = true
) > "!STREAMLIT_DIR!\config.toml"
echo       Config: !STREAMLIT_DIR!\config.toml (telemetry off, headless on)
echo.

REM Cari port yang free (8501-8510)
set "STREAMLIT_PORT=8501"
for %%P in (8501 8502 8503 8504 8505 8506 8507 8508 8509 8510) do (
    netstat -an | findstr "LISTENING" | findstr ":%%P " >nul 2>&1
    if errorlevel 1 (
        set "STREAMLIT_PORT=%%P"
        goto :port_found
    )
)
echo [WARN] Port 8501-8510 semua dipakai. Streamlit akan auto-cari.

:port_found
echo [2/3] Streamlit akan jalan di port: !STREAMLIT_PORT!
echo [3/3] Menjalankan server...
echo.
echo       Buka di browser: http://localhost:!STREAMLIT_PORT!
echo       Tekan Ctrl+C untuk stop.
echo.

REM Buka browser 3 detik kemudian
start "" /b cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:!STREAMLIT_PORT!"

REM Jalankan streamlit (echo. | untuk skip email prompt onboarding)
echo.|"!PYTHON_EXE!" -m streamlit run bundle_analyzer_web.py --server.headless=false --server.port=!STREAMLIT_PORT! --browser.gatherUsageStats=false

echo.
echo ============================================================
echo  Server berhenti.
echo ============================================================
pause
