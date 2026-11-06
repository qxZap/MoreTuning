# Runs inside UnrealEditor-Cmd (-run=pythonscript): imports D:\MT\SoundCook\wav\MT_<engine>\*.wav as SoundWaves
# at /Game/Cars/Parts/Engine/Sound/MT_<engine>/ and sets them up like vanilla's per-rpm layer waves
# (MidDuty_02/1000rpm_Exhaust): looping, SoundClass /Game/Sounds/Class_Engine, attenuation
# /Game/Sounds/EngineSoundAttenuation. The game owns those two; here they are stand-ins at the same paths so the
# cooked waves import them by path. The stand-ins must never be shipped. Fails loudly on any missing asset.
import os, glob, unreal

# a commandlet creates no audio device, so the BINKA decoder the importer asks for is never registered
unreal.load_module("BinkAudioDecoder")
unreal.load_module("AdpcmAudioDecoder")  # also decodes PCM (every set ships PCM)

SRC = r"D:\MT\SoundCook\wav"
ROOT = "/Game/Cars/Parts/Engine/Sound"
tools = unreal.AssetToolsHelpers.get_asset_tools()
lib = unreal.EditorAssetLibrary


def stub(path, cls, factory):
    if lib.does_asset_exist(path):
        return lib.load_asset(path)
    pkg, name = path.rsplit("/", 1)
    return tools.create_asset(name, pkg, cls, factory)


sound_class = stub("/Game/Sounds/Class_Engine", unreal.SoundClass, unreal.SoundClassFactory())
att = stub("/Game/Sounds/EngineSoundAttenuation", unreal.SoundAttenuation, unreal.SoundAttenuationFactory())
# vanilla EngineSoundAttenuation's settings, so the derived MaxDistance the waves serialise matches
s = att.get_editor_property("attenuation")
s.set_editor_property("non_spatialized_radius_start", 500.0)
s.set_editor_property("non_spatialized_radius_end", 200.0)
s.set_editor_property("distance_algorithm", unreal.AttenuationDistanceModel.NATURAL_SOUND)
s.set_editor_property("d_b_attenuation_at_max", -30.0)
s.set_editor_property("attenuation_shape_extents", unreal.Vector(200.0, 0.0, 0.0))
s.set_editor_property("falloff_distance", 6400.0)
att.set_editor_property("attenuation", s)
lib.save_loaded_asset(att, only_if_is_dirty=False)
lib.save_loaded_asset(sound_class, only_if_is_dirty=False)

# every set ships uncompressed: BINKA codes a loop's end and start independently, so the cooked wave jumps 4-13x a
# normal sample step at every wrap even when the wav is seamless (cgtv10: a small static every loop, loudest at
# redline). ~96 KB a second of wave; loudness.verify fails on any shipped wave that jumps at its wrap.

tasks, expect = [], []
for d in sorted(os.listdir(SRC)):
    if lib.does_directory_exist(f"{ROOT}/{d}"):
        lib.delete_directory(f"{ROOT}/{d}")
    for f in sorted(glob.glob(os.path.join(SRC, d, "*.wav"))):
        t = unreal.AssetImportTask()
        t.filename, t.destination_path = f, f"{ROOT}/{d}"
        t.automated, t.replace_existing, t.save = True, True, True
        tasks.append(t)
        expect.append(f"{ROOT}/{d}/{os.path.splitext(os.path.basename(f))[0]}")
tools.import_asset_tasks(tasks)
missing = []
for p in expect:
    w = lib.load_asset(p)
    if not isinstance(w, unreal.SoundWave):
        missing.append(p)
        continue
    w.set_editor_property("looping", not p.endswith("_Starter"))  # the starter is a one-shot, like vanilla's
    w.set_editor_property("sound_class_object", sound_class)
    w.set_editor_property("attenuation_settings", att)
    w.set_editor_property("sound_asset_compression_type", unreal.SoundAssetCompressionType.PCM)
    lib.save_loaded_asset(w, only_if_is_dirty=False)
unreal.log(f"MTIMPORT imported {len(expect) - len(missing)} of {len(expect)}")
if missing:
    unreal.log_error("MTIMPORT missing: " + ", ".join(missing))
    raise SystemExit(1)
