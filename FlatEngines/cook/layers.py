# Renders the two layers the game's MTEngineSoundDataAsset plays per rpm step, from each engine's on-load
# config: <name>_<rpm>_engine.wav (intake + mechanical, exhaust_volume 0) and <name>_<rpm>_exhaust.wav
# (exhaust only, intake_volume and engine_vibrations_volume 0). Same rpm steps and enginesound flags as the
# existing anchors (render3.sh). Runs enginesound.linux in the rust:1 image.
#   python layers.py          write cfgs + list, render everything (skips existing wavs)
import os, re, glob, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
FE = os.path.dirname(HERE)
OUT = os.path.join(FE, "layers")
from prep_wavs import SOURCES, engine_class  # (anchor folder, engines, two loads?)

CFG = {"iconic/anchors": "iconic/cfg/{}_on.esc", "diesel/anchors": "diesel/cfg/{}_on.esc", "anchors": "cfg2/{}.esc"}
ZERO = {"engine": ["exhaust_volume"], "exhaust": ["intake_volume", "engine_vibrations_volume"]}
# against the "bee" buzz (buzz.py): more crank fluctuation everywhere, more intake noise on petrol engines;
# diesels stay moderate, they have clatter
FLUCT, INTAKE_NOISE = 0.30, {"petrol": 0.45, "diesel": 0.15}


def steps(folder, name, loads):
    pat = rf"^{re.escape(name)}_on_(\d+)\.wav$" if loads else rf"^{re.escape(name)}_(\d+)\.wav$"
    return sorted(int(m.group(1)) for p in glob.glob(os.path.join(FE, folder, f"{name}_*.wav"))
                  if (m := re.match(pat, os.path.basename(p))))


def main():
    os.makedirs(os.path.join(OUT, "cfg"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "anchors"), exist_ok=True)
    jobs = []
    for folder, names, loads in SOURCES:
        for name in names:
            src = open(os.path.join(FE, CFG[folder].format(name))).read()
            for k, v in (("crankshaft_fluctuation", FLUCT), ("intake_noise_factor", INTAKE_NOISE[engine_class(name)])):
                src, n = re.subn(r"\b" + k + r":[-0-9.e]+", f"{k}:{v}", src)
                assert n == 1, (name, k, n)
            for layer, keys in ZERO.items():
                s = src
                for k in keys:
                    s, n = re.subn(rf"\b{k}:[-0-9.e]+", f"{k}:0", s)
                    assert n == 1, (name, k, n)
                cf = os.path.join(OUT, "cfg", f"{name}_{layer}.esc")
                if not os.path.exists(cf) or open(cf).read() != s:  # config changed: its renders are stale
                    for old in glob.glob(os.path.join(OUT, "anchors", f"{name}_*_{layer}.wav")):
                        os.remove(old)
                open(cf, "w", newline="\n").write(s)
                for r in steps(folder, name, loads):
                    if not os.path.exists(os.path.join(OUT, "anchors", f"{name}_{r}_{layer}.wav")):
                        jobs.append(f"{name} {r} {layer}")
    open(os.path.join(OUT, "list.txt"), "w", newline="\n").write("".join(j + "\n" for j in jobs))
    sh = r'''while read name rpm layer; do
  cf=$(awk "BEGIN{print 240/$rpm}"); len=$(awk "BEGIN{print 3+$cf/2}")
  /b/enginesound -h -c /w/layers/cfg/${name}_$layer.esc -r $rpm -l $len -f $cf -w 1.2 -v 1 -o /w/layers/anchors/${name}_${rpm}_$layer.wav >/dev/null 2>&1 &
  while [ $(jobs -r | wc -l) -ge 8 ]; do sleep 0.2; done
done < /w/layers/list.txt
wait; ls /w/layers/anchors | wc -l
'''
    open(os.path.join(OUT, "render.sh"), "w", newline="\n").write(sh)
    print(len(jobs), "renders queued")
    if jobs:
        fe = FE.replace("\\", "/")
        subprocess.run(["docker", "run", "--rm", "-v", f"{fe}:/w", "-v", f"{fe}/enginesound.linux:/b/enginesound",
                        "rust:1", "bash", "/w/layers/render.sh"], check=True, env={**os.environ, "MSYS_NO_PATHCONV": "1"})


if __name__ == "__main__":
    main()
