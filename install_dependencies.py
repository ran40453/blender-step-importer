"""
install_dependencies.py
自動找到 Blender 的 Python 並安裝 cadquery (Open CASCADE)。
支援 macOS / Windows / Linux，Blender 3.x ~ 4.x。

使用方式：
  python3 install_dependencies.py
  或直接雙擊執行（Windows）
"""

import subprocess
import sys
import os
import glob
import platform

def find_blender_pythons():
    system = platform.system()
    candidates = []

    if system == 'Darwin':  # macOS
        # 搜尋所有 Blender 版本
        for path in glob.glob('/Applications/Blender*.app/Contents/Resources/*/python/bin/python3*'):
            if os.path.isfile(path) and not path.endswith('-config'):
                candidates.append(path)
        # 也檢查 ~/Applications
        for path in glob.glob(os.path.expanduser('~/Applications/Blender*.app/Contents/Resources/*/python/bin/python3*')):
            if os.path.isfile(path) and not path.endswith('-config'):
                candidates.append(path)

    elif system == 'Windows':
        # 常見 Windows 安裝路徑
        drives = ['C:', 'D:']
        for drive in drives:
            for path in glob.glob(f'{drive}\\Program Files\\Blender Foundation\\Blender*\\*\\python\\bin\\python.exe'):
                candidates.append(path)
            for path in glob.glob(f'{drive}\\Program Files\\Blender Foundation\\Blender*\\*\\python\\bin\\python3*.exe'):
                candidates.append(path)
        # Steam 版
        steam = os.path.expanduser('~\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs')
        for path in glob.glob(f'C:\\Program Files (x86)\\Steam\\steamapps\\common\\Blender\\*\\python\\bin\\python*.exe'):
            candidates.append(path)

    else:  # Linux
        for path in glob.glob('/usr/share/blender/*/python/bin/python3*'):
            if os.path.isfile(path) and not path.endswith('-config'):
                candidates.append(path)
        for path in glob.glob(os.path.expanduser('~/blender-*/*/python/bin/python3*')):
            if os.path.isfile(path) and not path.endswith('-config'):
                candidates.append(path)
        # snap
        for path in glob.glob('/snap/blender/*/*/python/bin/python3*'):
            if os.path.isfile(path) and not path.endswith('-config'):
                candidates.append(path)

    # 去重，按版本號排序（優先最新）
    seen = set()
    result = []
    for p in sorted(candidates, reverse=True):
        if p not in seen:
            seen.add(p)
            result.append(p)
    return result


def get_python_version(py_path):
    try:
        out = subprocess.check_output([py_path, '--version'], stderr=subprocess.STDOUT, text=True, timeout=5)
        return out.strip()
    except Exception:
        return '?'


def install_cadquery(py_path):
    print(f"\n📦 安裝 cadquery → {py_path}")
    print(f"   Python: {get_python_version(py_path)}")
    result = subprocess.run(
        [py_path, '-m', 'pip', 'install', 'cadquery', '--upgrade'],
        timeout=300
    )
    return result.returncode == 0


def main():
    print("=" * 60)
    print("Blender STEP Importer — Dependency Installer")
    print("=" * 60)

    pythons = find_blender_pythons()

    if not pythons:
        print("\n❌ 找不到 Blender 的 Python。")
        print("請手動執行：")
        print("  <blender_python_path> -m pip install cadquery")
        print("\n常見路徑：")
        print("  macOS: /Applications/Blender.app/Contents/Resources/4.3/python/bin/python3.11")
        print("  Win:   C:\\Program Files\\Blender Foundation\\Blender 4.3\\4.3\\python\\bin\\python.exe")
        sys.exit(1)

    print(f"\n找到 {len(pythons)} 個 Blender Python：")
    for i, p in enumerate(pythons):
        print(f"  [{i+1}] {p}  ({get_python_version(p)})")

    if len(pythons) == 1:
        choice = 0
    else:
        try:
            choice = int(input("\n選擇要安裝的版本 (Enter = 全部): ").strip() or "0") - 1
        except (ValueError, EOFError):
            choice = -1  # 全部

    targets = pythons if choice < 0 else [pythons[choice]] if 0 <= choice < len(pythons) else pythons

    success_count = 0
    for py in targets:
        if install_cadquery(py):
            print(f"  ✅ 成功")
            success_count += 1
        else:
            print(f"  ❌ 失敗，請手動執行：{py} -m pip install cadquery")

    print(f"\n{'✅ 完成！' if success_count > 0 else '❌ 安裝失敗'} ({success_count}/{len(targets)})")
    if success_count > 0:
        print("→ 重新啟動 Blender 後即可使用 STEP 匯入功能")

    if platform.system() == 'Windows':
        input("\nPress Enter to exit...")


if __name__ == '__main__':
    main()
