# Blender STEP AP214 Importer

Blender addon for importing STEP AP214/203 files with full B-Rep quality using Open CASCADE (OCC).

## Features

- ✅ True B-Rep tessellation via Open CASCADE — cylinders, splines, and complex surfaces render correctly
- ✅ Color preservation from STEP XCAF metadata
- ✅ Part structure → Blender Collection hierarchy
- ✅ Adjustable tessellation quality (linear + angular deflection)
- ✅ Tested with SolidWorks / Creo / CATIA output

## Prerequisites

Install `cadquery` into Blender's Python:

```bash
/Applications/Blender.app/Contents/Resources/4.3/python/bin/python3.11 -m pip install cadquery
```

> ⚠️ macOS only (Blender 4.3, Python 3.11). For other OS/versions, adjust the path accordingly.

## Installation

1. Download `import_step_ap214.py`
2. In Blender: **Edit > Preferences > Add-ons > Install** → select the file → enable it
3. Import via **File > Import > STEP AP214 (.step/.stp)**

## Usage

| Parameter | Default | Description |
|-----------|---------|-------------|
| 縮放比例 (Scale) | `0.001` | mm → m conversion (SolidWorks/CATIA default mm) |
| 線性精度 (Linear deflection) | `0.05` mm | Smaller = finer mesh, slower |
| 角度精度 (Angular deflection) | `0.3` rad | Smaller = smoother curves |

For high-quality renders: set linear `0.02`, angular `0.1`.
For fast preview: set linear `0.1`, angular `0.5`.

## How it works

Uses `cadquery-ocp` (Open CASCADE Python bindings) to:
1. Read STEP via XCAF with color and name metadata
2. Tessellate B-Rep geometry with `BRepMesh_IncrementalMesh`
3. Build Blender mesh objects with correct face normals and materials

## Tested files

- SolidWorks STEP AP214 export
- Creo Parametric STEP AP214 export
- CATIA V5 STEP AP203 export
