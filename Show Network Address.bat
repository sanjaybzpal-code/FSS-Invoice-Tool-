@echo off
REM Prints the address teammates should open in their browser.
setlocal enabledelayedexpansion
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
    set ip=%%a
    set ip=!ip: =!
    echo Team URL:  http://!ip!:5000
)
echo.
echo Share one of the addresses above with your teammates.
echo (They must be on the same office network / Wi-Fi.)
echo.
pause
