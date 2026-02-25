#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSeek LLM Configuration

This module provides configuration helpers for using DeepSeek as the LLM provider
for legal extraction, routing decisions, and intelligent file organization.

Usage:
    from deepseek_config import get_deepseek_config

    config = get_deepseek_config()  # Prompts for API key if needed
    model = OpenAIModel(config)
    model.initialize()
    response = model.generate("Your prompt here")
"""

import os
import sys
import getpass
from pathlib import Path

# Fix Unicode encoding for Windows console
if sys.platform == 'win32':
    try:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except:
        pass  # Fallback to default encoding

from file_organizer.models.base import ModelConfig, ModelType


# Default API key (set yours here if environment variable doesn't work)
DEFAULT_DEEPSEEK_API_KEY = 


def get_deepseek_config(
    model_name: str = "deepseek-chat",
    temperature: float = 0.7,
    max_tokens: int = 3000,
    prompt_for_key: bool = True
) -> ModelConfig:
    """
    Get DeepSeek model configuration with API key.

    Args:
        model_name: DeepSeek model to use (default: deepseek-chat)
        temperature: Model temperature (0.0-1.0)
        max_tokens: Maximum tokens in response
        prompt_for_key: If True, prompts for API key if not in environment

    Returns:
        ModelConfig ready for use with OpenAIModel

    Environment Variables:
        DEEPSEEK_API_KEY: DeepSeek API key (optional if prompt_for_key=True)
    """
    # Check for API key in environment, then default
    api_key = os.environ.get("DEEPSEEK_API_KEY") or DEFAULT_DEEPSEEK_API_KEY

    if not api_key and prompt_for_key:
        print("=" * 70)
        print("DEEPSEEK API KEY REQUIRED")
        print("=" * 70)
        print("Get your API key from: https://platform.deepseek.com/")
        print()
        api_key = getpass.getpass("Enter your DeepSeek API key: ").strip()

        if not api_key:
            raise ValueError("DeepSeek API key is required")
    elif not api_key:
        raise ValueError(
            "DEEPSEEK_API_KEY environment variable not set. "
            "Set it or use prompt_for_key=True"
        )

    # Create configuration
    config = ModelConfig(
        name=model_name,
        model_type=ModelType.TEXT,
        framework="openai",
        temperature=temperature,
        max_tokens=max_tokens,
        extra_params={
            "url": "https://api.deepseek.com/v1",
            "api_key": api_key
        }
    )

    return config


def test_deepseek_connection(config: ModelConfig) -> bool:
    """
    Test DeepSeek API connection.

    Args:
        config: DeepSeek ModelConfig to test

    Returns:
        True if connection successful, False otherwise
    """
    from file_organizer.models.openai_model import OpenAIModel

    try:
        model = OpenAIModel(config)
        model.initialize()
        response = model.generate("Respond with 'OK' if you're working.")
        model.cleanup()

        print("[OK] DeepSeek connected successfully")
        print(f"  Model: {config.name}")
        print(f"  Response: {response[:100]}")
        return True

    except Exception as e:
        print(f"[FAILED] DeepSeek connection failed: {e}")
        return False


def save_api_key_to_env(api_key: str, env_file: Path = None):
    """
    Save API key to .env file for future use.

    Args:
        api_key: DeepSeek API key
        env_file: Path to .env file (default: .env in current directory)
    """
    if env_file is None:
        env_file = Path.cwd() / ".env"

    # Read existing .env if present
    existing_content = ""
    if env_file.exists():
        existing_content = env_file.read_text()

    # Check if key already exists
    if "DEEPSEEK_API_KEY=" in existing_content:
        print(f"DEEPSEEK_API_KEY already exists in {env_file}")
        return

    # Append key
    with open(env_file, "a") as f:
        if existing_content and not existing_content.endswith("\n"):
            f.write("\n")
        f.write(f"DEEPSEEK_API_KEY={api_key}\n")

    print(f"✓ API key saved to {env_file}")
    print("  Add this to your .gitignore to keep it secret!")


if __name__ == "__main__":
    """Test DeepSeek configuration"""
    print("DeepSeek Configuration Test")
    print("=" * 70)

    try:
        # Get configuration
        config = get_deepseek_config()

        print()
        print("Configuration:")
        print(f"  Model: {config.name}")
        print(f"  Endpoint: {config.extra_params['url']}")
        print(f"  Temperature: {config.temperature}")
        print(f"  Max Tokens: {config.max_tokens}")
        print()

        # Test connection
        if test_deepseek_connection(config):
            print()
            print("=" * 70)
            print("SUCCESS! DeepSeek is configured and working.")
            print("=" * 70)

            # Offer to save API key
            save = input("\nSave API key to .env file? (yes/no): ").strip().lower()
            if save in ['yes', 'y']:
                save_api_key_to_env(config.extra_params['api_key'])
        else:
            print("\nPlease check your API key and try again.")
            sys.exit(1)

    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)

