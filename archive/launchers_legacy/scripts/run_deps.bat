@echo off
echo Installing CUDA Torch...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
echo Installing requirements...
pip install -r requirements.txt
echo Done - run python Start.py next.
pause