Write-Host "========================================="
Write-Host "ODT Fascinatin - Startup Script"
Write-Host "========================================="
Write-Host ""

Write-Host ""
Write-Host "[2/3] Starting Multithreaded Engine..."
Start-Process python -ArgumentList "engine_runner.py" -WindowStyle Normal

Write-Host ""
Write-Host "[3/3] Starting Streamlit Dashboard..."
streamlit run main.py --server.address localhost --server.port 4513
