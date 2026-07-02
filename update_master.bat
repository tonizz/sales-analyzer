@echo off
title Update Master Data — Stock Opname
cd /d "%~dp0"
echo ============================================
echo  UPDATE MASTER DATA STOCK OPNAME
echo ============================================
echo.

echo [1/3] Generate barcode + nama maps...
python gen_maps.py
if %errorlevel% neq 0 ( echo ERROR: gen_maps.py gagal! & pause & exit /b 1 )

echo.
echo [2/3] Generate lokasi map...
python gen_lokasi_map.py
if %errorlevel% neq 0 ( echo ERROR: gen_lokasi_map.py gagal! & pause & exit /b 1 )

echo.
echo [3/3] Commit ke GitHub...
git add .
git commit -m "update master data %date% %time%"
git push
if %errorlevel% equ 0 (
  echo.
  echo ============================================
  echo  SELESAI! Data master sudah update.
  echo  https://tonizz.github.io/sales-analyzer
  echo ============================================
) else (
  echo.
  echo ============================================
  echo  GAGAL push ke GitHub! Lihat pesan error di atas.
  echo ============================================
)
pause
