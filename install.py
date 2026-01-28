#!/usr/bin/env python3
"""
Installer sederhana untuk Python Obfuscator Bot
"""

import os
import sys
import subprocess

def main():
    print("=" * 50)
    print("Python Obfuscator Bot Installer")
    print("=" * 50)
    
    # Cek Python version
    if sys.version_info < (3, 7):
        print("❌ Python 3.7+ required!")
        sys.exit(1)
    
    print("✅ Python version OK")
    
    # Install dependencies
    print("\n📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed")
    except:
        print("⚠️  Could not install from requirements.txt")
        print("Installing manually...")
        packages = [
            "python-telegram-bot==20.7",
            "cryptography==42.0.0",
            "pycryptodome==3.19.0"
        ]
        for pkg in packages:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
            except:
                print(f"⚠️  Failed to install {pkg}")
    
    # Buat folder
    folders = ["uploads", "outputs", "logs", "backups"]
    for folder in folders:
        os.makedirs(folder, exist_ok=True)
        print(f"📁 Created folder: {folder}")
    
    print("\n" + "=" * 50)
    print("✅ Installation complete!")
    print("\n📋 Next steps:")
    print("1. Edit config.json - add your bot token")
    print("2. Run: python telegram_obfuscator_bot.py")
    print("3. Open Telegram and start your bot")
    print("=" * 50)

if __name__ == "__main__":
    main()
