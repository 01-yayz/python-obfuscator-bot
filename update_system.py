"""
Auto-Update System untuk Python Obfuscator Bot
"""

import os
import json
import urllib.request
from datetime import datetime

class UpdateSystem:
    def __init__(self):
        self.current_version = "1.0.0"
    
    def check_update(self):
        """Cek update dari GitHub"""
        try:
            # URL untuk repository Anda
            owner = "01-yazy"  # Ganti dengan username GitHub Anda
            repo = "python-obfuscator-bot"
            url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
            
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'PythonObfuscatorBot/1.0')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
            
            latest_version = data.get('tag_name', '').lstrip('v')
            
            if self._compare_versions(latest_version, self.current_version) > 0:
                return True, {
                    'version': latest_version,
                    'name': data.get('name', ''),
                    'url': data.get('html_url', '')
                }
            
            return False, {}
            
        except Exception as e:
            print(f"Update check error: {e}")
            return False, {}
    
    def _compare_versions(self, v1: str, v2: str) -> int:
        """Bandingkan versi"""
        if v1 == v2:
            return 0
        
        v1_parts = list(map(int, v1.split('.'))) if v1 else [0, 0, 0]
        v2_parts = list(map(int, v2.split('.'))) if v2 else [0, 0, 0]
        
        for i in range(3):
            if v1_parts[i] > v2_parts[i]:
                return 1
            elif v1_parts[i] < v2_parts[i]:
                return -1
        
        return 0

# Contoh penggunaan
if __name__ == "__main__":
    update = UpdateSystem()
    available, info = update.check_update()
    
    if available:
        print(f"Update available: {info['version']}")
        print(f"Name: {info['name']}")
        print(f"URL: {info['url']}")
    else:
        print("Already up to date!")
