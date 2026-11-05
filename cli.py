#!/usr/bin/env python3
"""
OpenATS Command Line Interface Shim.
Delegates execution to openats.cli.main.
Author: Nazmul (@3447nazmul) | Repository: https://github.com/3447nazmul/openats
"""
import sys
import os

# Ensure project root is in sys.path when invoked directly
repo_root = os.path.abspath(os.path.dirname(__file__))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from openats.cli import main

if __name__ == "__main__":
    sys.exit(main())
