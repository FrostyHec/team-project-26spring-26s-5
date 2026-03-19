#!/usr/bin/env python3
"""
Language checker for deep-solutions project.

This script checks:
1. Source code contains only English (no Chinese characters in comments/strings)
2. Documentation requirements (via document_checker module)

Exit codes:
- 0: All checks passed
- 1: Errors found
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import List, Tuple

# Import document checker module
try:
    from document_checker import DocumentChecker
except ImportError:
    # Try relative import if running as script
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from document_checker import DocumentChecker

# Regex pattern for Chinese characters (CJK Unified Ideographs)
# Using proper Unicode escapes for extended ranges
CHINESE_PATTERN = re.compile(
    r"[\u4e00-\u9fff"  # CJK Unified Ideographs
    r"\u3400-\u4dbf"   # CJK Unified Ideographs Extension A
    r"\U00020000-\U0002a6df"  # CJK Unified Ideographs Extension B (use \U for 8-digit)
    r"\u3000-\u303f"   # CJK Symbols and Punctuation
    r"\uff00-\uffef]"  # Halfwidth and Fullwidth Forms
)

# Files/directories to exclude from source code check
EXCLUDE_PATTERNS = [
    "__pycache__",
    "/.git/",  # Use directory separators to avoid matching .github
    "/.git\\",
    ".tox",
    "*.egg-info",
    "build",
    "dist",
    ".nonpublic",
]


class LanguageChecker:
    """Check language requirements for the project."""

    def __init__(self, root_dir: str, verbose: bool = False):
        self.root_dir = Path(root_dir)
        self.verbose = verbose
        self.errors: List[str] = []
        # Initialize document checker
        self.doc_checker = DocumentChecker(root_dir, verbose)

    def log(self, message: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)

    def check_file_for_chinese(self, filepath: Path) -> List[Tuple[int, str]]:
        """
        Check a file for Chinese characters.

        Returns list of (line_number, line_content) tuples where Chinese was found.
        """
        chinese_lines = []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    if CHINESE_PATTERN.search(line):
                        chinese_lines.append((line_num, line.strip()))
        except (UnicodeDecodeError, IOError) as e:
            self.log(f"Warning: Could not read {filepath}: {e}")
        return chinese_lines

    def should_exclude(self, path: Path) -> bool:
        """Check if path should be excluded from checking."""
        path_str = str(path)
        for pattern in EXCLUDE_PATTERNS:
            if pattern in path_str:
                return True
        return False

    def check_source_code(self) -> int:
        """
        Check source code for Chinese characters.

        Returns number of files with Chinese characters.
        """
        self.log("\n=== Checking source code for Chinese characters ===")
        src_dir = self.root_dir / "src"
        tests_dir = self.root_dir / "tests"

        files_with_chinese = 0

        for directory in [src_dir, tests_dir]:
            if not directory.exists():
                continue

            for filepath in directory.rglob("*.py"):
                if self.should_exclude(filepath):
                    continue

                chinese_lines = self.check_file_for_chinese(filepath)
                if chinese_lines:
                    files_with_chinese += 1
                    rel_path = filepath.relative_to(self.root_dir)
                    for line_num, content in chinese_lines:
                        error_msg = f"ERROR: Chinese found in {rel_path}:{line_num}: {content[:60]}..."
                        self.errors.append(error_msg)
                        print(error_msg)

        if files_with_chinese == 0:
            self.log("✓ No Chinese characters found in source code")

        return files_with_chinese

    def check_ci_configs(self) -> int:
        """
        Check CI/CD configuration files for Chinese characters.

        Returns number of files with Chinese characters.
        """
        self.log("\n=== Checking CI/CD configuration files ===")
        github_dir = self.root_dir / ".github"

        files_with_chinese = 0

        if not github_dir.exists():
            self.log("✓ .github directory does not exist")
            return 0

        # Check workflow files (YAML)
        workflows_dir = github_dir / "workflows"
        if workflows_dir.exists():
            for filepath in workflows_dir.glob("*.yml"):
                if self.should_exclude(filepath):
                    continue

                chinese_lines = self.check_file_for_chinese(filepath)
                if chinese_lines:
                    files_with_chinese += 1
                    rel_path = filepath.relative_to(self.root_dir)
                    for line_num, content in chinese_lines:
                        error_msg = f"ERROR: Chinese found in {rel_path}:{line_num}: {content[:60]}..."
                        self.errors.append(error_msg)
                        print(error_msg)
            
            if files_with_chinese == 0:
                self.log(f"✓ No Chinese found in {workflows_dir.relative_to(self.root_dir)}")

        # Check issue template files (Markdown)
        templates_dir = github_dir / "ISSUE_TEMPLATE"
        if templates_dir.exists():
            for filepath in templates_dir.glob("*.md"):
                if self.should_exclude(filepath):
                    continue

                chinese_lines = self.check_file_for_chinese(filepath)
                if chinese_lines:
                    files_with_chinese += 1
                    rel_path = filepath.relative_to(self.root_dir)
                    for line_num, content in chinese_lines:
                        error_msg = f"ERROR: Chinese found in {rel_path}:{line_num}: {content[:60]}..."
                        self.errors.append(error_msg)
                        print(error_msg)
            
            if files_with_chinese == 0:
                self.log(f"✓ No Chinese found in {templates_dir.relative_to(self.root_dir)}")

        # Check PR template
        pr_template = github_dir / "PULL_REQUEST_TEMPLATE.md"
        if pr_template.exists():
            chinese_lines = self.check_file_for_chinese(pr_template)
            if chinese_lines:
                files_with_chinese += 1
                rel_path = pr_template.relative_to(self.root_dir)
                for line_num, content in chinese_lines:
                    error_msg = f"ERROR: Chinese found in {rel_path}:{line_num}: {content[:60]}..."
                    self.errors.append(error_msg)
                    print(error_msg)
            else:
                self.log(f"✓ Found: {pr_template.relative_to(self.root_dir)}")

        return files_with_chinese

    def run_all_checks(self) -> int:
        """
        Run all language checks.

        Returns exit code (0 = success, 1 = errors found).
        """
        print("=" * 60)
        print("Language Check for deep-solutions")
        print("=" * 60)

        # Check source code
        chinese_in_source = self.check_source_code()

        # Check CI/CD configuration
        chinese_in_ci = self.check_ci_configs()

        # Check documentation (using document_checker module)
        doc_exit_code = self.doc_checker.run_all_checks()

        # Collect all errors
        all_errors = self.errors + self.doc_checker.errors

        # Summary
        print("\n" + "=" * 60)
        print("Summary")
        print("=" * 60)

        if all_errors:
            print(f"\n❌ Errors: {len(all_errors)}")
            for error in all_errors:
                print(f"  - {error}")
            print("\n❌ Language checks FAILED!")
            return 1
        else:
            print("\n✅ All language checks passed!")
            return 0


def main():
    parser = argparse.ArgumentParser(
        description="Check language requirements for deep-solutions project"
    )
    parser.add_argument(
        "--root",
        "-r",
        default=".",
        help="Root directory of the project (default: current directory)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "--source-only",
        "-s",
        action="store_true",
        help="Only check source code for Chinese",
    )
    parser.add_argument(
        "--docs-only",
        "-d",
        action="store_true",
        help="Only check documentation",
    )

    args = parser.parse_args()

    checker = LanguageChecker(args.root, args.verbose)

    if args.source_only:
        exit_code = 1 if checker.check_source_code() > 0 else 0
    elif args.docs_only:
        # Use document_checker directly
        exit_code = checker.doc_checker.run_all_checks()
    else:
        exit_code = checker.run_all_checks()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
