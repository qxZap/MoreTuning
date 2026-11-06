# The audible rumble: how much the loudness (100 Hz-2 kHz envelope) pulses at crank rate vs firing rate.
import sys, numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfiltfilt, hilbert
for a in sys.argv[1:]:
    p, rpm, c = a.split(','); rpm = float(rpm); c = int(c)
    sr, x = wavfile.read(p); x = x.astype(float); x = x.mean(axis=1) if x.ndim > 1 else x
    env = np.abs(hilbert(sosfiltfilt(butter(4, [100, 2000], 'bandpass', fs=sr, output='sos'), x)))
    env -= env.mean(); E = np.abs(np.fft.rfft(env * np.hanning(len(env)))); f = np.fft.rfftfreq(len(env), 1/sr)
    b = lambda fr: E[(f > fr*0.93) & (f < fr*1.07)].max()
    crank = rpm/60; fire = crank*c/2
    print(f"{p.split('/')[-1]}: loudness pulsing at crank rate {20*np.log10(b(crank)/b(fire)):+.1f} dB vs firing rate")
