import matplotlib
matplotlib.use('TkAgg')  # or 'Qt5Agg' if you prefer
import numpy as np
import matplotlib.pyplot as plt
import socket
import struct
import threading
import sys

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
        import threading
        def handle_client(conn):
            with conn:
                print('[vsg_plot] Connection received')
                # Receive header: 8 bytes for sample_rate, 4 bytes for N
                header = conn.recv(12)
                if len(header) < 12:
                    print('[vsg_plot] Incomplete header received')
                    return
                sample_rate, N = struct.unpack('dI', header)
                if sample_rate == 0.0 and N == 0:
                    print('[vsg_plot] Shutdown signal received')
                    import matplotlib.pyplot as plt
                    plt.close(self.fig)
                    self.running = False
                    return
                # Receive IQ data (N complex64)
                iq_bytes = b''
                while len(iq_bytes) < N * 8:
                    chunk = conn.recv(N * 8 - len(iq_bytes))
                    if not chunk:
                        print('[vsg_plot] Connection closed before all data received')
                        return
                    iq_bytes += chunk
                if len(iq_bytes) == N * 8:
                    print(f'[vsg_plot] Received IQ data, N={N}')
                    iq = np.frombuffer(iq_bytes, dtype=np.complex64)
                    self.update_plot(iq, sample_rate)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((HOST, PORT))
            except OSError as e:
                print(f'[vsg_plot] Failed to bind to {HOST}:{PORT}: {e}')
                print('[vsg_plot] Is another plot window already running?')
                sys.exit(1)
            print(f'[vsg_plot] Listening on {HOST}:{PORT}')
            s.listen(5)
            while self.running:
                try:
                    conn, addr = s.accept()
                    print(f'[vsg_plot] Accepted connection from {addr}')
                except OSError:
                    break
                threading.Thread(target=handle_client, args=(conn,), daemon=True).start()

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
    print('[vsg_plot] Starting SpectrumPlotter...')
    plotter = SpectrumPlotter()
    plotter.show()
