"""Runs in UnrealEditor-Cmd (-run=pythonscript). Builds the stand-in /Game/Characters/Models/Skeletons/SK_MTCharacter:
the first 63 bones from glTF (import order is depth-first, which those are), then Jaw and the *_end bones appended in
the game's order with SkeletonModifier (the game's order is not depth-first: they came later). Writes its reference pose to D:\MT\SwimCook\gltf\standin_pose.json for checking.
The stand-in is never shipped."""
import unreal, json
G = "D:/MT/SwimCook/gltf"
lib = unreal.EditorAssetLibrary
at = unreal.AssetToolsHelpers.get_asset_tools()
for d in ("/Game/StandIn", "/Game/Characters", "/Game/Probe"):
    if lib.does_directory_exist(d): lib.delete_directory(d)

def imp(n, skel=None):
    t = unreal.AssetImportTask(); t.filename = G + "/stage%d.gltf" % n; t.destination_path = "/Game/StandIn"
    t.destination_name = "StandIn%d" % n; t.automated = True; t.save = True; t.replace_existing = True
    if skel:
        p = unreal.InterchangeGenericAssetsPipeline()
        p.common_skeletal_meshes_and_animations_properties.skeleton = skel
        p.mesh_pipeline.create_physics_asset = False
        t.options = p
    at.import_asset_tasks([t])
    print('SWIM imported', n, list(t.imported_object_paths))
    return t

t = imp(63)
skp = [p for p in t.imported_object_paths if 'Skeleton' in p][0]
assert lib.rename_asset(skp.split('.')[0], "/Game/Characters/Models/Skeletons/SK_MTCharacter")
skel = unreal.load_asset("/Game/Characters/Models/Skeletons/SK_MTCharacter")
mesh = unreal.load_asset("/Game/StandIn/StandIn63")
B = json.load(open("D:/MT/MoreTuning/Swim/bones.json"))
mod = unreal.SkeletonModifier(); mod.set_skeletal_mesh(mesh)
for b in B[63:]:
    tr = unreal.Transform(); tr.translation = unreal.Vector(*b['loc']); tr.rotation = unreal.Quat(*b['rot'])
    tr.scale3d = unreal.Vector(*b['scale'])
    assert mod.add_bone(b['name'], B[b['parent']]['name'], tr), b['name']
print('SWIM commit', mod.commit_skeleton_to_skeletal_mesh())
lib.save_asset("/Game/StandIn/StandIn63", only_if_is_dirty=False)
lib.save_asset("/Game/Characters/Models/Skeletons/SK_MTCharacter", only_if_is_dirty=False)
print('SWIM mesh skeleton', mesh.skeleton.get_path_name())
pose = unreal.AnimPoseExtensions.get_reference_pose(skel)
out = []
for n in unreal.AnimPoseExtensions.get_bone_names(pose):
    tr = unreal.AnimPoseExtensions.get_ref_bone_pose(pose, n, unreal.AnimPoseSpaces.LOCAL)
    out.append([str(n), [tr.translation.x, tr.translation.y, tr.translation.z], [tr.rotation.x, tr.rotation.y, tr.rotation.z, tr.rotation.w]])
json.dump(out, open(G + "/standin_pose.json", 'w'))
print('SWIM bones', len(out))
