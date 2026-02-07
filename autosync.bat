@echo off
:loop
cls
echo ---------------------------------------------------
echo  AUTO-SYNC ACTIVE: Watching for changes...
echo ---------------------------------------------------
echo.

:: 1. Add all changes
git add .

:: 2. Commit changes (suppress error if nothing changed)
git commit -m "Auto-update: %date% %time%" >nul 2>&1

:: 3. Push to GitHub (only if commit succeeded)
if %errorlevel% equ 0 (
    echo Changes detected! Uploading to GitHub...
    git push origin main
    echo Upload complete.
) else (
    echo No new changes found.
)

:: 4. Wait 10 seconds before checking again
timeout /t 10 >nul
goto loop