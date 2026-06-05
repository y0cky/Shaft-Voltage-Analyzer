import os
import time
import threading
import queue
from datetime import datetime
from collections import deque

import tkinter as tk
import customtkinter as ctk
import numpy as np
import pyvisa
import h5py

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# Importiere unsere ausgelagerte Mathe-Funktion
from src.utils.math_utils import calculate_thd

class SyncLoggerFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        
        self.running = False
        self.data_queue = queue.Queue()
        self.event_queue = queue.Queue()
        self.device = None
        self.log_dir = ""

        self.labels = ["RMS", "MEAN", "STD", "PEAK+", "PEAK-", "POS_PULSE", "NEG_PULSE", "THD (%)"]
        self.time_data = deque(maxlen=500)
        self.data_storage = {label: deque(maxlen=500) for label in self.labels}
        self.start_time = 0

        self.grid_columnconfigure(0, weight=0, minsize=280)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_plots()

    def _build_sidebar(self):

        sidebar = ctk.CTkFrame(self, width=280, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(sidebar, text="Wellenspannung Datalogger", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        
        # IP & Intervall
        ctk.CTkLabel(sidebar, text="IP-Adresse:", anchor="w").pack(fill="x", padx=15)
        self.ip_entry = ctk.CTkEntry(sidebar)
        self.ip_entry.insert(0, "192.168.0.100")
        self.ip_entry.pack(fill="x", padx=15, pady=2)
        
        ctk.CTkLabel(sidebar, text="Intervall (s):", anchor="w").pack(fill="x", padx=15)
        self.interval_entry = ctk.CTkEntry(sidebar)
        self.interval_entry.insert(0, "1.0")
        self.interval_entry.pack(fill="x", padx=15, pady=2)
        
        ctk.CTkLabel(sidebar, text="Messname (Dateipräfix):", anchor="w").pack(fill="x", padx=15)
        self.name_entry = ctk.CTkEntry(sidebar)
        self.name_entry.insert(0, "Messung")
        self.name_entry.pack(fill="x", padx=15, pady=2)
        
        ctk.CTkLabel(sidebar, text="Bericht-Kommentar:", anchor="w", font=ctk.CTkFont(weight="bold")).pack(fill="x", padx=15, pady=(10, 0))
        self.comment_entry = ctk.CTkEntry(sidebar, placeholder_text="Zusätzliche Notizen...")
        self.comment_entry.pack(fill="x", padx=15, pady=5)

        self.log_fft_var = tk.BooleanVar(value=True)
        self.chk_log_fft = ctk.CTkCheckBox(sidebar, text="FFT & THD mitloggen", variable=self.log_fft_var)
        self.chk_log_fft.pack(padx=15, pady=10, anchor="w")
        
        self.log_wave_var = tk.BooleanVar(value=True)
        self.chk_log_wave = ctk.CTkCheckBox(sidebar, text="Wellenform mitloggen", variable=self.log_wave_var)
        self.chk_log_wave.pack(padx=15, pady=(0, 10), anchor="w")

        # Buttons Start/Stop
        self.btn_start = ctk.CTkButton(sidebar, text="Start Logging", command=self.start, fg_color="green", hover_color="darkgreen")
        self.btn_start.pack(fill="x", padx=15, pady=5)
        self.btn_stop = ctk.CTkButton(sidebar, text="Stop Logging", command=self.stop, state="disabled", fg_color="red", hover_color="darkred")
        self.btn_stop.pack(fill="x", padx=15, pady=5)

        # EVENT MARKER LOG
        ctk.CTkFrame(sidebar, height=2, fg_color="gray").pack(fill="x", padx=15, pady=10)
        ctk.CTkLabel(sidebar, text="Event-Marker hinzufügen:", anchor="w", font=ctk.CTkFont(weight="bold")).pack(fill="x", padx=15)
        self.event_entry = ctk.CTkEntry(sidebar, placeholder_text="Zustand, Fehler etc...")
        self.event_entry.pack(fill="x", padx=15, pady=2)
        self.btn_event = ctk.CTkButton(sidebar, text="Marker Setzen", command=self.add_event, state="disabled")
        self.btn_event.pack(fill="x", padx=15, pady=5)

        # Werteanzeige in Sidebar
        ctk.CTkLabel(sidebar, text="--- Live Werte ---", font=ctk.CTkFont(weight="bold")).pack(pady=(15,5))
        self.val_labels = {}
        for label in self.labels:
            lbl = ctk.CTkLabel(sidebar, text=f"{label}: ---", font=("Consolas", 14), anchor="w")
            lbl.pack(fill="x", padx=20, pady=1)
            self.val_labels[label] = lbl

    def _build_plots(self):
        plot_container = ctk.CTkFrame(self)
        plot_container.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        self.fig = Figure(figsize=(8, 12), dpi=90)
        self.fig.patch.set_facecolor('#2b2b2b')
        
        self.ax_wave = self.fig.add_subplot(5, 1, 1)
        self.ax_fft = self.fig.add_subplot(5, 1, 2)
        self.ax_stat = self.fig.add_subplot(5, 1, 3)
        self.ax_peak = self.fig.add_subplot(5, 1, 4)
        self.ax_pulse = self.fig.add_subplot(5, 1, 5)

        self.line_fft_curr, = self.ax_fft.plot([], [], color='#1f77b4', label='FFT Aktuell', linewidth=1)
        self.line_fft_avg, = self.ax_fft.plot([], [], color='#ff7f0e', label='FFT Average', linewidth=1.5)
        
        self.line_wave, = self.ax_wave.plot([], [], color='red', linewidth=1, label='Waveform')
        self.ax_wave.set_title("Wellenform")
        
        self.lines = {
            "RMS": self.ax_stat.plot([], [], color='cyan', label='RMS')[0],
            "MEAN": self.ax_stat.plot([], [], color='magenta', label='MEAN')[0],
            "STD": self.ax_stat.plot([], [], color='lime', label='STD')[0],
            "THD (%)": self.ax_stat.plot([], [], color='yellow', label='THD (%)')[0],
            "PEAK+": self.ax_peak.plot([], [], color='orange', label='PEAK+')[0],
            "PEAK-": self.ax_peak.plot([], [], color='red', label='PEAK-')[0],
            "POS_PULSE": self.ax_pulse.plot([], [], color='blue', label='POS_PULSE')[0],
            "NEG_PULSE": self.ax_pulse.plot([], [], color='purple', label='NEG_PULSE')[0]
        }
        
        axes_titles = [(self.ax_wave, "Wellenform"), (self.ax_fft, "FFT Spektrum (dB)"), (self.ax_stat, "Statistik & THD"), (self.ax_peak, "Spitzenwerte"), (self.ax_pulse, "Impulse")]
        for ax, title in axes_titles:
            ax.set_title(title, color='white', fontsize=10)
            ax.set_facecolor('#333333')
            ax.tick_params(colors='white', labelsize=8)
            ax.grid(True, color='#555555', linestyle=":")
            ax.legend(loc='upper left', fontsize='x-small')

        self.fig.tight_layout()

        self.canvas = FigureCanvasTkAgg(self.fig, plot_container)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)
        
        self.after(100, self.update_gui)

    def add_event(self):
        txt = self.event_entry.get().strip()
        if txt:
            self.event_queue.put(txt)
            self.event_entry.delete(0, tk.END)

    def start(self):
        self.running = True
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.btn_event.configure(state="normal")
        self.start_time = time.time()
        
        # --- ALTE GRAPHEN & DATEN LÖSCHEN ---
        self._clear_plots()
        
        user_name = self.name_entry.get().strip() or "Messung"
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Log in den neuen data-Ordner
        self.log_dir = os.path.join("data", f"{user_name}_{timestamp_str}")
        os.makedirs(self.log_dir, exist_ok=True)
        
        threading.Thread(target=self.measurement_thread, daemon=True).start()

    def _clear_plots(self):
        """Löscht alle internen Datenstrukturen und setzt die Matplotlib-Graphen zurück."""
        # 1. Interne Datenspeicher leeren
        self.time_data.clear()
        for label in self.labels:
            self.data_storage[label].clear()
            
        # 2. Live-Labels in der Sidebar zurücksetzen
        for label in self.labels:
            self.val_labels[label].configure(text=f"{label}: ---")

        # 3. Matplotlib-Linien leeren
        self.line_wave.set_data([], [])
        self.line_fft_curr.set_data([], [])
        self.line_fft_avg.set_data([], [])
        
        for line in self.lines.values():
            line.set_data([], [])

        # 4. Achsen-Ansichten zurücksetzen, damit alte Skalierungen verschwinden
        for ax in [self.ax_wave, self.ax_fft, self.ax_stat, self.ax_peak, self.ax_pulse]:
            ax.relim()
            ax.autoscale_view()

        # 5. Canvas einmal leer zeichnen
        self.canvas.draw_idle()

    def stop(self):
        self.running = False
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.btn_event.configure(state="disabled")

    def measurement_thread(self):
        h5_file = None
        try:
            rm = pyvisa.ResourceManager('@py')
            self.device = rm.open_resource(f"TCPIP::{self.ip_entry.get().strip()}::5025::SOCKET")
            self.device.read_termination, self.device.write_termination, self.device.timeout = '\n', '\n', 6000
            
            for i in range(1, 8): self.device.write(f"MEAS{i}:ENAB ON")
            
            start_freq, stop_freq = 0.0, 0.0
            if self.log_fft_var.get():
                self.device.write("FORM:DATA REAL,32")
                self.device.write("FORM:BORD LSBF")
                start_freq = float(self.device.query("SPECtrum:FREQuency:STARt?"))
                stop_freq = float(self.device.query("SPECtrum:FREQuency:STOP?"))

            x_inc = 1.0
            if self.log_wave_var.get():
                try:
                    x_inc = float(self.device.query("CHAN1:DATA:XINC?"))
                except pyvisa.errors.VisaIOError:
                    print("Warnung: Konnte X-Increment nicht lesen. Standardwert 1.0 wird verwendet.")
                    x_inc = 1.0

            h5_file = h5py.File(os.path.join(self.log_dir, "datalog.h5"), "w")
            
            # --- HIER: Mess-Datum und Uhrzeit als Attribute speichern ---
            now = datetime.now()
            h5_file.attrs['date'] = now.strftime("%d.%m.%Y")
            h5_file.attrs['time'] = now.strftime("%H:%M:%S")
            # -------------------------------------------------------------
            
            ds_time = h5_file.create_dataset("time", (0,), maxshape=(None,), dtype='f8')
            ds_stats = h5_file.create_dataset("stats", (0, len(self.labels)), maxshape=(None, len(self.labels)), dtype='f8')
            
            h5_file.attrs['start_time'] = datetime.now().isoformat()
            h5_file.attrs['labels'] = ";".join(self.labels)
            h5_file.attrs['x_inc'] = x_inc
            
            ds_fft, ds_freq, ds_fft_avg = None, None, None
            event_timestamps, event_texts = [], []

            has_avg_fft = False
            if self.log_fft_var.get():
                try:
                    self.device.query_binary_values("SPECtrum:WAVeform:AVERage:DATA?", datatype='f', container=np.ndarray)
                    has_avg_fft = True
                except pyvisa.errors.VisaIOError:
                    print("Info: Average FFT Trace ist am Oszilloskop nicht aktiv.")

            row_idx = 0
            ds_wave = None
            
            if self.log_wave_var.get():
                self.device.write("FORM:DATA REAL,32")
                self.device.write("FORM:BORD LSBF")
            
            while self.running:
                loop_start = time.time()
                
                try:
                    self.device.query("*OPC?")
                except pyvisa.errors.VisaIOError:
                    print("Timeout: Oszilloskop braucht zu lange.")
                    time.sleep(0.1)
                    continue

                current_time_str = datetime.now().strftime("%H:%M:%S")
                rel_time = time.time() - self.start_time
                
                # 1. Stats abfragen
                vals = []
                for i in range(1, 8):
                    try:
                        val = float(self.device.query(f"MEAS{i}:RES:ACT?"))
                        vals.append(0.0 if val > 1e20 else val)
                    except: vals.append(0.0)
                
                # 2. FFT & THD
                fft_curr_data = None
                fft_avg_data = None
                frequencies = None
                thd_val = 0.0

                if self.log_fft_var.get():
                    try:
                        fft_curr_data = self.device.query_binary_values("SPECtrum:WAVeform:SPECtrum:DATA?", datatype='f', container=np.ndarray)
                        
                        if has_avg_fft:
                            fft_avg_data = self.device.query_binary_values("SPECtrum:WAVeform:AVERage:DATA?", datatype='f', container=np.ndarray)

                        frequencies = np.linspace(start_freq, stop_freq, len(fft_curr_data))
                        thd_val = calculate_thd(frequencies, fft_curr_data)
                        
                        if ds_fft is None:
                            ds_fft = h5_file.create_dataset("fft", (0, len(fft_curr_data)), maxshape=(None, len(fft_curr_data)), dtype='f4', compression="gzip")
                            ds_freq = h5_file.create_dataset("freq", data=frequencies)
                            if has_avg_fft:
                                ds_fft_avg = h5_file.create_dataset("fft_avg", (0, len(fft_avg_data)), maxshape=(None, len(fft_avg_data)), dtype='f4', compression="gzip")
                        
                        ds_fft.resize((row_idx + 1, len(fft_curr_data)))
                        ds_fft[row_idx] = fft_curr_data
                        
                        if has_avg_fft:
                            ds_fft_avg.resize((row_idx + 1, len(fft_avg_data)))
                            ds_fft_avg[row_idx] = fft_avg_data

                    except Exception as e:
                        print(f"FFT Error: {e}")

                vals.append(thd_val)
                
                # 3. Wellenform
                wave_data = None
                if self.log_wave_var.get():
                    try:
                        wave_data = self.device.query_binary_values("CHAN1:DATA?", datatype='f', container=np.ndarray)
                        
                        if ds_wave is None:
                            ds_wave = h5_file.create_dataset("wave", (0, len(wave_data)), maxshape=(None, len(wave_data)), 
                                                             dtype='f4', compression="gzip")
                        
                        ds_wave.resize((row_idx + 1, len(wave_data)))
                        ds_wave[row_idx] = wave_data
                    except Exception as e:
                        print(f"Waveform Error: {e}")
                
                # Statistik in HDF5 speichern
                ds_time.resize((row_idx + 1,))
                ds_time[row_idx] = rel_time
                ds_stats.resize((row_idx + 1, len(self.labels)))
                ds_stats[row_idx] = vals
                h5_file.flush()

                # Event-Marker abarbeiten
                while not self.event_queue.empty():
                    event_txt = self.event_queue.get()
                    event_timestamps.append(rel_time)
                    event_texts.append(event_txt.encode('utf-8'))

                # Daten an GUI senden
                self.data_queue.put({
                    'time': current_time_str, 
                    'rel': rel_time, 
                    'vals': vals, 
                    'fft_curr': fft_curr_data, 
                    'fft_avg': fft_avg_data,
                    'fft_freq': frequencies,
                    'wave': wave_data,
                    'x_inc': x_inc
                })
                
                row_idx += 1
                try: interval = float(self.interval_entry.get())
                except: interval = 1.0
                sleep_time = interval - (time.time() - loop_start)
                if sleep_time > 0: time.sleep(sleep_time)

        except Exception as e:
            print(f"Logger Error: {e}")
            self.running = False
        finally:
            if self.device: 
                try: self.device.close()
                except: pass
            
            if h5_file is not None:
                # Kommentar speichern
                comment = self.comment_entry.get().strip()
                h5_file.attrs['comment'] = comment if comment else "Kein Kommentar"
                if event_timestamps:
                    h5_file.create_dataset("events_time", data=np.array(event_timestamps))
                    dt = h5py.string_dtype(encoding='utf-8')
                    h5_file.create_dataset("events_text", data=np.array(event_texts, dtype=dt))
                h5_file.close()

    def update_gui(self):
        if not self.winfo_exists(): return
        needs_redraw = False
        
        while not self.data_queue.empty():
            data = self.data_queue.get()
            self.time_data.append(data['rel'])
            
            for i, label in enumerate(self.labels):
                val = data['vals'][i]
                self.data_storage[label].append(val)
                self.lines[label].set_data(list(self.time_data), list(self.data_storage[label]))
                
                fmt = f"{val:.2f}%" if "THD" in label else f"{val:.3f}"
                self.val_labels[label].configure(text=f"{label}: {fmt}")

            if data.get('wave') is not None:
                wave = data['wave']
                x_inc = data.get('x_inc', 1.0)
                
                x = np.arange(len(wave)) * x_inc * 1000
                dec = 2 if len(wave) > 5000 else 1

                self.line_wave.set_data(x[::dec], wave[::dec])
                self.ax_wave.set_xlim(x[0], x[-1])
                self.ax_wave.relim()
                self.ax_wave.autoscale_view(scalex=False, scaley=True)
            
            if data['fft_curr'] is not None:
                dec = 5 if len(data['fft_freq']) > 5000 else 1
                freq_scale = data['fft_freq'][::dec] / 1e3 if data['fft_freq'][-1] >= 1e5 else data['fft_freq'][::dec]
                
                self.line_fft_curr.set_data(freq_scale, data['fft_curr'][::dec])
                
                if data.get('fft_avg') is not None:
                    self.line_fft_avg.set_data(freq_scale, data['fft_avg'][::dec])
                
                self.ax_fft.relim()
                self.ax_fft.autoscale_view()
                
            needs_redraw = True

        if needs_redraw:
            for ax in [self.ax_stat, self.ax_peak, self.ax_pulse]:
                ax.relim()
                ax.autoscale_view()
            self.canvas.draw_idle()
            
        self.after(100, self.update_gui)