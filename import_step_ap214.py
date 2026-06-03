"""
STEP AP214 Importer for Blender  v4.0 (OCC)
=============================================
使用 Open CASCADE (cadquery-ocp) 做真正的 B-Rep tessellation。
支援精確曲面：CYLINDRICAL_SURFACE、B_SPLINE、TORUS、CONE 等。

前置需求（已在 Blender Python 安裝）：
  /Applications/Blender.app/Contents/Resources/4.3/python/bin/python3.11 -m pip install cadquery

安裝 addon：Edit > Preferences > Add-ons > Install > 啟用
匯入：File > Import > STEP AP214 OCC (.step, .stp)
"""

bl_info = {
    "name": "STEP AP214 Importer",
    "author": "Cody",
    "version": (4, 0, 0),
    "blender": (3, 0, 0),
    "location": "File > Import > STEP AP214 (.step/.stp)",
    "description": "Import STEP AP214/203 using Open CASCADE tessellation",
    "category": "Import-Export",
}

import sys
import os
import platform
import subprocess

def _inject_user_site():
    """
    自動偵測平台和 Python 版本，把 cadquery-ocp 的安裝路徑加進 sys.path。
    支援 macOS / Windows / Linux，Blender 3.x ~ 4.x。
    """
    ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    system = platform.system()

    candidates = []

    if system == 'Darwin':  # macOS
        candidates = [
            os.path.expanduser(f'~/.local/lib/python{ver}/site-packages'),
            f'/usr/local/lib/python{ver}/site-packages',
            f'/opt/homebrew/lib/python{ver}/site-packages',
        ]
    elif system == 'Windows':
        appdata = os.environ.get('APPDATA', '')
        localappdata = os.environ.get('LOCALAPPDATA', '')
        candidates = [
            os.path.join(localappdata, f'Programs\\Python\\Python{ver.replace(".", "")}\\Lib\\site-packages'),
            os.path.join(appdata, f'Python\\Python{ver.replace(".", "")}\\site-packages'),
            os.path.join(os.path.expanduser('~'), f'AppData\\Roaming\\Python\\Python{ver.replace(".", "")}\\site-packages'),
        ]
    else:  # Linux
        candidates = [
            os.path.expanduser(f'~/.local/lib/python{ver}/site-packages'),
            f'/usr/local/lib/python{ver}/site-packages',
            f'/usr/lib/python{ver}/site-packages',
        ]

    # 也嘗試用 pip 直接查詢 site-packages 路徑
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'site', '--user-site'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            user_site = result.stdout.strip()
            if user_site and user_site not in candidates:
                candidates.insert(0, user_site)
    except Exception:
        pass

    for path in candidates:
        if path and os.path.isdir(path) and path not in sys.path:
            sys.path.append(path)

_inject_user_site()

import bpy
import bmesh
from bpy.props import StringProperty, FloatProperty, IntProperty
from bpy_extras.io_utils import ImportHelper


# ─────────────────────────────────────────────
#  OCC tessellation core
# ─────────────────────────────────────────────

def _occ_available():
    try:
        from OCP.STEPCAFControl import STEPCAFControl_Reader
        return True
    except ImportError:
        return False


def tessellate_step(filepath: str, linear_deflection: float = 0.05,
                    angular_deflection: float = 0.3) -> list:
    """
    用 OCC 讀取 STEP，tessellate 所有 shape，回傳：
    [
      {
        'name': str,
        'verts': [(x,y,z), ...],
        'tris':  [(i,j,k), ...],
        'color': (r,g,b) or None,
      },
      ...
    ]
    linear_deflection:  越小越細，單位 mm，建議 0.01~0.1
    angular_deflection: 越小越細，單位 rad，建議 0.1~0.5
    """
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFApp import XCAFApp_Application
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.XCAFDoc import XCAFDoc_DocumentTool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_FACE
    from OCP.BRep import BRep_Tool
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS_Face
    from OCP.TDF import TDF_LabelSequence
    from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB
    from OCP.XCAFDoc import XCAFDoc_Color
    from OCP.TDF import TDF_Attribute

    # ── 讀 STEP with XCAF（保留顏色 + 名稱）──
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.NewDocument(TCollection_ExtendedString("XmlXCAF"), doc)

    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    reader.SetLayerMode(True)
    status = reader.ReadFile(filepath)
    if str(status) != 'IFSelect_ReturnStatus.IFSelect_RetDone':
        raise ValueError(f"STEP 讀取失敗: {status}")

    reader.Transfer(doc)

    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    color_tool = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    # ── 取得所有 free shapes（top-level parts）──
    labels = TDF_LabelSequence()
    shape_tool.GetFreeShapes(labels)
    print(f"[STEP] OCC free shapes: {labels.Size()}")

    results = []

    def get_color(label):
        """從 label 取顏色，回傳 (r,g,b) 或 None。"""
        from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB
        from OCP.XCAFDoc import XCAFDoc_ColorType
        color = Quantity_Color()
        # 嘗試 surface color → curve color → generic color
        for ctype in [XCAFDoc_ColorType.XCAFDoc_ColorSurf,
                      XCAFDoc_ColorType.XCAFDoc_ColorCurv,
                      XCAFDoc_ColorType.XCAFDoc_ColorGen]:
            if color_tool.GetColor_s(label, ctype, color):
                return (color.Red(), color.Green(), color.Blue())
        return None

    def process_label(label, depth=0):
        """遞迴處理 label，每個 simple shape 建立一個 mesh。"""
        name_attr = label.EntryDumpToString() if label.IsNull() else ""
        # 取 part 名稱
        from OCP.TDataStd import TDataStd_Name
        name_handle = TDataStd_Name()
        try:
            if label.FindAttribute(TDataStd_Name.GetID_s(), name_handle):
                name = name_handle.Get().ToExtString()
            else:
                name = f"Part_{label.Tag()}"
        except Exception:
            name = f"Part_{label.Tag()}"

        shape = shape_tool.GetShape_s(label)
        if shape.IsNull():
            return

        color = get_color(label)

        # 如果是 assembly，遞迴處理 components
        if shape_tool.IsAssembly_s(label):
            components = TDF_LabelSequence()
            shape_tool.GetComponents_s(label, components, False)
            for i in range(1, components.Size() + 1):
                comp_label = components.Value(i)
                # GetReferredShape 需要兩個參數（新版 OCP API）
                try:
                    from OCP.TDF import TDF_Label
                    referred_label = TDF_Label()
                    ok = shape_tool.GetReferredShape_s(comp_label, referred_label)
                    target_label = referred_label if ok and not referred_label.IsNull() else comp_label
                except Exception:
                    target_label = comp_label
                process_label(target_label, depth + 1)
            return

        # ── Tessellate ──
        mesh = BRepMesh_IncrementalMesh(shape, linear_deflection, False, angular_deflection)
        mesh.Perform()

        all_verts = []
        all_tris = []

        exp = TopExp_Explorer(shape, TopAbs_FACE)
        while exp.More():
            raw = exp.Current()
            # 正確 cast TopoDS_Shape → TopoDS_Face
            face = TopoDS_Face()
            face.TShape(raw.TShape())
            face.Location(raw.Location())
            face.Orientation(raw.Orientation())

            loc = TopLoc_Location()
            tri = BRep_Tool.Triangulation_s(face, loc)
            if tri is not None:
                base = len(all_verts)
                trsf = loc.IsIdentity()

                # 取 face color（優先於 shape color）
                face_color = None
                try:
                    fc = Quantity_Color()
                    if color_tool.GetColor_s(raw, XCAFDoc_ColorType.XCAFDoc_ColorSurf, fc):
                        face_color = (fc.Red(), fc.Green(), fc.Blue())
                except Exception:
                    pass

                for i in range(1, tri.NbNodes() + 1):
                    n = tri.Node(i)
                    if not loc.IsIdentity():
                        n.Transform(loc.IsIdentity())
                    all_verts.append((n.X(), n.Y(), n.Z()))

                # 處理 face orientation（決定三角形 winding）
                is_reversed = (raw.Orientation() == 1)  # TopAbs_REVERSED = 1
                for i in range(1, tri.NbTriangles() + 1):
                    t = tri.Triangle(i)
                    n1, n2, n3 = t.Get()
                    if is_reversed:
                        all_tris.append((base + n1 - 1, base + n3 - 1, base + n2 - 1))
                    else:
                        all_tris.append((base + n1 - 1, base + n2 - 1, base + n3 - 1))

            exp.Next()

        if all_verts and all_tris:
            results.append({
                'name': name,
                'verts': all_verts,
                'tris': all_tris,
                'color': color,
            })
            print(f"[STEP]   '{name}': {len(all_verts)} verts, {len(all_tris)} tris")

    for i in range(1, labels.Size() + 1):
        process_label(labels.Value(i))

    # ── Fallback：如果 XCAF 沒有拿到 shape，直接用 STEPControl ──
    if not results:
        print("[STEP] XCAF 無結果，fallback STEPControl…")
        from OCP.STEPControl import STEPControl_Reader as SCR
        from OCP.IFSelect import IFSelect_ReturnStatus
        r = SCR()
        r.ReadFile(filepath)
        r.TransferRoots()
        shape = r.OneShape()

        mesh = BRepMesh_IncrementalMesh(shape, linear_deflection, False, angular_deflection)
        mesh.Perform()

        all_verts = []; all_tris = []
        exp = TopExp_Explorer(shape, TopAbs_FACE)
        while exp.More():
            raw = exp.Current()
            face = TopoDS_Face()
            face.TShape(raw.TShape())
            face.Location(raw.Location())
            face.Orientation(raw.Orientation())
            loc = TopLoc_Location()
            tri = BRep_Tool.Triangulation_s(face, loc)
            if tri is not None:
                base = len(all_verts)
                for i in range(1, tri.NbNodes() + 1):
                    n = tri.Node(i)
                    all_verts.append((n.X(), n.Y(), n.Z()))
                is_rev = (raw.Orientation() == 1)
                for i in range(1, tri.NbTriangles() + 1):
                    t = tri.Triangle(i)
                    n1, n2, n3 = t.Get()
                    if is_rev:
                        all_tris.append((base+n1-1, base+n3-1, base+n2-1))
                    else:
                        all_tris.append((base+n1-1, base+n2-1, base+n3-1))
            exp.Next()

        fname = os.path.splitext(os.path.basename(filepath))[0]
        if all_verts:
            results.append({'name': fname, 'verts': all_verts, 'tris': all_tris, 'color': None})
            print(f"[STEP] Fallback: {len(all_verts)} verts, {len(all_tris)} tris")

    return results


# ─────────────────────────────────────────────
#  Blender mesh builder
# ─────────────────────────────────────────────

def make_material(name: str, color: tuple):
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (*color, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.35
        bsdf.inputs['Metallic'].default_value = 0.15
    return mat


def build_mesh_obj(name: str, verts: list, tris: list,
                   color: tuple | None, scale: float):
    mesh = bpy.data.meshes.new(name[:63])
    obj = bpy.data.objects.new(name[:63], mesh)

    scaled = [(x * scale, y * scale, z * scale) for x, y, z in verts]

    bm = bmesh.new()
    try:
        bm_verts = [bm.verts.new(v) for v in scaled]
        bm.verts.ensure_lookup_table()
        for tri in tris:
            try:
                bm.faces.new([bm_verts[i] for i in tri])
            except Exception:
                pass
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-8)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(mesh)
    finally:
        bm.free()
    mesh.update()

    if color:
        r, g, b = color
        mat_name = f"M_{int(r*255):02X}{int(g*255):02X}{int(b*255):02X}"
        mat = make_material(mat_name, color)
        obj.data.materials.append(mat)

    return obj


# ─────────────────────────────────────────────
#  Main import
# ─────────────────────────────────────────────

def import_step(filepath: str, scale: float = 0.001,
                linear_deflection: float = 0.05,
                angular_deflection: float = 0.3):

    if not _occ_available():
        raise RuntimeError(
            "找不到 OCP (cadquery-ocp)。請先執行：\n"
            "/Applications/Blender.app/Contents/Resources/4.3/python/bin/python3.11 "
            "-m pip install cadquery"
        )

    # 清除 orphan mesh objects
    for obj in list(bpy.data.objects):
        if obj.type == 'MESH' and not obj.users_collection:
            bpy.data.objects.remove(obj, do_unlink=True)

    fname = os.path.splitext(os.path.basename(filepath))[0]
    root_col = bpy.data.collections.new(fname)
    bpy.context.scene.collection.children.link(root_col)
    print(f"[STEP] root_col='{root_col.name}'")

    print(f"[STEP] Tessellating: linear={linear_deflection}mm angular={angular_deflection}rad")
    shapes = tessellate_step(filepath, linear_deflection, angular_deflection)
    print(f"[STEP] Got {len(shapes)} shapes")

    created = []
    for s in shapes:
        obj = build_mesh_obj(s['name'], s['verts'], s['tris'], s['color'], scale)
        root_col.objects.link(obj)
        created.append(obj)
        print(f"[STEP] Linked '{obj.name}' → '{root_col.name}'")

    bpy.context.view_layer.update()
    for o in created:
        try:
            o.select_set(True)
        except Exception:
            pass
    if created:
        bpy.context.view_layer.objects.active = created[0]

    print(f"[STEP] 完成：{len(created)} 物件")
    return {'FINISHED'}


# ─────────────────────────────────────────────
#  Operator
# ─────────────────────────────────────────────

class IMPORT_OT_step_ap214(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.step_ap214"
    bl_label = "Import STEP AP214"
    bl_options = {'PRESET'}

    filter_glob: StringProperty(default="*.step;*.stp;*.STEP;*.STP", options={'HIDDEN'})

    scale: FloatProperty(
        name="縮放比例",
        description="0.001 = mm→m（SolidWorks/CATIA 預設 mm）",
        default=0.001, min=1e-6, max=1000.0, step=0.1, precision=6,
    )
    linear_deflection: FloatProperty(
        name="線性精度 (mm)",
        description="越小 mesh 越細緻，越慢。建議 0.01~0.1",
        default=0.05, min=0.001, max=1.0, step=0.01, precision=3,
    )
    angular_deflection: FloatProperty(
        name="角度精度 (rad)",
        description="越小曲面越圓滑。建議 0.1~0.5",
        default=0.3, min=0.01, max=1.0, step=0.05, precision=2,
    )

    def execute(self, context):
        try:
            return import_step(
                self.filepath,
                scale=self.scale,
                linear_deflection=self.linear_deflection,
                angular_deflection=self.angular_deflection,
            )
        except Exception as e:
            self.report({'ERROR'}, f"STEP import error: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'scale')
        layout.separator()
        layout.label(text="Tessellation 精度（影響 mesh 品質）")
        layout.prop(self, 'linear_deflection')
        layout.prop(self, 'angular_deflection')


def menu_func_import(self, context):
    self.layout.operator(IMPORT_OT_step_ap214.bl_idname, text="STEP AP214 (.step/.stp)")


# ─────────────────────────────────────────────
#  Export: Blender mesh → B-Rep STEP
# ─────────────────────────────────────────────

def export_step(filepath: str, objects: list, scale: float = 1000.0):
    """
    把選取的 Blender mesh objects 轉成 B-Rep shell 輸出為 STEP。
    scale: Blender 單位 → mm（預設 1m = 1000mm）
    每個 polygon face → ADVANCED_FACE (PLANE)
    縫合成 SHELL → 輸出為完整 B-Rep STEP。
    """
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_MakePolygon,
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_Sewing,
        BRepBuilderAPI_MakeSolid,
    )
    from OCP.gp import gp_Pnt
    from OCP.TopoDS import TopoDS_Compound
    from OCP.BRep import BRep_Builder
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.STEPControl import STEPControl_AsIs
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFApp import XCAFApp_Application
    from OCP.XCAFDoc import XCAFDoc_DocumentTool
    from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB
    from OCP.TDF import TDF_LabelSequence
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.NewDocument(TCollection_ExtendedString("XmlXCAF"), doc)
    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    color_tool = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    total_objects = 0
    total_faces = 0
    sew_tol = 1e-4  # mm 單位下的縫合容差

    for obj in objects:
        if obj.type != 'MESH':
            continue

        # 取得帶 modifier 的 evaluated mesh
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = obj.evaluated_get(depsgraph)
        mesh = eval_obj.to_mesh()

        if not mesh or not mesh.polygons:
            continue

        face_count_raw = len(mesh.polygons)
        if face_count_raw > 5000:
            print(f"[STEP] ⚠ '{obj.name}' 有 {face_count_raw} 個面，B-Rep 縫合會很慢。")
            print(f"[STEP]   建議先在 Blender 做 Decimate（減少到 1000 面以下）再 export。")
            eval_obj.to_mesh_clear()
            raise ValueError(
                f"'{obj.name}' 面數過多（{face_count_raw} faces）。\n"
                f"建議先加 Decimate modifier 減少面數再 export。\n"
                f"Import 進來的 STP mesh 不適合用此方式 export。"
            )

        # 三角化（確保所有面都是三角形或四邊形，方便 BRepBuilderAPI 處理）
        import bmesh as _bmesh
        bm = _bmesh.new()
        bm.from_mesh(mesh)
        _bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()

        # 物件的世界矩陣（包含位移、旋轉、縮放）
        world_matrix = obj.matrix_world

        sewing = BRepBuilderAPI_Sewing(sew_tol)
        obj_face_count = 0

        for poly in mesh.polygons:
            verts_world = [world_matrix @ mesh.vertices[vi].co for vi in poly.vertices]

            poly_builder = BRepBuilderAPI_MakePolygon()
            for v in verts_world:
                poly_builder.Add(gp_Pnt(
                    v.x * scale,
                    v.y * scale,
                    v.z * scale,
                ))
            poly_builder.Close()

            if not poly_builder.IsDone():
                continue

            wire = poly_builder.Wire()
            face_builder = BRepBuilderAPI_MakeFace(wire, True)
            if face_builder.IsDone():
                sewing.Add(face_builder.Face())
                obj_face_count += 1

        if obj_face_count == 0:
            eval_obj.to_mesh_clear()
            continue

        sewing.Perform()
        shape = sewing.SewedShape()

        # 嘗試升級成 Solid（若 shell 是封閉的）
        try:
            solid_builder = BRepBuilderAPI_MakeSolid()
            from OCP.TopoDS import TopoDS_Shell
            from OCP.TopExp import TopExp_Explorer
            from OCP.TopAbs import TopAbs_SHELL
            exp = TopExp_Explorer(shape, TopAbs_SHELL)
            has_shell = False
            while exp.More():
                from OCP.TopoDS import TopoDS_Shell as _Shell
                shell = exp.Current()
                solid_builder.Add(shell)
                has_shell = True
                exp.Next()
            if has_shell and solid_builder.IsDone():
                shape = solid_builder.Solid()
                print(f"[STEP] '{obj.name}': {obj_face_count} faces → SOLID")
            else:
                print(f"[STEP] '{obj.name}': {obj_face_count} faces → SHELL (open)")
        except Exception:
            print(f"[STEP] '{obj.name}': {obj_face_count} faces → SHELL")

        # 加入 XCAF（帶名稱）
        label = shape_tool.AddShape(shape)
        from OCP.TDataStd import TDataStd_Name
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(obj.name))

        # 顏色（取第一個材質的 Base Color）
        if obj.data.materials:
            mat = obj.data.materials[0]
            if mat and mat.use_nodes:
                bsdf = mat.node_tree.nodes.get('Principled BSDF')
                if bsdf:
                    try:
                        c = bsdf.inputs['Base Color'].default_value
                        occ_color = Quantity_Color(c[0], c[1], c[2], Quantity_TOC_RGB)
                        from OCP.XCAFDoc import XCAFDoc_ColorType
                        color_tool.SetColor(label, occ_color, XCAFDoc_ColorType.XCAFDoc_ColorGen)
                    except Exception as e:
                        print(f"[STEP] 顏色設定失敗（略過）: {e}")

        total_faces += obj_face_count
        total_objects += 1
        eval_obj.to_mesh_clear()

    if total_objects == 0:
        raise ValueError("沒有可匯出的 Mesh 物件，請先選取至少一個 Mesh。")

    # 寫出 STEP
    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    writer.Transfer(doc)
    status = writer.Write(filepath)

    print(f"[STEP] Export: {total_objects} 物件, {total_faces} faces → {filepath}")
    print(f"[STEP] Write status: {status}")

    if 'RetDone' not in str(status):
        raise RuntimeError(f"STEP 寫出失敗: {status}")

    return total_objects, total_faces


class EXPORT_OT_step_ap214(bpy.types.Operator):
    """Export selected mesh objects to STEP AP214 (B-Rep shell)"""
    bl_idname = "export_scene.step_ap214"
    bl_label = "Export STEP AP214"
    bl_options = {'PRESET'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.step;*.stp", options={'HIDDEN'})

    scale: FloatProperty(
        name="縮放比例",
        description="Blender 單位 → mm（預設 1m = 1000mm）",
        default=1000.0, min=0.001, max=100000.0, precision=3,
    )
    selected_only: bpy.props.BoolProperty(
        name="僅匯出選取物件",
        description="關閉則匯出場景中所有 Mesh",
        default=True,
    )

    def invoke(self, context, event):
        # 預設檔名
        blend_name = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
        self.filepath = (blend_name or "export") + ".step"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if not _occ_available():
            self.report({'ERROR'},
                "找不到 OCP。請先執行 install_dependencies.py 安裝 cadquery。")
            return {'CANCELLED'}

        if self.selected_only:
            objects = [o for o in context.selected_objects if o.type == 'MESH']
        else:
            objects = [o for o in context.scene.objects if o.type == 'MESH']

        if not objects:
            self.report({'WARNING'}, "沒有選取任何 Mesh 物件。")
            return {'CANCELLED'}

        try:
            n_obj, n_faces = export_step(self.filepath, objects, scale=self.scale)
            self.report({'INFO'}, f"✅ 匯出完成：{n_obj} 物件，{n_faces} faces → {self.filepath}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"STEP export 失敗：{e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'scale')
        layout.prop(self, 'selected_only')
        layout.separator()
        layout.label(text="注意：圓柱/圓弧會輸出為多邊形近似")
        layout.label(text="平面幾何可在 Creo/NX 選面、量尺寸、拉伸")


def menu_func_export(self, context):
    self.layout.operator(EXPORT_OT_step_ap214.bl_idname, text="STEP AP214 (.step/.stp)")


def register():
    bpy.utils.register_class(IMPORT_OT_step_ap214)
    bpy.utils.register_class(EXPORT_OT_step_ap214)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(IMPORT_OT_step_ap214)
    bpy.utils.unregister_class(EXPORT_OT_step_ap214)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()

