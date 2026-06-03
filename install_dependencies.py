# Blender STEP AP214 Importer — Installation Script
# Run this script to install the required dependency into Blender's Python

import subprocess
import sys
import os

def find_blender_python():
    candidates = [
        "/Applications/Blender.app/Contents/Resources/4.3/python/bin/python3.11",
        "/Applications/Blender.app/Contents/Resources/4.2/python/bin/python3.11",
        "/Applications/Blender.app/Contents/Resources/4.1/python/bin/python3.11",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def main():
    py = find_blender_python()
    if not py:
        print("❌ 找不到 Blender Python，請手動執行：")
        print("   <blender_python> -m pip install cadquery")
        sys.exit(1)

    print(f"✅ 找到 Blender Python: {py}")
    print("📦 安裝 cadquery (Open CASCADE)...")
    result = subprocess.run([py, "-m", "pip", "install", "cadquery"], capture_output=False)

    if result.returncode == 0:
        print("\n✅ 安裝成功！")
        print("→ 在 Blender: Edit > Preferences > Add-ons > Install > 選 import_step_ap214.py")
    else:
        print("\n❌ 安裝失敗，請手動執行：")
        print(f"   {py} -m pip install cadquery")

if __name__ == "__main__":
    main()
