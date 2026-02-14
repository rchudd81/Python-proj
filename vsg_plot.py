
import numpy as np
import matplotlib.pyplot as plt
import sys

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python vsg_plot.py spectrum_data.npz')
        sys.exit(1)
    datafile = sys.argv[1]
    data = np.load(datafile)
    freqs = data['freqs']
    spectrum = data['spectrum']
    power = 20 * np.log10(np.abs(spectrum) + 1e-12)
    plt.figure(figsize=(10, 6))
    plt.plot(freqs / 1e6, power)
    plt.title('Transmitted IQ Spectrum')
    plt.xlabel('Frequency (MHz)')
    plt.ylabel('Power (dB)')
    plt.grid(True)
    plt.xlim(freqs[0]/1e6, freqs[-1]/1e6)
    if np.all(np.isfinite(power)):
        plt.ylim(np.max(power)-100, np.max(power)+10)
    plt.show()
