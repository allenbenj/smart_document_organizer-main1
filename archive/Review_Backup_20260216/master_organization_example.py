"""
Master Example: LLM-Derived Structure Organizer for E:\\Organization_Folder

This script scans files, uses DeepSeek LLM to derive a custom folder schema,
and organizes files into that schema with high confidence.

Refactored to use modular architecture.
"""

import sys
import logging
from pathlib import Path
import argparse

# Set up the package properly
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Import as if we're in the file_organizer package
import organizer_config
import organizer.processor

OrganizerConfig = organizer_config.OrganizerConfig
OrganizationProcessor = organizer.processor.OrganizationProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('organization.log')
    ]
)
logger = logging.getLogger(__name__)

def main():
    """
    Main entry point for the master example.
    """
    parser = argparse.ArgumentParser(description="File Organization with AI")
    parser.add_argument("--source", "-s", help="Source directory path", default=str(Path(__file__).parent / "test_files"))
    parser.add_argument("--output", "-o", help="Output directory path", default=str(Path(__file__).parent / "organized"))
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without executing")

    args = parser.parse_args()

    # Configuration - use command line args or defaults
    SOURCE_FOLDER = Path(args.source)
    OUTPUT_FOLDER = Path(args.output)

    # Create directories if they don't exist
    SOURCE_FOLDER.mkdir(parents=True, exist_ok=True)
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 70)
    logger.info("FILE-LEVEL ACTION GENERATOR - MODULAR MASTER EXAMPLE")
    logger.info(f"Source: {SOURCE_FOLDER}")
    logger.info(f"Output: {OUTPUT_FOLDER}")
    logger.info("=" * 70)

    # Create Configuration
    config = OrganizerConfig(
        source_folder=SOURCE_FOLDER,
        output_folder=OUTPUT_FOLDER,
        use_llm=True,       # LLM required
        dry_run=args.dry_run,  # Use command line argument
        llm_confidence_threshold=0.8, # High confidence enforcement
        enable_deduplication=True,
        enable_renaming=True,
        enable_indexing=True,
        resume_from_last_run=True  # Resume where it left off
    )

    try:
        # Initialize and Run Processor
        processor = OrganizationProcessor(config)
        processor.run()

        logger.info("\n" + "=" * 70)
        logger.info("✓ ORGANIZATION COMPLETE!")
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"Error during organization: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
