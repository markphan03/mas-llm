#!/bin/bash
#SBATCH --job-name=eval_truthfulqa
#SBATCH --output=logs/eval_truthfulqa_%j.out
#SBATCH --error=logs/eval_truthfulqa_%j.err
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32GB
#SBATCH --time=24:00:00
#SBATCH --partition=gpu

module purge
module load python/3.10
module load cuda/12.1
module load ollama-gpu

# Define virtual environment and requirements
WORK_DIR=/work/vinod/markphan03
VENV_PATH=$WORK_DIR/mas-llm/.venv
REQ_FILE=$WORK_DIR/mas-llm/requirements.txt

# Create the virtual environment if it doesn't exist
if [ ! -d "$VENV_PATH" ]; then
    echo "Creating new virtual environment at $VENV_PATH..."
    python -m venv $VENV_PATH
fi

# Activate the virtual environment
source $VENV_PATH/bin/activate
# Upgrade pip and install dependencies

echo "Installing dependencies from $REQ_FILE..."
python -m pip install --upgrade pip
python -m pip install -r $REQ_FILE

mkdir -p logs

echo "Starting Evaluating..."
python $WORK_DIR/mas-llm/src/evaluation/eval_truthfulqa.py

deactivate
echo "✅ Training finished!"