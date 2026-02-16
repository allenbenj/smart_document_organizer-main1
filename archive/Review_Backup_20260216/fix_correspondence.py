#!/usr/bin/env python3
"""
Fix Correspondence Folder - Move misplaced files out

Moves non-email files out of Correspondence folder into proper locations.
"""

import shutil
from pathlib import Path
from loguru import logger

# Configure logging
logger.add("fix_correspondence.log", rotation="10 MB")

# Email/correspondence extensions that SHOULD be in Correspondence
EMAIL_EXTENSIONS = {
    '.html', '.htm', '.eml', '.mbox', '.mboxlist',
    '.mboxview', '.p7s', '.url', '.msg'
}

# Source and destination
CORRESPONDENCE_FOLDER = Path(r"E:\Organization_Folder\01_Correspondence")
WORKING_FOLDER = Path(r"E:\Organization_Folder\02_Working_Folder")

# Categorization rules for misplaced files
CATEGORY_RULES = {
    # Documents go to Resources
    '.docx': 'Resources/Documents',
    '.doc': 'Resources/Documents',
    '.odt': 'Resources/Documents',
    '.xlsx': 'Resources/Documents',
    '.pdf': 'Resources/Documents',

    # Media files
    '.png': 'Resources/Media',
    '.jpg': 'Resources/Media',
    '.jpeg': 'Resources/Media',
    '.mov': 'Resources/Media',
    '.mp4': 'Resources/Media',
    '.m4a': 'Resources/Media',

    # Archives
    '.zip': 'Archives/Old_Files',
    '.rar': 'Archives/Old_Files',
    '.7z': 'Archives/Old_Files',

    # System/executable files - probably shouldn't be organized at all
    '.exe': 'Archives/System_Files',
    '.dll': 'Archives/System_Files',
    '.pdb': 'Archives/System_Files',
    '.cmd': 'Archives/System_Files',
    '.lnk': 'Archives/System_Files',
}


def fix_correspondence_folder():
    """Move all non-email files out of Correspondence folder."""

    logger.info("Starting Correspondence folder cleanup")

    # Find all files
    all_files = list(CORRESPONDENCE_FOLDER.rglob('*'))
    files_only = [f for f in all_files if f.is_file()]

    logger.info(f"Found {len(files_only)} total files in Correspondence")

    # Separate email from non-email
    email_files = []
    misplaced_files = []

    for file in files_only:
        ext = file.suffix.lower()
        if ext in EMAIL_EXTENSIONS or ext.startswith('.mboxview') or ext.startswith('.urootfolder'):
            email_files.append(file)
        else:
            misplaced_files.append(file)

    logger.info(f"Email files (keeping): {len(email_files)}")
    logger.info(f"Misplaced files (moving): {len(misplaced_files)}")

    if not misplaced_files:
        logger.info("No misplaced files found! ✓")
        print("\n✓ Correspondence folder is clean - all files are emails")
        return

    # Group by extension
    by_ext = {}
    for file in misplaced_files:
        ext = file.suffix.lower()
        if ext not in by_ext:
            by_ext[ext] = []
        by_ext[ext].append(file)

    print(f"\n Found {len(misplaced_files)} files that don't belong in Correspondence:\n")
    for ext, files in sorted(by_ext.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"  {len(files):3d} {ext} files")

    # Move files
    moved_count = 0
    error_count = 0

    print(f"\nMoving files out of Correspondence folder...")

    for file in misplaced_files:
        ext = file.suffix.lower()

        # Determine destination
        if ext in CATEGORY_RULES:
            dest_subdir = CATEGORY_RULES[ext]
        else:
            # Unknown extension - put in Archives/Uncategorized
            dest_subdir = 'Archives/Uncategorized'

        dest_dir = WORKING_FOLDER / dest_subdir
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = dest_dir / file.name

        # Handle duplicates
        counter = 1
        original_dest = dest_path
        while dest_path.exists():
            stem = original_dest.stem
            ext_part = original_dest.suffix
            dest_path = original_dest.parent / f"{stem}_{counter}{ext_part}"
            counter += 1

        try:
            shutil.move(str(file), str(dest_path))
            logger.info(f"Moved: {file.name} → {dest_subdir}")
            moved_count += 1
        except Exception as e:
            logger.error(f"Failed to move {file.name}: {e}")
            error_count += 1

    print(f"\n✓ Moved {moved_count} files out of Correspondence")
    if error_count:
        print(f"✗ {error_count} files failed to move (check log)")

    # Final verification
    remaining = list(CORRESPONDENCE_FOLDER.rglob('*'))
    remaining_files = [f for f in remaining if f.is_file()]
    non_email = [f for f in remaining_files if f.suffix.lower() not in EMAIL_EXTENSIONS
                 and not f.suffix.lower().startswith('.mboxview')
                 and not f.suffix.lower().startswith('.urootfolder')]

    print(f"\nFinal status:")
    print(f"  Total files in Correspondence: {len(remaining_files)}")
    print(f"  Email files: {len(remaining_files) - len(non_email)}")
    print(f"  Non-email files: {len(non_email)}")

    if non_email:
        print(f"\n⚠ Warning: Still have {len(non_email)} non-email files")
        for f in non_email[:10]:
            print(f"    {f.name}")
    else:
        print(f"\n✓ SUCCESS: Correspondence folder now contains only emails!")


if __name__ == "__main__":
    fix_correspondence_folder()
