@echo off
REM Apply / update SQL Server database schema for FSS Accounts
cd /d "%~dp0"
set PYTHONUTF8=1
python -c "import db; print(db.migrate()); ok,msg=db.test_connection(); print(msg if ok else 'ERROR: '+msg)"
pause
