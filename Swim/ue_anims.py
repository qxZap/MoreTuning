"""Runs in UnrealEditor-Cmd (-run=pythonscript) after ue_skeleton.py: keys D:/MT/SwimCook/keys.json (swim_anim.py
export) into /Game/Swim/Anims/<anim> on the stand-in SK_MTCharacter, with the game's ACL compression settings, and
makes a <anim>_Montage per anim in DefaultSlot (the emotes' slot) whose one section loops onto itself."""
import unreal, json
lib = unreal.EditorAssetLibrary
at = unreal.AssetToolsHelpers.get_asset_tools()
DST = "/Game/Swim/Anims"
skel = unreal.load_asset("/Game/Characters/Models/Skeletons/SK_MTCharacter")
keys = json.load(open("D:/MT/SwimCook/keys.json"))
if lib.does_directory_exist(DST): lib.delete_directory(DST)
bone_acl = unreal.load_asset("/ACLPlugin/ACLAnimBoneCompressionSettings")
curve_acl = unreal.load_asset("/ACLPlugin/ACLAnimCurveCompressionSettings")
print('SWIM acl', bone_acl, curve_acl)
readback = {}
V = lambda v: unreal.Vector(*v)
Q = lambda q: unreal.Quat(*q)
for name, a in keys.items():
    f = unreal.AnimSequenceFactory(); f.set_editor_property('target_skeleton', skel)
    seq = at.create_asset(name, DST, unreal.AnimSequence, f)
    c = seq.controller
    c.open_bracket(unreal.Text("swim keys"))
    c.set_frame_rate(unreal.FrameRate(30, 1))
    c.set_number_of_frames(unreal.FrameNumber(a['frames']))
    c.remove_all_bone_tracks()
    for bone, ks in a['bones'].items():
        c.add_bone_curve(bone)
        ok = c.set_bone_track_keys(bone, [V(k[0]) for k in ks], [Q(k[1]) for k in ks], [V(k[2]) for k in ks])
        assert ok, (name, bone)
    c.close_bracket()
    seq.set_editor_property('bone_compression_settings', bone_acl)
    seq.set_editor_property('curve_compression_settings', curve_acl)
    seq.set_editor_property('enable_root_motion', False)
    lib.save_loaded_asset(seq, only_if_is_dirty=False)
    # read the pose back at a quarter cycle; check.py compares it with swim_anim's own FK
    opt = unreal.AnimPoseEvaluationOptions()
    pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(seq, (a['frames'] // 4) / 30.0, opt)
    back = {}
    for b in ('Pelvis', 'head', 'Hand_L', 'Hand_R', 'Foot_L', 'toes_r'):
        t = unreal.AnimPoseExtensions.get_bone_pose(pose, b, unreal.AnimPoseSpaces.WORLD).translation
        back[b] = [t.x, t.y, t.z]
    readback[name] = back
    print('SWIM anim', name, seq.get_play_length(), seq.get_editor_property('number_of_sampled_frames') if hasattr(seq, 'number_of_sampled_frames') else '')

    mf = unreal.AnimMontageFactory(); mf.set_editor_property('source_animation', seq); mf.set_editor_property('target_skeleton', skel)
    m = at.create_asset(name + "_Montage", DST, unreal.AnimMontage, mf)
    try:
        secs = m.get_editor_property('composite_sections')
        for s in secs: s.set_editor_property('next_section_name', s.get_editor_property('section_name'))
        m.set_editor_property('composite_sections', secs); print('SWIM loop set in editor')
    except Exception as e:
        print('SWIM loop not settable in editor:', e)
    lib.save_loaded_asset(m, only_if_is_dirty=False)
    print('SWIM montage', m.get_path_name(), m.get_num_sections(), m.get_section_name(0), m.get_default_blend_in_time(), m.get_default_blend_out_time())
json.dump(readback, open('D:/MT/SwimCook/readback.json', 'w'))
