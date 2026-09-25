@echo off
echo =========================================
echo ODT Fascinatin - Startup Script
echo =========================================

echo.
echo.
echo [2/3] Starting Multithreaded Engine...
start "Engine Runner" python engine_runner.py

echo.
echo [3/3] Starting Streamlit Dashboard...
streamlit run main.py --server.address localhost --server.port 4513
