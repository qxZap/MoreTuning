# Flyby previews of shipped engine sets, for review on Telegram: a 3rd-gear pull past the listener, a shift, a second
# pull, a lift -- from the wavs the cook ships (Exhaust + Engine layer per rpm step), doppler and distance by drive_by.
# Trucks and pickups pass at half the car speeds.
#   python flyby_preview.py <out dir> <engine> [engine ...]
import sys, os, re, glob, subprocess, json, numpy as np
from scipy.io import wavfile
H = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [H, os.path.join(H, "recompose")]
exec(open(os.path.join(H, "drive_by.py")).read().split("folder = sys.argv[1]")[0])  # place(), tyres(), run(), SR
import scene_diesel as sd
import es_steps

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
for name in sys.argv[2:]:
    W = rf"D:\MT\SoundCook\wav\MT_{name}"
    loops = {}
    for p in glob.glob(W + rf"\MT_{name}_*rpm_Exhaust.wav"):
        k = int(re.search(r"_(\d+)rpm_", p).group(1))
        a = wavfile.read(p)[1].astype(float) / 32768
        b = wavfile.read(p.replace("Exhaust", "Engine"))[1].astype(float) / 32768
        loops[k] = a + (b[:len(a)] if b.any() else 0)  # a silent engine layer is not resampled with the exhaust
    loops = dict(sorted(loops.items()))
    d = es_steps.engine_spec(name)
    top, vs = d["top"], (1.0 if d["kind"] == "car" else 0.5)
    script = np.array([[0, 0.45 * top, 0.4, 24 * vs], [2.5, 0.47 * top, 0.4, 25 * vs], [2.8, 0.5 * top, 1, 26 * vs],
                       [5.3, 0.95 * top, 1, 45 * vs], [5.45, 0.72 * top, 0.2, 45 * vs], [5.6, 0.73 * top, 1, 45 * vs],
                       [8.2, 0.92 * top, 1, 56 * vs], [8.4, 0.9 * top, 0, 56 * vs], [12.0, 0.45 * top, 0, 48 * vs]], float)
    t, rpm, thr, speed = run(script, 12.0)
    eng = sd.play(loops, rpm)
    on = lfilter([0.002], [1, -0.998], thr)
    eng = (0.45 + 0.55 * on) * (on * eng + (1 - on) * sosfilt(butter(2, 900, fs=SR, output="sos"), eng))
    st = place(eng / np.abs(eng).max() + tyres(speed, len(t)), speed, t, 5.0)
    fade = np.minimum(1, np.minimum(t / 0.6, (12 - t) / 0.8))[:, None]
    y = st * fade
    y = y / np.abs(y).max() * 0.89
    wav = os.path.join(out, f"{name}_flyby.wav")
    wavfile.write(wav, SR, (y * 32767).astype(np.int16))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-b:a", "192k", wav[:-4] + ".mp3"], check=True)
    os.remove(wav)
    print(wav[:-4] + ".mp3", flush=True)
