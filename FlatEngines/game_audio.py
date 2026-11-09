# What Motor Town does to an MTEngineSoundDataAsset at runtime, measured by the SoundProbe loader plugin on the
# 0.7.20+T6 build (2026-11-07, plugins/logs/SoundProbe): every preview plays sets through this, so what is judged on
# Telegram is what the game plays. My earlier previews kept steps phase-locked and ignored throttle -- the game does
# neither, which is why previews and the game disagreed.
#   pitch  = clamp(rpm / step rpm, MinPitch, MaxPitch)         defaults 0.5, 2 (exact to 0.001 in the log)
#   blend  = adjacent steps only, smoothstep in log rpm         (fits the logged weights to ~0.03)
#   volume = layer ratio + (1 - ratio) * throttle, per layer    IdleEngineRatio 0.5, IdleExhaustRatio 0.2 by default:
#            with the throttle shut the exhaust layer plays at a fifth of full, the engine layer at half
#   no filtering anywhere: Class_Engine, the attenuation and both sound mixes leave the low-pass at 20 kHz
# Steps are not phase-locked in the game; each plays from its own start here.
#   python -I game_audio.py demo
import numpy as np
from scipy.signal import lfilter

SR = 48000
DEFAULTS = dict(MinPitch=0.5, MaxPitch=2.0, IdleEngineRatio=0.5, IdleExhaustRatio=0.2)


def weights(keys, rpm):
    """Per-step blend weight over time: adjacent steps only, smoothstep in log rpm."""
    keys = np.asarray(keys, float)
    if len(keys) == 1:
        return np.ones((1, len(rpm)))
    lo = np.clip(np.searchsorted(keys, rpm) - 1, 0, len(keys) - 2)
    a, b = keys[lo], keys[lo + 1]
    f = np.clip(np.log(np.maximum(rpm, 1) / a) / np.log(b / a), 0, 1)
    f = f * f * (3 - 2 * f)
    w = np.zeros((len(keys), len(rpm)))
    idx = np.arange(len(rpm))
    w[lo, idx] = 1 - f
    w[lo + 1, idx] = f
    return w


def play_layer(loops, rpm, settings=None, rng=None):
    """One layer's steps ({rpm: loop}) through the game's pitch clamp and blend, each step on its own clock."""
    s = dict(DEFAULTS, **(settings or {}))
    rng = rng or np.random.default_rng(0)
    keys = sorted(loops)
    w = weights(keys, rpm)
    y = np.zeros(len(rpm))
    for j, k in enumerate(keys):
        if w[j].max() == 0:
            continue
        src = loops[k]
        pitch = np.clip(rpm / k, s["MinPitch"], s["MaxPitch"])
        pos = (rng.uniform(0, len(src)) + np.cumsum(pitch)) % len(src)
        i0 = pos.astype(int)
        fr = pos - i0
        y += w[j] * (src[i0] * (1 - fr) + src[(i0 + 1) % len(src)] * fr)
    return y


def play(engine, exhaust, rpm, throttle, settings=None):
    """Both layers as the game mixes them: each scaled by its idle ratio and the (smoothed) throttle, times the
    asset's volumes. engine/exhaust: {rpm: loop}; a silent layer may be {}."""
    s = dict(DEFAULTS, MasterVolume=1.0, EngineVolumeMultiplier=1.0, ExhaustVolumeMultiplier=1.0, **(settings or {}))
    thr = lfilter([0.0015], [1, -0.9985], np.clip(throttle, 0, 1))  # the game eases throttle into the mix
    y = np.zeros(len(rpm))
    for layer, ratio, mult in ((engine, s["IdleEngineRatio"], s["EngineVolumeMultiplier"]),
                               (exhaust, s["IdleExhaustRatio"], s["ExhaustVolumeMultiplier"])):
        if layer:
            y += play_layer(layer, rpm, s, np.random.default_rng(len(layer))) * (ratio + (1 - ratio) * thr) * mult
    return y * s["MasterVolume"]


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["demo"]:
        # the log: 880->3000 at 1600 rpm weighs about 0.48/0.52; 2010->3060 at 2800 about 0.07/0.93
        w = weights([880, 3000], np.array([1600.0]))
        assert abs(w[1, 0] - 0.52) < 0.06, w[:, 0]
        w = weights([2010, 3060], np.array([2800.0]))
        assert abs(w[1, 0] - 0.93) < 0.06, w[:, 0]
        # throttle shut: the exhaust layer at a fifth of full
        tone = {1000: np.sin(2 * np.pi * 100 * np.arange(SR) / SR)}
        r = np.full(SR * 4, 1000.0)
        idle = play({}, tone, r, np.zeros_like(r))[-SR:]
        full = play({}, tone, r, np.ones_like(r))[-SR:]
        assert abs(np.sqrt(np.mean(idle ** 2)) / np.sqrt(np.mean(full ** 2)) - 0.2) < 0.02
        print("demo ok")
