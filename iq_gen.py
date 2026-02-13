"""Simple IQ file generator

Creates interleaved float32 IQ binary files (I,Q,I,Q,...). Usage:

python iq_gen.py --out tone.iq --sample-rate 1e6 --tone 100e3 --length 16384 --amplitude 0.5

This writes `tone.iq` as raw interleaved float32. You can also save as NumPy .npy with --npy flag.
"""
import argparse
import numpy as np


def generate_iq(tone_hz, sample_rate, num_samples, amplitude=1.0, phase=0.0):
    t = np.arange(num_samples) / float(sample_rate)
    i = (amplitude * np.cos(2 * np.pi * tone_hz * t + phase)).astype(np.float32)
    q = (amplitude * np.sin(2 * np.pi * tone_hz * t + phase)).astype(np.float32)
    iq = np.empty(num_samples * 2, dtype=np.float32)
    iq[0::2] = i
    iq[1::2] = q
    return iq


def main():
    p = argparse.ArgumentParser(description="Generate interleaved IQ files (float32)")
    p.add_argument("--out", required=True, help="Output filename (e.g. tone.iq)")
    p.add_argument("--sample-rate", type=float, default=1e6)
    p.add_argument("--tone", type=float, default=100e3)
    p.add_argument("--length", type=int, default=16384, help="Number of complex samples")
    p.add_argument("--amplitude", type=float, default=1.0)
    p.add_argument("--phase", type=float, default=0.0)
    p.add_argument("--npy", action="store_true", help="Also save as .npy (NumPy) format)")
    args = p.parse_args()

    iq = generate_iq(args.tone, args.sample_rate, args.length, amplitude=args.amplitude, phase=args.phase)
    out = args.out
    # Write raw interleaved float32
    with open(out, "wb") as f:
        f.write(iq.tobytes())
    print(f"Wrote {out} ({iq.nbytes} bytes, {args.length} complex samples)")
    if args.npy:
        np.save(out + ".npy", iq)
        print(f"Also saved {out}.npy")


if __name__ == '__main__':
    main()
