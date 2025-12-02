#!/usr/bin/env python3
"""
Simple script to attempt importing every module under a given package and report failures.

Usage:
    python scripts/check_imports.py app

This is helpful for catching import-time errors (ImportError, AttributeError, SyntaxError, etc.)
that occur when importing modules during application startup.
"""
import importlib
import pkgutil
import sys
import traceback
from types import ModuleType


def find_package(name: str) -> ModuleType:
    try:
        return importlib.import_module(name)
    except Exception as e:
        print(f"Fatal: unable to import base package '{name}': {e}")
        traceback.print_exc()
        sys.exit(2)


def check_package(pkg_name: str) -> int:
    pkg = find_package(pkg_name)
    failures = []
    total = 0
    for finder, module_name, ispkg in pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + "."):
        total += 1
        try:
            importlib.import_module(module_name)
        except Exception as e:
            failures.append((module_name, e))
    print(f"Scanned {total} modules under {pkg_name}, found {len(failures)} failures")
    if failures:
        print("\nFailures:")
        for name, exc in failures:
            print("- ", name)
            traceback.print_exception(type(exc), exc, exc.__traceback__)
        return 1
    print("All imports OK ✅")
    return 0


def main():
    if len(sys.argv) < 2:
        print("Usage: check_imports.py <package_name>")
        sys.exit(2)
    pkg_name = sys.argv[1]
    sys.exit(check_package(pkg_name))


if __name__ == "__main__":
    main()
