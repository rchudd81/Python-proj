import numpy as np
import matplotlib.pyplot as plt
import socket
import struct
import threading

HOST = '127.0.0.1'
PORT = 56789

class SpectrumPlotter:
    def __init__(self):
        self.fig, self.ax = plt.subplots(figsize=(10, 6))
        self.line, = self.ax.plot([], [], lw=2)
        self.ax.set_title('Transmitted IQ Spectrum')
        self.ax.set_xlabel('Frequency (MHz)')
        self.ax.set_ylabel('Power (dB)')
        self.ax.grid(True)
        self.ax.set_xlim(-5, 5)
        self.ax.set_ylim(-140, 10)
        self.running = True
        self.thread = threading.Thread(target=self.listen_for_data, daemon=True)
        self.thread.start()

    def listen_for_data(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((HOST, PORT))
            s.listen(1)
            while self.running:
                conn, addr = s.accept()
                with conn:
                    # Receive header: 8 bytes for sample_rate, 4 bytes for N
                    header = conn.recv(12)
                    if len(header) < 12:
                        continue
                    sample_rate, N = struct.unpack('dI', header)
                    if sample_rate == 0.0 and N == 0:
                        # Shutdown signal
                        import matplotlib.pyplot as plt
                        plt.close(self.fig)
                        self.running = False
                        break
                    # Receive IQ data (N complex64)
                    iq_bytes = b''
                    while len(iq_bytes) < N * 8:
                        chunk = conn.recv(N * 8 - len(iq_bytes))
                        if not chunk:
                            break
                        iq_bytes += chunk
                    if len(iq_bytes) == N * 8:
                        iq = np.frombuffer(iq_bytes, dtype=np.complex64)
                        self.update_plot(iq, sample_rate)

    def update_plot(self, iq, sample_rate):
        N = len(iq)
        window = np.hanning(N)
        iq_win = iq * window
        spectrum = np.fft.fftshift(np.fft.fft(iq_win))
        freqs = np.fft.fftshift(np.fft.fftfreq(N, d=1/sample_rate))
        power = 20 * np.log10(np.abs(spectrum) + 1e-12)
        self.line.set_data(freqs / 1e6, power)
        self.ax.set_xlim(freqs[0]/1e6, freqs[-1]/1e6)
        if np.all(np.isfinite(power)):
            self.ax.set_ylim(np.max(power)-100, np.max(power)+10)
        else:
            self.ax.set_ylim(-140, 10)
        self.fig.canvas.draw_idle()

    def show(self):
        plt.show()
        self.running = False

if __name__ == '__main__':
    plotter = SpectrumPlotter()
    plotter.show()
