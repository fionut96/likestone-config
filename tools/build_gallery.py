#!/usr/bin/env python3
"""
Rebuilds gallery/index.json (the list the iOS app reads) and any missing thumbnails.

Run from anywhere, after adding/removing photos:
    python3 tools/build_gallery.py
then commit and push.

Layout:
    gallery/<Collection>/<Design>/<photo>.jpg
    gallery/<Collection>/<Design>/thumbs/<photo>.jpg   ← created by this script
Photos placed directly in a collection folder (without a design folder) also work.
"""
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GALLERY = ROOT / "gallery"
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
THUMB_SIZE = 400


def natural_key(text):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


def is_photo(path):
    return path.is_file() and path.suffix.lower() in EXTENSIONS and not path.name.startswith(".")


def make_thumbnail(source, target):
    target.parent.mkdir(exist_ok=True)
    try:
        from PIL import Image  # pip3 install pillow
        with Image.open(source) as image:
            image = image.convert("RGB")
            image.thumbnail((THUMB_SIZE, THUMB_SIZE))
            image.save(target, "JPEG", quality=72, optimize=True)
        return
    except ImportError:
        pass
    if shutil.which("sips"):  # built into macOS
        subprocess.run(
            ["sips", "-Z", str(THUMB_SIZE), "-s", "format", "jpeg", "-s", "formatOptions", "72",
             str(source), "--out", str(target)],
            check=True, capture_output=True,
        )
        return
    shutil.copyfile(source, target)  # last resort: full photo as preview


def photo_entry(photo):
    thumb = photo.parent / "thumbs" / (photo.stem + ".jpg")
    if not thumb.exists() or thumb.stat().st_mtime < photo.stat().st_mtime:
        make_thumbnail(photo, thumb)
    return {
        "file": photo.relative_to(ROOT).as_posix(),
        "thumb": thumb.relative_to(ROOT).as_posix(),
    }


def build():
    collections = []
    for collection_dir in sorted((d for d in GALLERY.iterdir() if d.is_dir()), key=lambda d: natural_key(d.name)):
        groups = []
        loose = sorted((p for p in collection_dir.iterdir() if is_photo(p)), key=lambda p: natural_key(p.name))
        if loose:
            groups.append({"name": collection_dir.name, "photos": [photo_entry(p) for p in loose]})
        for group_dir in sorted((d for d in collection_dir.iterdir() if d.is_dir() and d.name != "thumbs"),
                                key=lambda d: natural_key(d.name)):
            photos = sorted((p for p in group_dir.iterdir() if is_photo(p)), key=lambda p: natural_key(p.name))
            if photos:
                groups.append({"name": group_dir.name, "photos": [photo_entry(p) for p in photos]})
        if groups:
            collections.append({"name": collection_dir.name, "groups": groups})

    index = {
        "version": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "collections": collections,
    }
    (GALLERY / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    photo_count = sum(len(g["photos"]) for c in collections for g in c["groups"])
    group_count = sum(len(c["groups"]) for c in collections)
    print(f"gallery/index.json: {len(collections)} collection(s), {group_count} design(s), {photo_count} photo(s)")


if __name__ == "__main__":
    build()
