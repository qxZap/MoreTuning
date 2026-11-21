# Runs in UnrealEditor-Cmd (-run=pythonscript) in the SoundCook project: imports tongues.fbx as
# /Game/ECUTuning/Flames/SM_QX_Tongue_0..5 (no collision, no lightmap) and builds M_QX_Flame, the flame material:
# additive, unlit, two-sided; colour runs Color (at the pipe, UV v 0) to Color x TipTint (v 1), dimmed at the tip and at
# the silhouette (a soft edge), times Intensity and Opacity. The plugin drives Color and Opacity through a dynamic instance.
import os, unreal

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = "/Game/ECUTuning/Flames"
tools = unreal.AssetToolsHelpers.get_asset_tools()
lib = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary

# ---- meshes
opts = unreal.FbxImportUI()
opts.set_editor_property("import_mesh", True)
opts.set_editor_property("import_materials", False)
opts.set_editor_property("import_textures", False)
opts.set_editor_property("import_as_skeletal", False)
opts.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
sm = opts.static_mesh_import_data
sm.set_editor_property("combine_meshes", False)
sm.set_editor_property("auto_generate_collision", False)
sm.set_editor_property("generate_lightmap_u_vs", False)
task = unreal.AssetImportTask()
task.set_editor_property("filename", os.path.join(HERE, "tongues.fbx"))
task.set_editor_property("destination_path", DEST)
task.set_editor_property("replace_existing", True)
task.set_editor_property("automated", True)
task.set_editor_property("save", True)
task.set_editor_property("options", opts)
tools.import_asset_tasks([task])

# ---- material
path = DEST + "/M_QX_Flame"
if lib.does_asset_exist(path):
    lib.delete_asset(path)
m = tools.create_asset("M_QX_Flame", DEST, unreal.Material, unreal.MaterialFactoryNew())
m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
m.set_editor_property("two_sided", True)
m.set_editor_property("used_with_static_lighting", False)


def node(cls, x, y):
    return mel.create_material_expression(m, cls, x, y)


def vparam(name, rgb, x, y):
    p = node(unreal.MaterialExpressionVectorParameter, x, y)
    p.set_editor_property("parameter_name", name)
    p.set_editor_property("default_value", unreal.LinearColor(*rgb, 1))
    return p


def sparam(name, v, x, y):
    p = node(unreal.MaterialExpressionScalarParameter, x, y)
    p.set_editor_property("parameter_name", name)
    p.set_editor_property("default_value", v)
    return p


uv = node(unreal.MaterialExpressionTextureCoordinate, -1400, 0)
v = node(unreal.MaterialExpressionComponentMask, -1200, 0)
v.set_editor_property("r", False); v.set_editor_property("g", True)
mel.connect_material_expressions(uv, "", v, "")
# the plugin paints "Color" and "Opacity" as it does M_GhostCar's; the tip is that colour reddened
core = vparam("Color", (1.0, 0.6, 0.2), -1000, -300)
tint = vparam("TipTint", (1.0, 0.4, 0.12), -1300, -100)
tip = node(unreal.MaterialExpressionMultiply, -1000, -100)
mel.connect_material_expressions(core, "", tip, "A")
mel.connect_material_expressions(tint, "", tip, "B")
lerp = node(unreal.MaterialExpressionLinearInterpolate, -700, -200)
mel.connect_material_expressions(core, "", lerp, "A")
mel.connect_material_expressions(tip, "", lerp, "B")
mel.connect_material_expressions(v, "", lerp, "Alpha")
# fade toward the tip: (1 - v) ^ 1.3
one_minus = node(unreal.MaterialExpressionOneMinus, -1000, 150)
mel.connect_material_expressions(v, "", one_minus, "")
power = node(unreal.MaterialExpressionPower, -800, 150)
power.set_editor_property("const_exponent", 1.3)
mel.connect_material_expressions(one_minus, "", power, "Base")
# soft silhouette: 1 - fresnel
fres = node(unreal.MaterialExpressionFresnel, -1000, 350)
fres.set_editor_property("exponent", 2.5)
edge = node(unreal.MaterialExpressionOneMinus, -800, 350)
mel.connect_material_expressions(fres, "", edge, "")
intensity = sparam("Intensity", 1.0, -800, 550)
alpha = sparam("Opacity", 1.0, -800, 700)
m1 = node(unreal.MaterialExpressionMultiply, -500, 0)
mel.connect_material_expressions(lerp, "", m1, "A")
mel.connect_material_expressions(power, "", m1, "B")
m2 = node(unreal.MaterialExpressionMultiply, -350, 100)
mel.connect_material_expressions(m1, "", m2, "A")
mel.connect_material_expressions(edge, "", m2, "B")
m3 = node(unreal.MaterialExpressionMultiply, -200, 200)
mel.connect_material_expressions(intensity, "", m3, "A")
mel.connect_material_expressions(alpha, "", m3, "B")
m4 = node(unreal.MaterialExpressionMultiply, -50, 100)
mel.connect_material_expressions(m2, "", m4, "A")
mel.connect_material_expressions(m3, "", m4, "B")
mel.connect_material_property(m4, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
mel.recompile_material(m)
lib.save_loaded_asset(m, only_if_is_dirty=False)

for n in range(6):
    mesh = lib.load_asset(f"{DEST}/SM_QX_Tongue_{n}")
    if not mesh:
        raise RuntimeError(f"SM_QX_Tongue_{n} did not import")
    mesh.set_material(0, m)
    b = mesh.get_bounding_box()
    print(f"SM_QX_Tongue_{n}: bounds min {b.min} max {b.max}")
    lib.save_loaded_asset(mesh, only_if_is_dirty=False)
print("flames imported")
