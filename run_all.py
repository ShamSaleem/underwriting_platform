#!/usr/bin/env python3
"""run_all.py - initialise and launch the Underwriting Platform locally.

  Backend  (FastAPI) : http://localhost:8080
  Frontend (Vite dev): http://localhost:5173   (proxies /api -> :8080)

First run creates the backend venv (.unde) and installs all deps; later runs
reuse them. On Windows each service opens in its own console window with hot
reload. Set ANTHROPIC_API_KEY / GEMINI_API_KEY beforehand to enable the AI layer.

Usage:
    python run_all.py                 # install (if needed) + launch both services
    python run_all.py --install-only  # just create the venv + install deps, no launch

Login: admin / aegis2024
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VENV = BACKEND / ".unde"
IS_WINDOWS = os.name == "nt"
PY = VENV / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")


def need(cmd: str) -> str:
    path = shutil.which(cmd)
    if not path:
        sys.exit(f"'{cmd}' was not found on PATH. Install it and re-run.")
    return path


def run(args: list[str], cwd: Path) -> None:
    print(f"  $ {' '.join(args)}  (in {cwd})")
    subprocess.run(args, cwd=cwd, check=True)


def main() -> None:
    install_only = "--install-only" in sys.argv or "--setup" in sys.argv

    uv = need("uv")
    npm = need("npm")

    # --- backend: venv + dependencies ---------------------------------------
    if not PY.exists():
        print("Creating backend virtual environment (.unde)...")
        run([uv, "venv", str(VENV)], cwd=BACKEND)
    print("Installing backend dependencies...")
    # --native-tls uses the system cert store (needed behind TLS-inspecting proxies).
    run([uv, "pip", "install", "--native-tls", "--python", str(PY),
         "-r", "requirements.txt"], cwd=BACKEND)

    # --- frontend: npm dependencies -----------------------------------------
    if not (FRONTEND / "node_modules").exists():
        print("Installing frontend dependencies...")
        run([npm, "install"], cwd=FRONTEND)
    else:
        print("Frontend dependencies already present (skipping npm install).")

    if install_only:
        print("\nSetup complete (venv + backend + frontend deps installed). "
              "Run 'python run_all.py' to launch.")
        return

    # --- launch both ---------------------------------------------------------
    print("\nStarting backend on :8080 and frontend on :5173 ...")
    backend_cmd = [str(PY), "-m", "uvicorn", "main:app", "--port", "8080", "--reload"]
    frontend_cmd = [npm, "run", "dev"]

    flags = subprocess.CREATE_NEW_CONSOLE if IS_WINDOWS else 0
    subprocess.Popen(backend_cmd, cwd=BACKEND, creationflags=flags)
    subprocess.Popen(frontend_cmd, cwd=FRONTEND, creationflags=flags)

    print("Launched backend + frontend.")
    print("Open http://localhost:5173  (login: admin / aegis2024)")
    if not IS_WINDOWS:
        print("(Non-Windows: both run in the background of this shell; "
              "use a process manager or two terminals if you prefer.)")


if __name__ == "__main__":
    main()
