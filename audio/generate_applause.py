"""Synthesize a crowd-applause WAV (stdlib only): many independent clappers,
each a stochastic train of filtered noise bursts, summed and reverberated.
"""
import array, math, random, struct, wave

SR = 44100
DUR = 9.0
N = int(SR * DUR)
random.seed(7)

left = array.array('d', bytes(8 * N))
right = array.array('d', bytes(8 * N))


def clap(hardness):
    """One clap: noise burst, band-shaped by a one-pole HP + one-pole LP,
    with a fast attack and exponential decay. Returns a float list."""
    length = int(SR * random.uniform(0.045, 0.11))
    decay = random.uniform(180.0, 420.0)          # 1/sec
    lp_a = math.exp(-2 * math.pi * random.uniform(2200, 6500) / SR)
    hp_a = math.exp(-2 * math.pi * random.uniform(500, 1400) / SR)
    out = [0.0] * length
    lp = hp_x = hp_y = 0.0
    attack = max(4, int(SR * 0.0012))
    for i in range(length):
        x = random.uniform(-1.0, 1.0)
        lp = lp_a * lp + (1 - lp_a) * x           # lowpass: dulls the crack
        hp_y = hp_a * (hp_y + lp - hp_x)          # highpass: removes body
        hp_x = lp
        env = math.exp(-decay * i / SR)
        if i < attack:
            env *= i / attack
        out[i] = hp_y * env * hardness
    return out


def add(buf_l, buf_r, sig, start, gain_l, gain_r):
    end = min(N, start + len(sig))
    for i in range(max(0, -start), end - start):
        s = sig[i]
        buf_l[start + i] += s * gain_l
        buf_r[start + i] += s * gain_r


# Crowd energy over time: a few people start, it swells to a roar, then eases.
def energy(t):
    if t < 0.9:
        return 0.12 + 0.75 * (t / 0.9) ** 2       # ragged start
    if t < 5.6:
        return 0.87 + 0.13 * math.sin((t - 0.9) * 1.1)
    return max(0.0, 1.0 - (t - 5.6) / 3.4) ** 1.5  # fade as it dies down

CLAPPERS = 70
for c in range(CLAPPERS):
    period = random.uniform(0.16, 0.34)           # personal clapping tempo
    jitter = period * random.uniform(0.06, 0.22)
    dist = random.uniform(0.25, 1.0)              # near the mic vs. far back
    hardness = random.uniform(0.35, 1.0) * dist
    pan = random.uniform(-1.0, 1.0)
    gl = math.cos((pan + 1) * math.pi / 4)
    gr = math.sin((pan + 1) * math.pi / 4)
    delay = int(SR * (1 - dist) * 0.02)           # far claps arrive later
    t = random.uniform(0.0, 1.4)
    while t < DUR:
        e = energy(t)
        if e > 0.02 and random.random() < min(1.0, e * 1.15):
            add(left, right, clap(hardness * (0.55 + 0.45 * e)),
                int(t * SR) + delay, gl, gr)
        t += max(0.05, period * random.uniform(0.85, 1.15) / (0.55 + 0.75 * e)) \
             + random.uniform(-jitter, jitter)

# A handful of whistles / whoops riding on top of the roar.
for _ in range(6):
    start = random.uniform(1.2, 6.0)
    length = int(SR * random.uniform(0.3, 0.7))
    f0 = random.uniform(1500, 2600)
    f1 = f0 * random.uniform(1.05, 1.5)
    pan = random.uniform(-0.8, 0.8)
    gl = math.cos((pan + 1) * math.pi / 4) * 0.05
    gr = math.sin((pan + 1) * math.pi / 4) * 0.05
    ph = 0.0
    sig = [0.0] * length
    for i in range(length):
        u = i / length
        f = f0 + (f1 - f0) * u + 25 * math.sin(2 * math.pi * 5.5 * i / SR)
        ph += 2 * math.pi * f / SR
        env = math.sin(math.pi * u) ** 1.5
        sig[i] = math.sin(ph) * env
    add(left, right, sig, int(start * SR), gl, gr)

# Room: a small feedback-delay reverb so it reads as a hall, not a dry studio.
def reverb(buf, taps):
    out = array.array('d', buf)
    for d_ms, g in taps:
        d = int(SR * d_ms / 1000.0)
        for i in range(d, N):
            out[i] += out[i - d] * g
    return out

left = reverb(left, [(23.0, 0.30), (41.0, 0.24), (67.0, 0.18), (113.0, 0.12)])
right = reverb(right, [(29.0, 0.30), (47.0, 0.24), (73.0, 0.18), (127.0, 0.12)])

peak = max(max(abs(v) for v in left), max(abs(v) for v in right)) or 1.0
gain = 0.89 / peak
frames = array.array('h', bytes(4 * N))
for i in range(N):
    # Soft-clip so the densest moments compress instead of crackling.
    l = math.tanh(left[i] * gain * 1.25)
    r = math.tanh(right[i] * gain * 1.25)
    frames[2 * i] = int(max(-32767, min(32767, l * 31000)))
    frames[2 * i + 1] = int(max(-32767, min(32767, r * 31000)))

with wave.open('applause.wav', 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(frames.tobytes())
print('wrote applause.wav')
