"""Crowd applause, v2. Each clap is a transient + resonant body (cupped hands
ring) rather than a plain noise burst, and the mix keeps a few close clappers
in front of a distant, darker crowd bed so it reads as hands, not rain.
"""
import array, math, random, wave

SR = 44100
DUR = 9.0
N = int(SR * DUR)
random.seed(11)

left = array.array('d', bytes(8 * N))
right = array.array('d', bytes(8 * N))


def resonator(x, freq, q, gain):
    """2-pole bandpass. The ringing is what gives a clap its pitch/body."""
    w = 2 * math.pi * freq / SR
    r = math.exp(-w / (2 * q))
    a1, a2 = 2 * r * math.cos(w), -r * r
    out = [0.0] * len(x)
    y1 = y2 = 0.0
    for i, s in enumerate(x):
        y = s * (1 - r) + a1 * y1 + a2 * y2
        out[i] = y * gain
        y2, y1 = y1, y
    return out


def clap(bright):
    """Transient crack + two resonant modes, then a short noisy tail."""
    length = int(SR * 0.09)
    # Source: a 1.5 ms burst of noise. Everything after is resonance.
    burst = int(SR * random.uniform(0.0010, 0.0022))
    src = [0.0] * length
    for i in range(burst):
        src[i] = random.uniform(-1.0, 1.0) * (1 - i / burst)

    f1 = random.uniform(900, 1700)          # palm cavity
    f2 = f1 * random.uniform(1.7, 2.6)      # finger slap, brighter
    body = resonator(src, f1, random.uniform(3.5, 7.0), 1.0)
    slap = resonator(src, f2, random.uniform(2.5, 5.0), 0.65 * bright)

    # A little unresonated noise keeps it from sounding like a tuned drum.
    out = [0.0] * length
    dec = random.uniform(70.0, 130.0)
    for i in range(length):
        env = math.exp(-dec * i / SR)
        n = random.uniform(-1.0, 1.0) * env * 0.18 * bright
        out[i] = (body[i] + slap[i]) * env + n
    # Hard front edge: the first sample is the loudest thing in the clap.
    out[0] += random.uniform(0.5, 0.9)
    return out


def onepole_lp(x, freq):
    a = math.exp(-2 * math.pi * freq / SR)
    y = 0.0
    out = [0.0] * len(x)
    for i, s in enumerate(x):
        y = a * y + (1 - a) * s
        out[i] = y
    return out


def add(sig, start, gl, gr):
    end = min(N, start + len(sig))
    for i in range(max(0, -start), end - start):
        left[start + i] += sig[i] * gl
        right[start + i] += sig[i] * gr


def energy(t):
    if t < 0.7:
        return 0.15 + 0.8 * (t / 0.7) ** 2
    if t < 5.4:
        return 0.9 + 0.1 * math.sin((t - 0.7) * 0.9)
    return max(0.0, 1.0 - (t - 5.4) / 3.6) ** 1.4


# Two layers: a handful of close, detailed clappers you can pick out, and a
# large distant crowd that is quieter, darker and washier.
def layer(count, near, level):
    for _ in range(count):
        period = random.uniform(0.19, 0.36)
        pan = random.uniform(-1.0, 1.0) * (0.7 if near else 1.0)
        gl = math.cos((pan + 1) * math.pi / 4) * level
        gr = math.sin((pan + 1) * math.pi / 4) * level
        bright = random.uniform(0.7, 1.0) if near else random.uniform(0.3, 0.6)
        delay = 0 if near else int(SR * random.uniform(0.004, 0.03))
        t = random.uniform(0.0, 1.2)
        while t < DUR:
            e = energy(t)
            if e > 0.03 and random.random() < min(1.0, e * 1.1):
                c = clap(bright)
                if not near:
                    c = onepole_lp(c, random.uniform(2500, 5000))  # air loss
                add(c, int(t * SR) + delay, gl, gr)
            t += max(0.06, period * random.uniform(0.85, 1.2) / (0.6 + 0.7 * e))

layer(9, True, 0.85)     # front row
layer(55, False, 0.5)    # the rest of the room

# A couple of whoops, well under the claps.
for _ in range(4):
    start = random.uniform(1.0, 5.5)
    length = int(SR * random.uniform(0.25, 0.6))
    f0 = random.uniform(1400, 2400)
    pan = random.uniform(-0.8, 0.8)
    gl = math.cos((pan + 1) * math.pi / 4) * 0.035
    gr = math.sin((pan + 1) * math.pi / 4) * 0.035
    ph = 0.0
    sig = [0.0] * length
    for i in range(length):
        u = i / length
        f = f0 * (1 + 0.25 * u) + 30 * math.sin(2 * math.pi * 5.0 * i / SR)
        ph += 2 * math.pi * f / SR
        sig[i] = math.sin(ph) * math.sin(math.pi * u) ** 1.5
    add(sig, int(start * SR), gl, gr)

# Short, quiet room reflections only — long reverb smears claps into hiss.
def room(buf, taps):
    out = array.array('d', buf)
    for d_ms, g in taps:
        d = int(SR * d_ms / 1000.0)
        for i in range(d, N):
            out[i] += out[i - d] * g
    return out

left = room(left, [(17.0, 0.16), (37.0, 0.11), (71.0, 0.07)])
right = room(right, [(21.0, 0.16), (43.0, 0.11), (79.0, 0.07)])

peak = max(max(abs(v) for v in left), max(abs(v) for v in right)) or 1.0
gain = 2.1 * 0.95 / peak   # push into the limiter for real-world loudness
frames = array.array('h', bytes(4 * N))
for i in range(N):
    # Limit only the rare overshoot; leave transients untouched.
    l, r = left[i] * gain, right[i] * gain
    if abs(l) > 0.9: l = math.copysign(0.9 + math.tanh((abs(l) - 0.9) * 6) * 0.09, l)
    if abs(r) > 0.9: r = math.copysign(0.9 + math.tanh((abs(r) - 0.9) * 6) * 0.09, r)
    frames[2 * i] = int(max(-32767, min(32767, l * 32000)))
    frames[2 * i + 1] = int(max(-32767, min(32767, r * 32000)))

with wave.open('applause.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(frames.tobytes())
print('ok')
