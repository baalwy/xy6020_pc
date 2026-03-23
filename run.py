#!/usr/bin/env python3
"""
XY6020 Serial Controller - Launcher Script
Automatically sets up virtual environment and installs dependencies.
Compatible with Windows and Raspberry Pi 5 (Linux ARM64).

Usage:
    python run.py
"""

import os
import sys
import subprocess
import platform


def get_venv_dir():
    """Get the virtual environment directory path."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'venv')


def get_python_executable():
    """Get the Python executable path inside the virtual environment."""
    venv_dir = get_venv_dir()
    if platform.system() == 'Windows':
        return os.path.join(venv_dir, 'Scripts', 'python.exe')
    else:
        return os.path.join(venv_dir, 'bin', 'python')


def get_pip_executable():
    """Get the pip executable path inside the virtual environment."""
    venv_dir = get_venv_dir()
    if platform.system() == 'Windows':
        return os.path.join(venv_dir, 'Scripts', 'pip.exe')
    else:
        return os.path.join(venv_dir, 'bin', 'pip')


def setup_venv():
    """Create virtual environment if it doesn't exist."""
    venv_dir = get_venv_dir()
    python_exe = get_python_executable()

    if not os.path.exists(python_exe):
        print("=" * 50)
        print("  Creating virtual environment...")
        print("=" * 50)
        subprocess.check_call([sys.executable, '-m', 'venv', venv_dir])
        print("  Virtual environment created at:", venv_dir)
    else:
        print("  Virtual environment found at:", venv_dir)


def install_dependencies():
    """Install required packages from requirements.txt."""
    pip_exe = get_pip_executable()
    req_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'requirements.txt')

    if not os.path.exists(req_file):
        print("  ERROR: requirements.txt not found!")
        sys.exit(1)

    print("=" * 50)
    print("  Installing dependencies...")
    print("=" * 50)

    subprocess.check_call([pip_exe, 'install', '-r', req_file])
    print("  Dependencies installed successfully.")


def check_dependencies():
    """Check if all dependencies are installed."""
    python_exe = get_python_executable()
    try:
        result = subprocess.run(
            [python_exe, '-c', 'import flask; import minimalmodbus; import serial'],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def run_server():
    """Run the Flask server using the virtual environment Python."""
    python_exe = get_python_executable()
    app_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.py')

    if not os.path.exists(app_file):
        print("  ERROR: app.py not found!")
        sys.exit(1)

    print()
    print("=" * 50)
    print("  Starting XY6020 Serial Controller...")
    print(f"  Platform: {platform.system()} ({platform.machine()})")
    print("=" * 50)
    print()

    # Run the Flask app
    os.execv(python_exe, [python_exe, app_file])


def main():
    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║       XY6020 Serial Controller Launcher         ║")
    print("║       Windows & Raspberry Pi 5 Compatible       ║")
    print("╚══════════════════════════════════════════════════╝")
    print()
    print(f"  System: {platform.system()} {platform.release()}")
    print(f"  Architecture: {platform.machine()}")
    print(f"  Python: {sys.version}")
    print()

    # Step 1: Setup virtual environment
    setup_venv()

    # Step 2: Check/install dependencies
    if not check_dependencies():
        install_dependencies()
    else:
        print("  All dependencies are already installed.")

    # Step 3: Run the server
    run_server()


if __name__ == '__main__':
    main()
