# Copies the cooked MT_<engine> wave folders from the cook project into the mod and checks every wave:
# UAssetGUI reads it back as a SoundWave NormalExport (not RawExport), and its package summary is the same
# unversioned UE5 layout as QX_Flutter_Shot (a cooked wave known to work in game).
# Only Cars/Parts/Engine/Sound/MT_* is copied: the project's /Game/Sounds stand-ins never leave it.
import os, sys, glob, json, shutil, struct, subprocess
COOKED = r"D:\MT\SoundCook\MTEngineSounds\Saved\Cooked\Windows\MTEngineSounds\Content\Cars\Parts\Engine\Sound"
MOD = r"D:\MT\MoreTuning\qxZap_MoreTuning_P\MotorTown\Content\Cars\Parts\Engine\Sound"
REF = r"D:\MT\MoreTuning\qxZap_MoreTuning_P\MotorTown\Content\Sounds\Vehicle\Intake\QX_Flutter_Shot.uasset"
WORK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "work", "readback")


def summary(p):
    b = open(p, "rb").read(24)
    tag, legacy, ue3, ue4, ue5, lic = struct.unpack_from("<Iiiiii", b)
    return tag, legacy, ue4, ue5, lic


def main():
    ref = summary(REF)
    os.makedirs(WORK, exist_ok=True)
    n = 0
    for src in sorted(glob.glob(os.path.join(COOKED, "MT_*"))):
        dst = os.path.join(MOD, os.path.basename(src))
        if os.path.isdir(dst):  # keep the EngineSoundData make_data.py writes, replace the waves
            for f in glob.glob(os.path.join(dst, "*rpm_*.u*")) + glob.glob(os.path.join(dst, "*_Starter.u*")):
                os.remove(f)
        os.makedirs(dst, exist_ok=True)
        for f in glob.glob(os.path.join(src, "*")):
            shutil.copy2(f, dst)
        for ua in sorted(glob.glob(os.path.join(dst, "*rpm_*.uasset")) + glob.glob(os.path.join(dst, "*_Starter.uasset"))):
            assert summary(ua) == ref, (ua, summary(ua), ref)
            for ext in (".uexp", ".ubulk"):
                assert os.path.exists(ua[:-7] + ext), ua[:-7] + ext
            js = os.path.join(WORK, os.path.basename(ua)[:-7] + ".json")
            if os.path.exists(js):
                os.remove(js)
            subprocess.run([r"D:\MT\UAssetGUI.exe", "tojson", ua, js, "VER_UE5_4", "MotorTown720T6"], check=True)
            assert os.path.exists(js), f"UAssetGUI wrote nothing for {ua}"
            e = json.load(open(js))["Exports"][0]
            assert e["$type"].endswith("NormalExport, UAssetAPI"), (ua, e["$type"])
            imps = {i["ObjectName"] for i in json.load(open(js))["Imports"]}
            assert {"Class_Engine", "EngineSoundAttenuation"} <= imps, (ua, imps)
            n += 1
    print(n, "waves copied and verified; summary", ref)


if __name__ == "__main__":
    main()
