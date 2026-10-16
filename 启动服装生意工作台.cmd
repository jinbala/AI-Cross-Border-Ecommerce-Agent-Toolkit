@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "桌面版\服装生意工作台-1.3.exe" (
  start "" "桌面版\服装生意工作台-1.3.exe"
) else if exist "桌面版\服装生意工作台-1.2.exe" (
  start "" "桌面版\服装生意工作台-1.2.exe"
) else if exist "桌面版\服装生意工作台-1.1.exe" (
  start "" "桌面版\服装生意工作台-1.1.exe"
) else if exist "桌面版\服装生意工作台.exe" (
  start "" "桌面版\服装生意工作台.exe"
) else (
  echo 未找到桌面程序，请先完成打包。
  pause
)
