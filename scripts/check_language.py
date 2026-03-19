#!/usr/bin/env python3
"""
Language checker for agent project (monorepo).

Checks that source code contains only English (no Chinese characters).
Documentation (docs/) is excluded since it provides Chinese versions.

Exit codes:
- 0: All checks passed
- 1: Errors found
"""

import argparse
import re
import sys
from pathlib import Path

# Regex pattern for Chinese characters (CJK Unified Ideographs)
CHINESE_PATTERN = re.compile(
    r"[\u4e00-\u9fff"  # CJK Unified Ideographs
    r"\u3400-\u4dbf"  # CJK Unified Ideographs Extension A
    r"\U00020000-\U0002a6df"  # CJK Unified Ideographs Extension B
    r"\u3000-\u303f"  # CJK Symbols and Punctuation
    r"\uff00-\uffef]"  # Halfwidth and Fullwidth Forms
)

# File extensions to check
SOURCE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".vue"}

# Directories to exclude from checking
EXCLUDE_DIRS = {
    "__pycache__",
    ".git",
    ".tox",
    ".venv",
    "venv",
    "node_modules",
    ".nonpublic",
    "dist",
    "build",
    ".eggs",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".chainlit",
}


class LanguageChecker:
    """Check that source code files contain only English."""

    def __init__(self, root_dir: str, verbose: bool = False) -> None:
        self.root_dir = Path(root_dir)
        self.verbose = verbose
        self.errors: list[str] = []

    def log(self, message: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)

    def _should_exclude(self, path: Path) -> bool:
        """Check if path should be excluded from checking."""
        for part in path.parts:
            if part in EXCLUDE_DIRS:
                return True
        return False

    def _check_file(self, filepath: Path) -> list[tuple[int, str]]:
        """Check a file for Chinese characters.

        Returns list of (line_number, line_content) tuples.
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

    def check_packages(self) -> int:
        """Check all source files in packages/ directory.

        Returns number of files with Chinese characters.
        """
        self.log("\n=== Checking source code for Chinese characters ===")
        packages_dir = self.root_dir / "packages"
        files_with_chinese = 0

        if not packages_dir.exists():
            self.log("Warning: packages/ directory not found")
            return 0

        for filepath in packages_dir.rglob("*"):
            if not filepath.is_file():
                continue
            if filepath.suffix not in SOURCE_EXTENSIONS:
                continue
            if self._should_exclude(filepath):
                continue

            chinese_lines = self._check_file(filepath)
            if chinese_lines:
                files_with_chinese += 1
                rel_path = filepath.relative_to(self.root_dir)
                for line_num, content in chinese_lines:
                    error_msg = (
                        f"ERROR: Chinese found in "
                        f"{rel_path}:{line_num}: {content[:60]}..."
                    )
                    self.errors.append(error_msg)
                    print(error_msg)

        if files_with_chinese == 0:
            self.log("✓ No Chinese characters found in source code")

        return files_with_chinese

    def check_ci_configs(self) -> int:
        """Check CI/CD configuration files for Chinese characters.

        Returns number of files with Chinese characters.
        """
        self.log("\n=== Checking CI/CD configuration files ===")
        github_dir = self.root_dir / ".github"
        files_with_chinese = 0

        if not github_dir.exists():
            self.log("✓ .github directory does not exist")
            return 0

        for filepath in github_dir.rglob("*"):
            if not filepath.is_file():
                continue
            if filepath.suffix not in {".yml", ".yaml", ".md"}:
                continue

            chinese_lines = self._check_file(filepath)
            if chinese_lines:
                files_with_chinese += 1
                rel_path = filepath.relative_to(self.root_dir)
                for line_num, content in chinese_lines:
                    error_msg = (
                        f"ERROR: Chinese found in "
                        f"{rel_path}:{line_num}: {content[:60]}..."
                    )
                    self.errors.append(error_msg)
                    print(error_msg)

        if files_with_chinese == 0:
            self.log("✓ No Chinese found in CI configuration")

        return files_with_chinese

    def check_scripts(self) -> int:
        """Check script files for Chinese characters.

        Returns number of files with Chinese characters.
        """
        self.log("\n=== Checking scripts ===")
        scripts_dir = self.root_dir / "scripts"
        files_with_chinese = 0

        if not scripts_dir.exists():
            return 0

        for filepath in scripts_dir.rglob("*"):
            if not filepath.is_file():
                continue
            if filepath.suffix not in {".sh", ".py"}:
                continue

            chinese_lines = self._check_file(filepath)
            if chinese_lines:
                files_with_chinese += 1
                rel_path = filepath.relative_to(self.root_dir)
                for line_num, content in chinese_lines:
                    error_msg = (
                        f"ERROR: Chinese found in "
                        f"{rel_path}:{line_num}: {content[:60]}..."
                    )
                    self.errors.append(error_msg)
                    print(error_msg)

        if files_with_chinese == 0:
            self.log("✓ No Chinese found in scripts")

        return files_with_chinese

    def run_all_checks(self) -> int:
        """Run all language checks.

        Returns exit code (0 = success, 1 = errors found).
        """
        print("=" * 60)
        print("Language Check for Agent Project")
        print("=" * 60)

        self.check_packages()
        self.check_ci_configs()
        self.check_scripts()

        print("\n" + "=" * 60)
        print("Summary")
        print("=" * 60)

        if self.errors:
            print(f"\n❌ Errors: {len(self.errors)}")
            for error in self.errors:
                print(f"  - {error}")
            print("\n❌ Language checks FAILED!")
            return 1
        else:
            print("\n✅ All language checks passed!")
            return 0


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Check language requirements for the agent project"
    )
    parser.add_argument(
        "--root",
        "-r",
        default=".",
        help="Root directory of the project (default: current directory)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()
    checker = LanguageChecker(args.root, args.verbose)
    sys.exit(checker.run_all_checks())


if __name__ == "__main__":
    main()
