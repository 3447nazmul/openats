#!/usr/bin/env python3
"""
Master Quality Control (QC) Test Runner for OpenATS.
Discovers and executes all unit, integration, and server tests under tests/.
Author: Nazmul (@3447nazmul) | Repository: https://github.com/3447nazmul/openats
"""
import os
import sys
import unittest

def run_all_tests():
    # Ensure repository root is on sys.path
    repo_root = os.path.abspath(os.path.dirname(__file__))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    print("\n" + "=" * 65)
    print(" 🧪 OpenATS Multi-Agent Quality Control (QC) Test Suite")
    print("=" * 65)

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="tests", pattern="test_*.py", top_level_dir=repo_root)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 65)
    if result.wasSuccessful():
        print(f" ✅ QC STATUS: 100% PASSED ({result.testsRun} tests run with 0 errors/failures)")
        print(" 🚀 CERTIFIED READY FOR GITHUB OPEN-SOURCE RELEASE")
        print("=" * 65 + "\n")
        return 0
    else:
        print(f" ❌ QC FAILED: {len(result.failures)} failures, {len(result.errors)} errors.")
        print("=" * 65 + "\n")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
