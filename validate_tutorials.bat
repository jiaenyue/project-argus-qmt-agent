@echo off
REM 激活Python虚拟环境
call qmt_env\Scripts\activate

REM 运行Python验证脚本
python run_validation.py
