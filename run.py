#!/usr/bin/env python3
"""
EduTutor — Cross-platform launcher.
Works on macOS, Linux, and Windows.

Usage:
    python run.py              # Start everything (builds data if needed)
    python run.py --setup      # Install dependencies only
    python run.py --build      # Build data from NCERT PDFs
    python run.py --stop       # Stop all services
"""

import os
import sys
import subprocess
import shutil
import time
import signal
import argparse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
DATA_DIR = ROOT / "data"
VENV_DIR = BACKEND_DIR / ".venv"
PORT_FRONTEND = 3000
PORT_BACKEND = 8000

# NCERT zip download URLs
NCERT_ZIPS = {
    "lech1dd.zip": "https://ncert.nic.in/textbook/pdf/lech1dd.zip",
    "lech2dd.zip": "https://ncert.nic.in/textbook/pdf/lech2dd.zip",
    "leph1dd.zip": "https://ncert.nic.in/textbook/pdf/leph1dd.zip",
    "leph2dd.zip": "https://ncert.nic.in/textbook/pdf/leph2dd.zip",
    "lemh1dd.zip": "https://ncert.nic.in/textbook/pdf/lemh1dd.zip",
    "lemh2dd.zip": "https://ncert.nic.in/textbook/pdf/lemh2dd.zip",
}

# ─── Helpers ────────────────────────────────────────────────────────────────

def log(msg, color="green"):
    colors = {"green": "\033[92m", "yellow": "\033[93m", "red": "\033[91m", "cyan": "\033[96m", "reset": "\033[0m"}
    print(f"{colors.get(color, '')}{msg}{colors['reset']}")


def run(cmd, cwd=None, env=None, check=True, capture=False):
    return subprocess.run(
        cmd, cwd=cwd, env=env,
        shell=isinstance(cmd, str),
        check=check,
        capture_output=capture,
        text=capture,
    )


def is_port_free(port):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def kill_port(port):
    if sys.platform == "win32":
        run(f"for /f \"tokens=5\" %a in ('netstat -ano ^| findstr :{port} ^| findstr LISTENING') do taskkill /PID %a /F", check=False)
    else:
        run(f"lsof -ti:{port} | xargs kill -9 2>/dev/null || true", check=False)


def wait_for_port(port, timeout=30):
    import socket
    for _ in range(timeout * 2):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.5)
    return False


def find_python():
    for cmd in ["python3", "python"]:
        path = shutil.which(cmd)
        if path:
            try:
                result = subprocess.run([cmd, "--version"], capture_output=True, text=True)
                if "Python 3" in result.stdout:
                    return cmd
            except Exception:
                pass
    return None


def find_node():
    return shutil.which("node") and shutil.which("npm")


def get_venv_python():
    if sys.platform == "win32":
        return str(VENV_DIR / "Scripts" / "python")
    return str(VENV_DIR / "bin" / "python")


def get_venv_pip():
    if sys.platform == "win32":
        return str(VENV_DIR / "Scripts" / "pip")
    return str(VENV_DIR / "bin" / "pip")


def data_is_built():
    """Check if compiled data exists."""
    return (DATA_DIR / "compiled").exists() and any((DATA_DIR / "compiled").iterdir())


# ─── Download NCERT PDFs ────────────────────────────────────────────────────

def download_ncert_pdfs():
    """Download NCERT chapter-wise zip files."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for filename, url in NCERT_ZIPS.items():
        zip_path = DATA_DIR / filename
        if zip_path.exists():
            log(f"  Already have {filename}", "green")
            continue
        log(f"  Downloading {filename}...", "yellow")
        try:
            urllib.request.urlretrieve(url, zip_path)
            log(f"  Downloaded {filename}", "green")
        except Exception as e:
            log(f"  Failed to download {filename}: {e}", "red")
            log(f"  Download manually from: https://ncert.nic.in/textbook.php", "yellow")
            log(f"  Place zip files in: {DATA_DIR}", "yellow")
            return False
    return True


# ─── Build Pipeline ─────────────────────────────────────────────────────────

def build_data():
    """Build all data from NCERT PDFs."""
    log("=== Building data from NCERT PDFs ===", "cyan")

    python = get_venv_python()

    # Step 1: Download zips
    log("[1/4] Downloading NCERT PDFs...", "yellow")
    if not download_ncert_pdfs():
        log("Download failed. Place zip files manually in data/ and retry.", "red")
        return False

    # Step 2: Build raw PDFs from zips
    log("[2/4] Building raw PDFs from chapter zips...", "yellow")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    result = run([python, "scripts/build_raw_pdfs.py"], cwd=str(ROOT), env=env, capture=True)
    if result.returncode != 0:
        log(f"Failed to build raw PDFs: {result.stderr}", "red")
        return False
    log(result.stdout, "green")

    # Step 3: Compile PDFs into concept graphs
    log("[3/4] Compiling PDFs into concept graphs...", "yellow")
    result = run([python, "-m", "backend.compiler.pipeline"], cwd=str(ROOT), env=env, capture=True)
    if result.returncode != 0:
        log(f"Compiler failed: {result.stderr}", "red")
        return False
    log(result.stdout, "green")

    # Step 4: Build embeddings
    log("[4/4] Building embeddings...", "yellow")
    # Install embedding requirements
    run([get_venv_pip(), "install", "-q", "-r", str(BACKEND_DIR / "requirements-embeddings.txt")], check=False)
    result = run([python, "scripts/build_bge_embeddings.py"], cwd=str(ROOT), env=env, capture=True)
    if result.returncode != 0:
        log(f"Embedding build failed (non-fatal): {result.stderr}", "yellow")
    else:
        log(result.stdout, "green")

    log("=== Data build complete! ===", "green")
    return True


# ─── Setup ──────────────────────────────────────────────────────────────────

def setup():
    """Install all dependencies."""
    log("=== EduTutor Setup ===", "cyan")

    # Check Python
    python = find_python()
    if not python:
        log("ERROR: Python 3 not found. Install from https://python.org", "red")
        sys.exit(1)
    log(f"Python: {python}", "green")

    # Check Node.js
    if not find_node():
        log("ERROR: Node.js not found. Install from https://nodejs.org", "red")
        sys.exit(1)
    log(f"Node: {subprocess.run(['node', '--version'], capture_output=True, text=True).stdout.strip()}", "green")

    # Create venv
    if not VENV_DIR.exists():
        log("Creating Python virtual environment...", "yellow")
        run([python, "-m", "venv", str(VENV_DIR)])

    # Install Python dependencies
    log("Installing Python dependencies...", "yellow")
    run([get_venv_pip(), "install", "-q", "-r", str(BACKEND_DIR / "requirements.txt")])

    # Install frontend dependencies
    log("Installing Node.js dependencies...", "yellow")
    run(["npm", "install"], cwd=str(FRONTEND_DIR))

    # Copy .env if not exists
    env_file = ROOT / ".env"
    env_sample = ROOT / ".env.sample"
    if not env_file.exists() and env_sample.exists():
        shutil.copy(env_sample, env_file)
        log("Created .env from .env.sample — edit with your API keys", "yellow")

    log("=== Setup complete! ===", "green")


# ─── Start ──────────────────────────────────────────────────────────────────

def start():
    """Start backend + frontend."""
    log("=== Starting EduTutor ===", "cyan")

    # Check venv exists
    if not VENV_DIR.exists():
        log("Run setup first: python run.py --setup", "red")
        sys.exit(1)

    # Build data if not already built
    if not data_is_built():
        log("Data not found — building from NCERT PDFs...", "yellow")
        if not build_data():
            log("Data build failed. Fix errors and retry.", "red")
            sys.exit(1)

    # Kill stale processes
    kill_port(PORT_FRONTEND)
    kill_port(PORT_BACKEND)
    time.sleep(1)

    python = get_venv_python()

    # Start backend
    log(f"Starting backend on :{PORT_BACKEND}...", "yellow")
    backend_env = os.environ.copy()
    backend_env["PYTHONPATH"] = str(ROOT)
    backend_proc = subprocess.Popen(
        [python, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(PORT_BACKEND)],
        cwd=str(ROOT),
        env=backend_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Wait for backend
    log("Waiting for backend...", "yellow")
    if wait_for_port(PORT_BACKEND, timeout=30):
        log(f"Backend ready on :{PORT_BACKEND}", "green")
    else:
        log("Backend slow to start — continuing anyway", "yellow")

    # Start frontend
    log(f"Starting frontend on :{PORT_FRONTEND}...", "yellow")
    frontend_env = os.environ.copy()
    frontend_env["PORT"] = str(PORT_FRONTEND)
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(FRONTEND_DIR),
        env=frontend_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Wait for frontend
    if wait_for_port(PORT_FRONTEND, timeout=30):
        log(f"Frontend ready on :{PORT_FRONTEND}", "green")
    else:
        log("Frontend slow to start — continuing anyway", "yellow")

    # Print instructions
    print()
    log("=== EduTutor is ready! ===", "green")
    print(f"  Local:   http://localhost:{PORT_FRONTEND}")
    print(f"  Ngrok:   ngrok http {PORT_FRONTEND}")
    print()
    print("Press Ctrl+C to stop all services.")
    print()

    # Handle shutdown
    def shutdown(sig=None, frame=None):
        log("\nShutting down...", "yellow")
        backend_proc.terminate()
        frontend_proc.terminate()
        try:
            backend_proc.wait(timeout=5)
            frontend_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            backend_proc.kill()
            frontend_proc.kill()
        log("Stopped.", "green")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Tail output from both processes
    procs = [("backend", backend_proc), ("frontend", frontend_proc)]

    try:
        while True:
            for name, proc in procs:
                if proc.poll() is not None:
                    log(f"{name} exited with code {proc.returncode}", "red")
                    shutdown()
                line = proc.stdout.readline()
                if line:
                    prefix = f"[{name}]"
                    stripped = line.strip()
                    if stripped and "WARNING" not in stripped and "Console Ninja" not in stripped:
                        print(f"{prefix} {stripped}")
            time.sleep(0.1)
    except KeyboardInterrupt:
        shutdown()


# ─── Stop ───────────────────────────────────────────────────────────────────

def stop():
    """Stop all services."""
    log("Stopping services...", "yellow")
    kill_port(PORT_FRONTEND)
    kill_port(PORT_BACKEND)
    log("All services stopped.", "green")


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="EduTutor launcher")
    parser.add_argument("--setup", action="store_true", help="Install dependencies")
    parser.add_argument("--build", action="store_true", help="Build data from NCERT PDFs")
    parser.add_argument("--stop", action="store_true", help="Stop all services")
    args = parser.parse_args()

    if args.setup:
        setup()
    elif args.build:
        build_data()
    elif args.stop:
        stop()
    else:
        start()


if __name__ == "__main__":
    main()
