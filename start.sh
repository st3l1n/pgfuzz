#! /bin/bash

activate () {
  . FUZZVenv/bin/activate
}

if [ -d "FUZZVenv" ] 
then
    echo "Venv exists. Go ahead..."
    activate
    python main.py
else
    echo "Creating venv for tests..."
    python3 -m venv FUZZVenv
    activate
    pip install -r requirements.txt
    python main.py
    deactivate
fi
