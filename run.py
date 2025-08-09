#!/usr/bin/env python3
"""
Launcher script for Instagram-Telegram chat integration.
This script sets up the Python path correctly and runs the main application.
"""

import sys
import os
from pathlib import Path

# Add the src directory to Python path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

# Add the project root to Python path for config imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    # Import and run the main application
    from main import main
    
    try:
        import asyncio
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nApplication stopped by user")
    except Exception as e:
        print(f"Error running application: {e}")
        sys.exit(1) 