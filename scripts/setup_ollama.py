#!/usr/bin/env python3
"""
Ollama Setup Script for GraphRAG Learning Platform
This script helps install and configure Ollama with Llama 3.1 model.
"""

import os
import sys
import subprocess
import platform
import urllib.request
import json
import time

def run_command(cmd, shell=False):
    """Run a command and return success status."""
    try:
        result = subprocess.run(cmd, shell=shell, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def check_ollama_installed():
    """Check if Ollama is installed."""
    success, _, _ = run_command(["ollama", "--version"])
    return success

def install_ollama_windows():
    """Install Ollama on Windows."""
    print("Installing Ollama on Windows...")

    # Download and install Ollama
    ollama_url = "https://ollama.ai/download/OllamaSetup.exe"
    installer_path = "ollama_installer.exe"

    print(f"Downloading Ollama installer from {ollama_url}...")
    try:
        urllib.request.urlretrieve(ollama_url, installer_path)
        print("Download complete.")
    except Exception as e:
        print(f"Failed to download Ollama: {e}")
        return False

    print("Running Ollama installer...")
    print("Please complete the installation manually, then press Enter to continue...")
    input()

    # Clean up installer
    if os.path.exists(installer_path):
        os.remove(installer_path)

    return True

def install_ollama_linux():
    """Install Ollama on Linux."""
    print("Installing Ollama on Linux...")

    # Install using the official script
    success, _, error = run_command(["curl", "-fsSL", "https://ollama.ai/install.sh", "|", "sh"], shell=True)
    if not success:
        print(f"Failed to install Ollama: {error}")
        return False

    return True

def install_ollama_macos():
    """Install Ollama on macOS."""
    print("Installing Ollama on macOS...")

    # Use Homebrew to install Ollama
    success, _, error = run_command(["brew", "install", "ollama"])
    if not success:
        print(f"Failed to install Ollama: {error}")
        return False

    return True

def install_ollama():
    """Install Ollama based on the platform."""
    system = platform.system().lower()

    if system == "windows":
        return install_ollama_windows()
    elif system == "linux":
        return install_ollama_linux()
    elif system == "darwin":
        return install_ollama_macos()
    else:
        print(f"Unsupported platform: {system}")
        return False

def start_ollama_service():
    """Start the Ollama service."""
    print("Starting Ollama service...")

    # Start Ollama in the background
    if platform.system().lower() == "windows":
        success, _, error = run_command(["start", "ollama", "serve"], shell=True)
    else:
        success, _, error = run_command(["ollama", "serve"], shell=False)

    if not success:
        print(f"Failed to start Ollama service: {error}")
        return False

    # Wait for Ollama to be ready
    print("Waiting for Ollama to start...")
    time.sleep(5)

    return True

def pull_llama_model():
    """Pull the Llama 3.1 model."""
    print("Pulling Llama 3.1 model...")

    success, _, error = run_command(["ollama", "pull", "llama3.1"])
    if not success:
        print(f"Failed to pull Llama 3.1 model: {error}")
        return False

    print("Llama 3.1 model downloaded successfully!")
    return True

def test_ollama_connection():
    """Test connection to Ollama."""
    print("Testing Ollama connection...")

    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/tags",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [model["name"] for model in data.get("models", [])]
            if "llama3.1" in models:
                print("✅ Ollama is running and Llama 3.1 is available!")
                return True
            else:
                print(f"❌ Llama 3.1 not found in available models: {models}")
                return False
    except Exception as e:
        print(f"❌ Failed to connect to Ollama: {e}")
        return False

def create_env_file():
    """Create or update .env file with Ollama configuration."""
    env_file = ".env"
    env_content = ""

    # Read existing .env file if it exists
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            env_content = f.read()

    # Update or add Ollama settings
    lines = env_content.split("\n")
    updated_lines = []
    ollama_settings = {
        "USE_OLLAMA": "true",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "OLLAMA_MODEL": "llama3.1",
        "OLLAMA_TIMEOUT": "120"
    }

    for line in lines:
        key = line.split("=")[0] if "=" in line else ""
        if key in ollama_settings:
            updated_lines.append(f"{key}={ollama_settings[key]}")
            del ollama_settings[key]
        else:
            updated_lines.append(line)

    # Add any remaining Ollama settings
    for key, value in ollama_settings.items():
        updated_lines.append(f"{key}={value}")

    # Write back to .env file
    with open(env_file, "w") as f:
        f.write("\n".join(updated_lines))

    print("✅ Updated .env file with Ollama configuration!")

def main():
    """Main setup function."""
    print("🚀 GraphRAG Learning Platform - Ollama Setup")
    print("=" * 50)

    # Check if Ollama is already installed
    if check_ollama_installed():
        print("✅ Ollama is already installed!")
    else:
        print("❌ Ollama is not installed.")
        if not install_ollama():
            print("❌ Failed to install Ollama. Please install it manually from https://ollama.ai")
            sys.exit(1)

    # Start Ollama service
    if not start_ollama_service():
        print("❌ Failed to start Ollama service.")
        sys.exit(1)

    # Test connection
    if not test_ollama_connection():
        print("❌ Ollama connection test failed.")
        sys.exit(1)

    # Pull Llama 3.1 model
    if not pull_llama_model():
        print("❌ Failed to pull Llama 3.1 model.")
        sys.exit(1)

    # Update environment configuration
    create_env_file()

    print("\n🎉 Ollama setup complete!")
    print("You can now run the GraphRAG application with Ollama + Llama 3.1")
    print("\nTo start the application:")
    print("1. Make sure Ollama is running: ollama serve")
    print("2. Start the backend: python -m uvicorn app.api.server:app --reload --host 0.0.0.0 --port 8001")
    print("3. Start the frontend: npm run dev")

if __name__ == "__main__":
    main()