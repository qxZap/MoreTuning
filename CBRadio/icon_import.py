# Runs inside UnrealEditor-Cmd (-run=pythonscript) in the SoundCook project: imports CBRadio/Ham_Radio.png as the
# item icon /Game/UI/Icons/CBRadio/Ham_Radio, set up like the game's own item icons (UI/Icons/Item/Radio: 512 px,
# DXT5 with alpha, no mips, UI group). CBRadio/build.py copies the cooked texture into qxZap_CBRadio_P.
import os, unreal

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Ham_Radio.png")
DEST = "/Game/UI/Icons/CBRadio"

task = unreal.AssetImportTask()
task.set_editor_property("filename", SRC)
task.set_editor_property("destination_path", DEST)
task.set_editor_property("destination_name", "Ham_Radio")
task.set_editor_property("replace_existing", True)
task.set_editor_property("automated", True)
task.set_editor_property("save", False)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

tex = unreal.EditorAssetLibrary.load_asset(DEST + "/Ham_Radio")
if not tex:
    raise RuntimeError("Ham_Radio did not import")
tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_DEFAULT)
tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_UI)
tex.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
tex.set_editor_property("never_stream", True)
tex.set_editor_property("srgb", True)
unreal.EditorAssetLibrary.save_loaded_asset(tex, only_if_is_dirty=False)
print("Ham_Radio imported:", tex.blueprint_get_size_x(), "x", tex.blueprint_get_size_y())
