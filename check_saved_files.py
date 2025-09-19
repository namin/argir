#!/usr/bin/env python3
"""
Check all JSON files in the saved directory for corruption.
"""

import json
from pathlib import Path

def check_saved_files():
    """Check all JSON files in saved directory and report any corruption."""
    saved_dir = Path("saved")
    
    if not saved_dir.exists():
        print("❌ saved/ directory does not exist")
        return
    
    json_files = list(saved_dir.glob("*.json"))
    
    if not json_files:
        print("📂 No JSON files found in saved/ directory")
        return
    
    print(f"🔍 Checking {len(json_files)} JSON files in saved/ directory...")
    print()
    
    valid_files = []
    corrupted_files = []
    
    for file_path in json_files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Basic validation - check if it's a dict and has some expected structure
            if not isinstance(data, dict):
                corrupted_files.append((file_path.name, f"Not a JSON object (got {type(data).__name__})"))
                continue
                
            # Check if it looks like a valid saved query
            has_text = "text" in data
            has_timestamp = "timestamp" in data
            
            if has_text and has_timestamp:
                print(f"✅ {file_path.name} - Valid query file")
                valid_files.append(file_path.name)
            elif "query" in data and "result" in data:
                print(f"✅ {file_path.name} - Valid analysis result file")
                valid_files.append(file_path.name)
            else:
                print(f"⚠️  {file_path.name} - Valid JSON but unexpected structure")
                print(f"   Top-level keys: {list(data.keys())}")
                valid_files.append(file_path.name)
                
        except json.JSONDecodeError as e:
            error_msg = f"JSON parsing error at line {e.lineno}, column {e.colno}: {e.msg}"
            print(f"❌ {file_path.name} - {error_msg}")
            corrupted_files.append((file_path.name, error_msg))
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"❌ {file_path.name} - {error_msg}")
            corrupted_files.append((file_path.name, error_msg))
    
    print()
    print("=" * 50)
    print(f"📊 SUMMARY:")
    print(f"   Valid files: {len(valid_files)}")
    print(f"   Corrupted files: {len(corrupted_files)}")
    
    if corrupted_files:
        print()
        print("🗑️  CORRUPTED FILES:")
        for filename, error in corrupted_files:
            print(f"   - {filename}: {error}")
        print()
        print("💡 You can delete corrupted files with:")
        for filename, _ in corrupted_files:
            print(f"   rm saved/{filename}")
    else:
        print("   🎉 All files are valid!")

if __name__ == "__main__":
    check_saved_files()
