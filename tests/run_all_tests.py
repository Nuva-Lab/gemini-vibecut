#!/usr/bin/env python
"""
Run All Tests

Executes all test files and reports results.

Run: python tests/run_all_tests.py
"""

import subprocess
import sys
from pathlib import Path


def run_test(test_file: Path) -> bool:
    """Run a single test file and return success status."""
    print(f"\n{'='*60}")
    print(f"Running: {test_file.name}")
    print("="*60 + "\n")

    result = subprocess.run(
        [sys.executable, str(test_file)],
        cwd=test_file.parent.parent,  # Run from project root
    )

    return result.returncode == 0


def main():
    tests_dir = Path(__file__).parent

    print("\n" + "="*60)
    print(" CREATIVE UNIVERSE - TEST SUITE")
    print("="*60)

    # Find all test files
    test_files = sorted(tests_dir.glob("test_*.py"))

    print(f"\nFound {len(test_files)} test files:")
    for f in test_files:
        print(f"  • {f.name}")

    # Run each test
    results = {}
    for test_file in test_files:
        results[test_file.name] = run_test(test_file)

    # Summary
    print("\n" + "="*60)
    print(" TEST SUITE SUMMARY")
    print("="*60 + "\n")

    passed = sum(1 for v in results.values() if v)
    failed = len(results) - passed

    for name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status}  {name}")

    print()
    print(f"Passed: {passed}/{len(results)}")
    print(f"Failed: {failed}/{len(results)}")

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!\n")
        return 0
    else:
        print(f"\n⚠️  {failed} TEST(S) FAILED\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
