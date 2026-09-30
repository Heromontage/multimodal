"""Create a portable source bundle for Docker Compose."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "cardiolens-docker-bundle.zip"
TOP_LEVEL = [
    ".dockerignore", ".gitignore", "README.md", "DEBUG_REPORT.md",
    "Makefile", "docker-compose.yml", "requirements.txt", "file.csv",
    "architecture.md", "pr.md", "tech-stack.md", "ps.pdf",
]
SOURCE_DIRS = ["api", "ml", "web", "scripts"]
EXCLUDED_PARTS = {
    "node_modules", "dist", "__pycache__", ".pytest_cache", ".venv",
    "myenv", ".git", ".vite",
}
REQUIRED = [
    "file.csv", "docker-compose.yml", "requirements.txt",
    "ml/artifacts/schema.json", "ml/artifacts/manifest.json",
    *[f"ml/artifacts/models/{target}.joblib" for target in ("CAD", "LAD", "LCX", "RCA")],
]


def main() -> None:
    missing = [name for name in REQUIRED if not (ROOT / name).is_file()]
    if missing:
        raise SystemExit(f"Cannot package without: {', '.join(missing)}")

    paths = [ROOT / name for name in TOP_LEVEL if (ROOT / name).is_file()]
    for directory in SOURCE_DIRS:
        paths.extend(
            path for path in (ROOT / directory).rglob("*")
            if path.is_file()
            and not EXCLUDED_PARTS.intersection(path.relative_to(ROOT).parts)
            and path.suffix not in {".pyc", ".log"}
        )

    with ZipFile(OUTPUT, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(set(paths)):
            archive.write(path, arcname=Path("cardiolens") / path.relative_to(ROOT))
    print(f"Created {OUTPUT} with {len(set(paths))} files ({OUTPUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
