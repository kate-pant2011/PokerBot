from pathlib import Path
import sys

sys.stdout.reconfigure(encoding="utf-8")

IGNORE_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "env",
    "dist",
    "build",
    ".next",
    "coverage",
    ".pytest_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
}


def tree(path: Path, prefix=""):
    entries = sorted(
        [
            p for p in path.iterdir()
            if p.name not in IGNORE_DIRS
        ],
        key=lambda x: (x.is_file(), x.name.lower())
    )

    for i, entry in enumerate(entries):
        connector = "└── " if i == len(entries) - 1 else "├── "
        print(prefix + connector + entry.name)

        if entry.is_dir():
            extension = "    " if i == len(entries) - 1 else "│   "
            tree(entry, prefix + extension)


if __name__ == "__main__":
    root = Path(".")
    print(root.resolve().name)
    tree(root)