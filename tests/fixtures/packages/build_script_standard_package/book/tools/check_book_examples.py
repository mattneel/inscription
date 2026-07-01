from pathlib import Path

book_root = Path(__file__).resolve().parents[1]
assert (book_root / "book.toml").exists()
assert (book_root / "src" / "SUMMARY.md").exists()
print("fixture book examples checked")
