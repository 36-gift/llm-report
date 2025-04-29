import sys
import os
from pathlib import Path

# Ensure the package directory is in the Python path
# This allows importing llm_report_tool even when running main.py from the root
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import the main function from the package
from llm_report_tool.main import main

if __name__ == "__main__":
    # Call the main function from the package
    # sys.argv will be automatically passed and parsed by the argparse logic within llm_report_tool.main.main
    sys.exit(main())