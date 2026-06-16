#!/bin/bash

# Change to the project directory
cd /opt/data/workspace/barrel-proof || { echo "Failed to change directory to /opt/data/workspace/barrel-proof"; exit 1; }

# Activate the virtual environment
source ./.venv/bin/activate || { echo "Failed to activate virtual environment"; exit 1; }

# Define the path to the virtual environment's Python interpreter
PYTHON_EXEC="./.venv/bin/python"

# Define the list of scripts to run in order
SCRIPTS=(
    "update_dope_sheet.py"
    "scripts/update_dope_player_matchups.py"
    "scripts/check_dope_player_matchups_ready.py"
    "scripts/update_dope_pitcher_matchups.py"
    "scripts/check_dope_pitcher_matchups_ready.py"
    "scripts/update_pitch_type_intelligence.py"
    "scripts/check_pitch_type_intelligence_ready.py"
    "scripts/update_dope_game_intelligence.py"
    "scripts/check_dope_game_intelligence_ready.py"
)

# Loop through the scripts and execute them
for script in "${SCRIPTS[@]}"; do
    echo "Running $script..."
    $PYTHON_EXEC "$script"
    if [ $? -ne 0 ]; then
        echo "Error running $script. Retrying..."
        $PYTHON_EXEC "$script"
        if [ $? -ne 0 ]; then
            echo "Error running $script after retry. Marking as failed and continuing."
            # In a real scenario, you might want to log this more formally or exit
        fi
    fi
done

echo "All scripts attempted."
