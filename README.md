# Blender STEP AP214 Importer

Blender addon for importing STEP AP214/203 files with full B-Rep quality using Open CASCADE (OCC).

## Features

- ✅ True B-Rep tessellation via Open CASCADE — cylinders, splines, and complex surfaces render correctly
- ✅ Color preservation from STEP XCAF metadata
- ✅ Part structure → Blender Collection hierarchy
- ✅ Adjustable tessellation quality (linear + angular deflection)
- ✅ Cross-platform: macOS / Windows / Linux
- ✅ Blender 3.x ~ 4.x (auto-detects Python version)
- ✅ Tested with SolidWorks / Creo / CATIA output

## Prerequisites

Install `cadquery` (Open CASCADE) into Blender's Python.

### Option A — Auto installer (recommended)

```bash
python3 install_dependencies.py
```

The script automatically finds all Blender installations on your machine and installs the dependency into the correct Python environment. On Windows, double-click the script to run it.

### Option B — Manual

Find your Blender Python and run:

| OS | Path |
|----|------|
| macOS | `/Applications/Blender.app/Contents/Resources/4.3/python/bin/python3.11 -m pip install cadquery` |
| Windows | `"C:\Program Files\Blender Foundation\Blender 4.3\4.3\python\bin\python.exe" -m pip install cadquery` |
| Linux | `/usr/share/blender/4.3/python/bin/python3.11 -m pip install cadquery` |

> Adjust the version number to match your Blender installation.

## Installation

1. Download `import_step_ap214.py`
2. In Blender: **Edit > Preferences > Add-ons > Install** → select the file → enable it
3. Import via **File > Import > STEP AP214 (.step/.stp)**

## Usage

| Parameter | Default | Description |
|-----------|---------|-------------|
| Scale | `0.001` | mm → m conversion (SolidWorks/CATIA default is mm) |
| Linear deflection | `0.05` mm | Smaller = finer mesh, slower import |
| Angular deflection | `0.3` rad | Smaller = smoother curves |

**High quality render:** linear `0.02`, angular `0.1`
**Fast preview:** linear `0.1`, angular `0.5`

## How it works

Uses `cadquery-ocp` (Open CASCADE Python bindings) to:

1. Read STEP via XCAF — preserves color and part name metadata
2. Tessellate B-Rep geometry with `BRepMesh_IncrementalMesh`
3. Build Blender mesh objects with correct face normals, materials, and Collection hierarchy

This produces significantly better results than pure-Python STEP parsers, which can only approximate curved surfaces (cylinders, splines, cones) using polygon endpoints.

## Compatibility

| | Supported |
|---|---|
| OS | macOS, Windows, Linux |
| Blender | 3.x ~ 4.x |
| Python | 3.10, 3.11, 3.12 |
| STEP formats | AP203, AP214, AP242 |
| CAD sources | SolidWorks, Creo, CATIA V5, NX, FreeCAD |

> ⚠️ `cadquery-ocp` does not have a prebuilt wheel for ARM Windows (Surface Pro X etc.). Intel/AMD Windows works normally.

## Known limitations

- Geometry is tessellated (polygon mesh), not parametric B-Rep — editing in Creo/NX after round-trip is not supported
- Assembly hierarchy is flattened into Blender Collections (no transform instances yet)
- B-Spline surfaces are tessellated accurately but control points are not exposed
