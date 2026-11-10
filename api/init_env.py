"""Setup environment lokal sekali; tidak pernah menimpa .env yang sudah ada."""

from pathlib import Path
import secrets

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    destination = root / ".env"
    if destination.exists():
        print(".env sudah ada dan dipertahankan.")
    else:
        template = (root / ".env.example").read_text(encoding="utf-8")
        with destination.open("x", encoding="utf-8") as stream:
            stream.write(
                template.replace("CHANGE_ME_WITH_RANDOM_PASSWORD", secrets.token_urlsafe(24))
            )
        print(".env dibuat dengan password acak. File ini diabaikan Git.")
