@echo off
echo Running tutorial validation...
python validate_tutorials.py %*
echo.
echo Validation complete. Check tutorials_validation_report.txt for results.
pause