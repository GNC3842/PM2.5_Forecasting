"""
Checks if the manifest is valid. If not, it prints the problems and exits with a non-zero status code.
"""

import sys

from pm25 import manifest

if __name__ == "__main__":
    problems = manifest.verify()
    for problem in problems:
        print(problem)
    print(f"{len(problems)} problem(s)")
    if len(problems) > 0:
        print("Please fix the problems and re-run this script.")
        sys.exit(1)
    sys.exit(0)
