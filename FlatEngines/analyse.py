import sys, numpy as np
from scipy.io import wavfile
def report(path, rpm, cyls):
    sr, x = wavfile.read(path); x = x.astype(np.float64)
    if x.ndim > 1: x = x.mean(axis=1)
    x /= 32768 if np.abs(x).max() > 2 else 1
    peak, rms = np.abs(x).max(), np.sqrt((x**2).mean())
    X = np.abs(np.fft.rfft(x * np.hanning(len(x)))); f = np.fft.rfftfreq(len(x), 1/sr)
    def band(c): m = (f > c*0.94) & (f < c*1.06); return X[m].max()
    crank = rpm / 60; fire = crank * cyls / 2
    cen = (f * X).sum() / X.sum()
    print(f"{path.split('/')[-1]}: peak {peak:.2f} rms {rms:.3f} clip {(np.abs(x)>0.99).mean()*100:.2f}% centroid {cen:.0f} Hz | "
          f"crank {crank:.0f} Hz {20*np.log10(band(crank)/band(fire)):+.1f} dB vs firing {fire:.0f} Hz, 2x firing {20*np.log10(band(2*fire)/band(fire)):+.1f} dB")
for a in sys.argv[1:]:
    p, rpm, c = a.split(','); report(p, float(rpm), int(c))
