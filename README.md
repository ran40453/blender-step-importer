# Blender STEP AP214 匯入器

使用 Open CASCADE (OCC) 進行真正的 B-Rep 幾何細分，在 Blender 中高品質匯入 STEP AP214/203 檔案。

## 功能特色

- ✅ 透過 Open CASCADE 進行真正的 B-Rep 細分——圓柱、曲線、複雜曲面都能正確渲染
- ✅ 保留 STEP XCAF 中的顏色資訊
- ✅ Part 結構對應 Blender Collection 階層
- ✅ 可調整細分品質（線性偏差 + 角度偏差）
- ✅ 跨平台支援：macOS / Windows / Linux
- ✅ 支援 Blender 3.x ~ 4.x（自動偵測 Python 版本）
- ✅ 已測試：SolidWorks / Creo / CATIA 輸出檔案

## 前置需求

需要將 `cadquery`（Open CASCADE）安裝到 Blender 的 Python 環境中。

### 方式 A — 自動安裝腳本（建議）

```bash
python3 install_dependencies.py
```

腳本會自動找到電腦上所有 Blender 安裝位置，並安裝到對應的 Python 環境。Windows 使用者可直接雙擊執行。

### 方式 B — 手動安裝

找到你的 Blender Python 路徑後執行：

| 作業系統 | 指令範例 |
|---------|---------|
| macOS | `/Applications/Blender.app/Contents/Resources/4.3/python/bin/python3.11 -m pip install cadquery` |
| Windows | `"C:\Program Files\Blender Foundation\Blender 4.3\4.3\python\bin\python.exe" -m pip install cadquery` |
| Linux | `/usr/share/blender/4.3/python/bin/python3.11 -m pip install cadquery` |

> 請依照你的 Blender 版本調整路徑中的版本號。

## 安裝步驟

1. 下載 `import_step_ap214.py`
2. 開啟 Blender：**Edit > Preferences > Add-ons > Install** → 選擇檔案 → 啟用
3. 透過 **File > Import > STEP AP214 (.step/.stp)** 匯入

## 使用說明

| 參數 | 預設值 | 說明 |
|------|--------|------|
| 縮放比例 | `0.001` | mm → m 換算（SolidWorks/CATIA 預設單位為 mm） |
| 線性精度 | `0.05` mm | 數值越小 mesh 越細緻，匯入越慢 |
| 角度精度 | `0.3` rad | 數值越小曲面越圓滑 |

**高品質渲染：** 線性 `0.02`，角度 `0.1`
**快速預覽：** 線性 `0.1`，角度 `0.5`

## 運作原理

使用 `cadquery-ocp`（Open CASCADE Python 綁定）：

1. 透過 XCAF 讀取 STEP——保留顏色與 Part 名稱
2. 以 `BRepMesh_IncrementalMesh` 對 B-Rep 幾何進行細分
3. 建立 Blender mesh 物件，包含正確的面法線、材質與 Collection 階層

相較於純 Python 的 STEP 解析器（只能以多邊形端點近似曲面），本插件能產生顯著更高品質的結果。

## 相容性

| | 支援範圍 |
|---|---|
| 作業系統 | macOS、Windows、Linux |
| Blender 版本 | 3.x ~ 4.x |
| Python 版本 | 3.10、3.11、3.12 |
| STEP 格式 | AP203、AP214、AP242 |
| CAD 來源 | SolidWorks、Creo、CATIA V5、NX、FreeCAD |

> ⚠️ `cadquery-ocp` 目前沒有 ARM Windows（Surface Pro X 等）的預編譯套件，Intel/AMD Windows 正常運作。

## 已知限制

- 幾何以細分 mesh 輸出（非參數化 B-Rep）——不支援匯出後在 Creo/NX 中編輯特徵
- Assembly 階層會平展為 Blender Collection（尚未支援變換實例）
- B-Spline 曲面可精確細分，但不會開放控制點
