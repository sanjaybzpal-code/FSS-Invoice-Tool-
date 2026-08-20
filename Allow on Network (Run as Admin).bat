@echo off
REM Opens Windows Firewall so teammates on the same network can reach the
REM FSS Invoice Tool. Right-click this file and choose "Run as administrator".

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo This must be run as Administrator.
    echo Right-click the file and choose "Run as administrator".
    echo.
    pause
    exit /b 1
)

set RULENAME=FSS Invoice Tool (port 5000)
netsh advfirewall firewall delete rule name="%RULENAME%" >nul 2>&1
netsh advfirewall firewall add rule name="%RULENAME%" dir=in action=allow protocol=TCP localport=5000 profile=private,domain

echo.
echo Firewall rule added. Teammates on the same network can now open the tool.
echo Find your address by running "Show Network Address.bat".
echo.
pause
