"""
Emergency cleanup script to merge fragmented case folders.
Runs in minutes, not hours.
"""

import os
import shutil
import re
from pathlib import Path
from collections import defaultdict

def normalize_case_number(case_str):
    """Normalize case numbers to merge variations."""
    if not case_str:
        return None

    # Remove spaces, underscores, dashes
    normalized = re.sub(r'[\s_-]+', '', str(case_str).upper())

    # Extract pattern: 19CR051799520, 19CRS51799, etc.
    match = re.search(r'(\d{2,4})(CR|CRS|CVD|JA|MO|DHC)S?(\d+)', normalized)
    if match:
        year = match.group(1)
        case_type = match.group(2).replace('CRS', 'CR')  # Normalize CRS -> CR
        number = match.group(3).lstrip('0')  # Remove leading zeros
        return f"{year}CR{number}"

    return normalized

def merge_case_folders(base_path):
    """Merge all variations of the same case into one canonical folder."""
    base = Path(base_path)

    # Find all case folders
    case_materials = base / "01_Case_Materials"
    if not case_materials.exists():
        print(f"No case materials folder found at {case_materials}")
        return

    # Scan for case-related folders
    case_folders = defaultdict(list)

    for item in case_materials.iterdir():
        if not item.is_dir():
            continue

        # Look for folders like "01_Filings_Motions"
        for subfolder in item.iterdir():
            if not subfolder.is_dir():
                continue

            # Check if this is a case number folder
            folder_name = subfolder.name
            normalized = normalize_case_number(folder_name)

            if normalized:
                case_folders[normalized].append(subfolder)

    # Merge duplicates
    merged_count = 0
    for canonical_case, folders in case_folders.items():
        if len(folders) <= 1:
            continue

        print(f"\nMerging {len(folders)} variations of case {canonical_case}:")

        # Pick the first folder as the target
        target = folders[0]
        print(f"  Target: {target}")

        # Merge all others into it
        for source in folders[1:]:
            print(f"  Merging: {source}")

            # Move all files from source to target
            for file in source.rglob('*'):
                if file.is_file():
                    rel_path = file.relative_to(source)
                    dest = target / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)

                    if dest.exists():
                        # Handle duplicates
                        base_name = dest.stem
                        ext = dest.suffix
                        counter = 1
                        while dest.exists():
                            dest = dest.parent / f"{base_name}_{counter}{ext}"
                            counter += 1

                    shutil.move(str(file), str(dest))
                    merged_count += 1

            # Remove empty source folder
            try:
                shutil.rmtree(source)
                print(f"  Removed: {source}")
            except:
                pass

    print(f"\n✓ Merged {merged_count} files across {len([f for f in case_folders.values() if len(f) > 1])} cases")

if __name__ == "__main__":
    org_folder = Path(r"E:\Organization_Folder")
    print(f"Scanning: {org_folder}")
    merge_case_folders(org_folder)
    print("\n✓ Cleanup complete!")
