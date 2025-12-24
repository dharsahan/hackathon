import sys
import os

# Add smart_file_organizer to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

print("Checking imports for Android compatibility...")

try:
    print("Importing Config...")
    from smart_file_organizer.src.config import Config
    print("Config imported.")
except ImportError as e:
    print(f"FAILED to import Config: {e}")

try:
    print("Importing RulesEngine...")
    from smart_file_organizer.src.actions.rules_engine import RulesEngine
    print("RulesEngine imported.")
except ImportError as e:
    print(f"FAILED to import RulesEngine: {e}")

try:
    print("Importing Classification (This might fail if ML libs are missing)...")
    # This module might import torch/transformers
    from smart_file_organizer.src.classification import tier1_metadata
    print("Classification tier1_metadata imported.")
except ImportError as e:
    print(f"FAILED to import Classification: {e}")
    print("Note: If this fails, we need to ensure RulesEngine doesn't strictly depend on it for basic rules.")

print("Import check complete.")
