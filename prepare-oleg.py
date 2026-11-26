#!/usr/bin/env python3
"""Prepare Oleg from a trusted local server archive."""
import argparse
import getpass
import os
from pathlib import Path
import re
import shutil
import tarfile
from tempfile import TemporaryDirectory
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

SOURCE_ROOT = "opt/oleg-bridge/"
FILES = (
    "bridge.py", "oleg_dialogue.py", "oleg_controls.py", "web_chat.py",
    "web_chat.html", "web_sources.py", "airplay_output.py",
    "airplay_volume_event.py", "audio_visualizer.py", "chat_store.py",
)

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=Path("payload/oleg-private.tar"))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("destination", nargs="?", type=Path)
    args = parser.parse_args()
    os.umask(0o077)

    try:
        with tarfile.open(args.archive, "r") as archive:
            members = {
                item.name.removeprefix(SOURCE_ROOT): item
                for item in archive
                if item.isfile() and item.name.startswith(SOURCE_ROOT)
            }
            missing = set(FILES) - members.keys()
            if missing:
                parser.error("Missing files: " + ", ".join(sorted(missing)))
            sources = {}
            for name in FILES:
                with archive.extractfile(members[name]) as source:
                    sources[name] = source.read().decode("utf-8")
                if name.endswith(".py"):
                    compile(sources[name], name, "exec")
            if args.check:
                print("Archive verified. Python source syntax is valid.")
                return

            if args.destination is None:
                parser.error("Specify a new destination directory")
            target = args.destination.absolute()
            if target.exists() or target.is_symlink() or not target.parent.is_dir():
                parser.error("Destination must be new and its parent must exist")

            url = input("Home Assistant URL: ").strip().rstrip("/")
            parts = urlsplit(url)
            if (parts.scheme not in ("http", "https") or not parts.hostname
                    or parts.username is not None or parts.query or parts.fragment):
                parser.error("Enter an HTTP(S) URL without credentials")
            if not os.isatty(0):
                parser.error("Enter the token in an interactive terminal")
            token = getpass.getpass("Home Assistant long-lived token: ").strip()
            if not token or any(char.isspace() for char in token):
                parser.error("Invalid token format")
            request = Request(url + "/api/", headers={"Authorization": "Bearer " + token})
            try:
                with build_opener(NoRedirect()).open(request, timeout=10) as response:
                    if response.status != 200:
                        parser.error("Home Assistant API did not return HTTP 200")
            except (URLError, OSError):
                parser.error("Home Assistant API check failed. Verify the URL and token.")

            endpoint = re.compile(r"https?://192[.]168[.]0[.][0-9]+:8123\b")
            with TemporaryDirectory(prefix=".oleg-", dir=target.parent) as temporary:
                stage = Path(temporary) / "prepared"
                stage.mkdir()
                for name, source in sources.items():
                    (stage / name).write_text(endpoint.sub(lambda _: url, source), encoding="utf-8")
                (stage / "ha.token").write_text(token + "\n", encoding="utf-8")
                (stage / "home-assistant-url.txt").write_text(url + "\n", encoding="utf-8")
                models = stage / "voice-samples"
                models.mkdir()
                for name, item in members.items():
                    model = Path(name)
                    if model.parent == Path("voice-samples") and name.endswith((".onnx", ".onnx.json")):
                        with archive.extractfile(item) as source, (models / model.name).open("wb") as dest:
                            shutil.copyfileobj(source, dest)
                target.mkdir(mode=0o700)
                for item in stage.iterdir():
                    item.rename(target / item.name)
    except (OSError, tarfile.TarError, UnicodeError, SyntaxError) as error:
        parser.error(f"Preparation failed ({type(error).__name__})")
    print(f"Prepared: {target}")

if __name__ == "__main__":
    main()
