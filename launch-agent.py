#!/usr/bin/env python3
"""Download the selected Ollama model and start the local AI agent."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

DEFAULT_MODEL = "qwen2.5:1.5b"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    if args.model.startswith("-") or not args.model.strip():
        parser.error("Enter a valid Ollama model name")
    ollama = shutil.which("ollama")
    if ollama is None:
        parser.error("Install and start Ollama from https://ollama.com/download")
    server = Path(__file__).resolve().with_name("processing-server.py")
    if not server.is_file():
        parser.error("Download and extract the complete release ZIP")
    try:
        result = subprocess.run([ollama, "show", args.model],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode:
            subprocess.run([ollama, "pull", args.model], check=True)
        return subprocess.call([sys.executable, str(server), "--model", args.model,
                                "--port", str(args.port)])
    except subprocess.CalledProcessError:
        parser.error("Model download failed. Check that Ollama is running and online.")
    except KeyboardInterrupt:
        return 130

if __name__ == "__main__":
    sys.exit(main())
