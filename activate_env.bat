@echo off
echo Activating QMT Python 3.10 environment...
call conda activate qmt_py310
echo Environment activated! Python version:
python --version
echo.
echo Available commands:
echo   python - Run Python 3.10
echo   jupyter notebook - Start Jupyter Notebook
echo   uvicorn main:app --reload - Start FastAPI server
echo.