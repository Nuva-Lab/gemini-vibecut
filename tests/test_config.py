"""
Test: Configuration Loading

Verifies that:
1. Config module loads correctly
2. Environment variables are read
3. Model selection (flash/pro) works
4. Path configuration is correct

Run: python tests/test_config.py
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_config_loading():
    """Test configuration loading."""

    print("=" * 60)
    print("TEST: Configuration Loading")
    print("=" * 60)
    print()

    # Change to project root
    os.chdir(Path(__file__).parent.parent)

    try:
        import config
        print("✓ Config module imported")
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

    # Test model configuration
    print()
    print("Model Configuration:")
    print("-" * 40)
    print(f"  GEMINI_FLASH_MODEL: {config.GEMINI_FLASH_MODEL}")
    print(f"  GEMINI_PRO_MODEL: {config.GEMINI_PRO_MODEL}")
    print(f"  USE_PRO_MODEL: {config.USE_PRO_MODEL}")
    print(f"  → Active model: {config.GEMINI_MODEL}")

    if config.GEMINI_MODEL in [config.GEMINI_FLASH_MODEL, config.GEMINI_PRO_MODEL]:
        print("✓ Model selection valid")
    else:
        print("✗ Model selection invalid")
        return False

    # Test API configuration
    print()
    print("API Configuration:")
    print("-" * 40)
    print(f"  GOOGLE_API_KEY: {'***' + config.GOOGLE_API_KEY[-4:] if config.GOOGLE_API_KEY else 'Not set'}")
    print(f"  USE_VERTEX_AI: {config.USE_VERTEX_AI}")
    print(f"  GOOGLE_CLOUD_PROJECT: {config.GOOGLE_CLOUD_PROJECT or 'Not set'}")

    if config.GOOGLE_API_KEY or config.USE_VERTEX_AI:
        print("✓ API credentials configured")
    else:
        print("⚠ No API credentials set (set GOOGLE_API_KEY or USE_VERTEX_AI)")

    # Test paths
    print()
    print("Path Configuration:")
    print("-" * 40)
    print(f"  PROJECT_ROOT: {config.PROJECT_ROOT}")
    print(f"  ASSETS_DIR: {config.ASSETS_DIR}")
    print(f"  OUTPUT_DIR: {config.OUTPUT_DIR}")
    print(f"  SKILLS_DIR: {config.SKILLS_DIR}")

    if config.PROJECT_ROOT.exists():
        print("✓ PROJECT_ROOT exists")
    else:
        print("✗ PROJECT_ROOT not found")
        return False

    if config.SKILLS_DIR.exists():
        print("✓ SKILLS_DIR exists")
    else:
        print("✗ SKILLS_DIR not found")
        return False

    # Test generation settings
    print()
    print("Generation Settings:")
    print("-" * 40)
    print(f"  CHARACTER_STYLES: {config.CHARACTER_STYLES}")
    print(f"  VIDEO_DURATION_SECONDS: {config.VIDEO_DURATION_SECONDS}")
    print(f"  VIDEO_RESOLUTION: {config.VIDEO_RESOLUTION}")
    print(f"  MUSIC_STYLES: {config.MUSIC_STYLES[:3]}...")
    print("✓ Generation settings loaded")

    # Test temperature settings
    print()
    print("Agent Settings:")
    print("-" * 40)
    print(f"  TEMPERATURE_UNDERSTANDING: {config.TEMPERATURE_UNDERSTANDING}")
    print(f"  TEMPERATURE_CREATIVE: {config.TEMPERATURE_CREATIVE}")
    print(f"  TEMPERATURE_GENERATION: {config.TEMPERATURE_GENERATION}")
    print("✓ Temperature settings loaded")

    print()
    print("✅ Config loading test passed!")
    return True


def test_model_switching():
    """Test that model switching works."""

    print()
    print("=" * 60)
    print("TEST: Model Switching (Flash ↔ Pro)")
    print("=" * 60)
    print()

    import os

    # Save original value
    original = os.environ.get("USE_PRO_MODEL", "")

    # Test Flash (default)
    os.environ["USE_PRO_MODEL"] = "false"

    # Need to reload config to pick up new env var
    import importlib
    import config
    importlib.reload(config)

    print(f"USE_PRO_MODEL=false → Model: {config.GEMINI_MODEL}")
    if "flash" in config.GEMINI_MODEL:
        print("✓ Flash model selected correctly")
    else:
        print("✗ Expected flash model")
        return False

    # Test Pro
    os.environ["USE_PRO_MODEL"] = "true"
    importlib.reload(config)

    print(f"USE_PRO_MODEL=true → Model: {config.GEMINI_MODEL}")
    if "pro" in config.GEMINI_MODEL:
        print("✓ Pro model selected correctly")
    else:
        print("✗ Expected pro model")
        return False

    # Restore original
    if original:
        os.environ["USE_PRO_MODEL"] = original
    else:
        os.environ.pop("USE_PRO_MODEL", None)
    importlib.reload(config)

    print()
    print("✅ Model switching test passed!")
    return True


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print(" CONFIGURATION TESTS")
    print("=" * 60 + "\n")

    test1 = test_config_loading()
    test2 = test_model_switching()

    print("\n" + "=" * 60)
    print(" FINAL RESULT")
    print("=" * 60)

    if test1 and test2:
        print("\n✅ ALL TESTS PASSED\n")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED\n")
        sys.exit(1)
