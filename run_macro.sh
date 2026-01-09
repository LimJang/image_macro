#!/bin/bash

# Navigate to the project directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Path to your conda environment's python executable
PYTHON_EXEC="/Users/ogf2002/miniconda3/envs/macro_env/bin/python"

# Run the main GUI script
"$PYTHON_EXEC" main_gui.py
