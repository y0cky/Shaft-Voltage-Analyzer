import os
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import numpy as np
import h5py

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

class SyncViewerFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        
        self.wave_data = None
        self.x_inc = 1.0
        
        self.h5_file = None
        self.time_data = []
        self.stat_data = []
        self.fft_data = None
        self.fft_avg_data = None
        self.fft_freq = None
        self.events_time = []
        self.events_text = []
        
        self.current_index = 0

        self.grid_columnconfigure(0, weight=0, minsize=280)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_plot()

    def show_boxplot(self):
        if self.stat_data is None or len(self.stat_data) == 0:
            messagebox.showwarning("Hinweis", "Keine statistischen Daten geladen.")
            return

        fig, ax = plt.subplots(figsize=(10, 6))
        fig.patch.set_facecolor('#2b2b2b')
        ax.set_facecolor('#333333')
        
        data_to_plot = [self.stat_data[:, i] for i in range(self.stat_data.shape[1])]
        
        num_cols = len(data_to_plot)
        current_labels = self.labels.copy()
        
        if len(current_labels) < num_cols:
            for i in range(len(current_labels), num_cols):
                current_labels.append(f"Var_{i}")
        elif len(current_labels) > num_cols:
            current_labels = current_labels[:num_cols]
            
        bp = ax.boxplot(data_to_plot, labels=current_labels, patch_artist=True)
        
        for box in bp['boxes']:
            box.set(facecolor='#1f77b4', color='white', alpha=0.7)
        for median in bp['medians']:
            median.set(color='yellow', linewidth=2)
            
        ax.set_title("Statistische Verteilung der Messwerte", color='white', fontsize=12)
        ax.tick_params(colors='white', labelsize=9)
        plt.xticks(rotation=45, ha='right')
        plt.grid(True, linestyle=":", alpha=0.3, color='gray')
        
        plt.tight_layout()
        plt.show()

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(self.sidebar, text="Sync Offline Viewer", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        ctk.CTkButton(self.sidebar, text="HDF5 Log-Ordner laden", command=self.load_log_folder, font=ctk.CTkFont(weight="bold")).pack(fill="x", padx=15, pady=10)
        
        self.folder_label = ctk.CTkLabel(self.sidebar, text="Keine Daten geladen", text_color="gray", font=ctk.CTkFont(size=11), justify="left")
        self.folder_label.pack(fill="x", padx=15)

        self.time_label = ctk.CTkLabel(self.sidebar, text="Rel. Zeit: 0.00s", font=ctk.CTkFont(weight="bold"), anchor="w")
        self.time_label.pack(fill="x", padx=15, pady=10)

        # Slider & Nav
        ctk.CTkLabel(self.sidebar, text="Zeitleiste:").pack(fill="x", padx=15, anchor="w")
        self.time_slider = ctk.CTkSlider(self.sidebar, from_=0, to=1, command=self.on_slider_change, state="disabled")
        self.time_slider.pack(fill="x", padx=15, pady=5)
        
        nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav_frame.pack(fill="x", padx=15, pady=5)
        self.btn_prev = ctk.CTkButton(nav_frame, text="<", width=50, command=self.step_prev, state="disabled")
        self.btn_prev.pack(side="left", fill="x", expand=True, padx=(0,2))
        self.btn_next = ctk.CTkButton(nav_frame, text=">", width=50, command=self.step_next, state="disabled")
        self.btn_next.pack(side="right", fill="x", expand=True, padx=(2,0))

        # Event Anzeige
        ctk.CTkLabel(self.sidebar, text="Verfügbare Events:", font=ctk.CTkFont(weight="bold")).pack(pady=(15, 0))
        self.event_listbox = tk.Listbox(self.sidebar, height=5, bg="#333333", fg="white", highlightthickness=0)
        self.event_listbox.pack(fill="x", padx=15, pady=5)
        self.event_listbox.bind('<<ListboxSelect>>', self.jump_to_event)

        # Stats
        ctk.CTkLabel(self.sidebar, text="--- Messwerte ---", font=ctk.CTkFont(size=11, weight="bold")).pack(pady=(20, 5))
        self.labels = ["RMS", "MEAN", "STD", "PEAK+", "PEAK-", "POS_PULSE", "NEG_PULSE", "THD (%)"]
        self.val_labels = {}
        for label in self.labels:
            lbl = ctk.CTkLabel(self.sidebar, text=f"{label}: ---", font=("Consolas", 14), anchor="w")
            lbl.pack(fill="x", padx=20, pady=1)
            self.val_labels[label] = lbl

        ctk.CTkButton(self.sidebar, text="Statistik-Boxplot anzeigen", 
                      command=self.show_boxplot, fg_color="#444444").pack(fill="x", padx=15, pady=20)

    def _build_plot(self):
        self.plot_frame = ctk.CTkFrame(self, corner_radius=10)
        self.plot_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.plot_frame.grid_columnconfigure(0, weight=1)
        self.plot_frame.grid_rowconfigure(0, weight=1)

        self.fig = Figure(figsize=(8, 11), dpi=90)
        
        self.ax_wave = self.fig.add_subplot(311)
        self.ax_wave.set_title("Wellenform")
        self.ax_wave.set_xlabel("Zeit (ms)")
        self.ax_wave.grid(True, linestyle=":", alpha=0.6)
        self.line_wave, = self.ax_wave.plot([], [], color='red')
        
        self.ax = self.fig.add_subplot(312)
        self.ax.set_title("FFT Spektrum")
        self.ax.set_ylabel("Amplitude (dB)")
        self.ax.grid(True, linestyle=":", alpha=0.6)
        self.line_fft, = self.ax.plot([], [], color='#1f77b4', label="Aktuell")
        self.line_fft_avg, = self.ax.plot([], [], color='#ff7f0e', label="Average", linewidth=1.5)
        self.ax.legend(loc="upper right")

        self.ax_waterfall = self.fig.add_subplot(313)
        self.ax_waterfall.set_title("Spektrogramm (Wasserfall)")
        self.ax_waterfall.set_xlabel("Frequenz")
        self.ax_waterfall.set_ylabel("Zeit (s)")
        
        self.fig.tight_layout(pad=2.0)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

    def load_log_folder(self):
        # Zeige standardmäßig den data-Ordner an, falls vorhanden
        initial_dir = os.path.join(os.getcwd(), "data") if os.path.exists("data") else "/"
        folder_path = filedialog.askdirectory(initialdir=initial_dir)
        if not folder_path: return
        
        h5_path = os.path.join(folder_path, "datalog.h5")
        if not os.path.exists(h5_path):
            messagebox.showerror("Fehler", "Ausgewählter Ordner enthält keine 'datalog.h5'!")
            return
            
        try:
            self.h5_file = h5py.File(h5_path, "r")
            self.time_data = self.h5_file["time"][:]
            self.stat_data = self.h5_file["stats"][:]
            
            self.x_inc = self.h5_file.attrs.get('x_inc', 1.0)
            
            if 'labels' in self.h5_file.attrs:
                self.labels = self.h5_file.attrs['labels'].split(";")
            
            if "fft" in self.h5_file:
                self.fft_data = self.h5_file["fft"][:]
                self.fft_freq = self.h5_file["freq"][:]
                
                if "fft_avg" in self.h5_file:
                    self.fft_avg_data = self.h5_file["fft_avg"][:]
                else:
                    self.fft_avg_data = None
                
                self.render_waterfall()
            else:
                self.fft_data = None
                self.fft_avg_data = None
                self.ax_waterfall.clear()
                self.ax_waterfall.set_title("Keine FFT Daten für Wasserfall")

            if "wave" in self.h5_file:
                self.wave_data = self.h5_file["wave"][:]
            else:
                self.wave_data = None
            
            self.event_listbox.delete(0, tk.END)
            self.events_time = []
            if "events_time" in self.h5_file:
                self.events_time = self.h5_file["events_time"][:]
                self.events_text = self.h5_file["events_text"][:]
                for t, txt in zip(self.events_time, self.events_text):
                    decoded_txt = txt.decode('utf-8') if isinstance(txt, bytes) else txt
                    self.event_listbox.insert(tk.END, f"{t:.1f}s: {decoded_txt}")

            max_idx = len(self.time_data) - 1
            self.folder_label.configure(text=f"Ordner: {os.path.basename(folder_path)}\n{max_idx+1} Datenpunkte")
            
            if max_idx > 0:
                self.time_slider.configure(state="normal", from_=0, to=max_idx, number_of_steps=max_idx)
                self.btn_prev.configure(state="normal")
                self.btn_next.configure(state="normal")
            else:
                self.time_slider.configure(state="disabled")
                
            self.time_slider.set(0)
            self.update_view(0)
            
        except Exception as e:
            messagebox.showerror("Fehler", f"Konnte HDF5 nicht laden:\n{e}")

    def render_waterfall(self):
        self.ax_waterfall.clear()
        if self.fft_data is None or len(self.fft_data) == 0: return
        
        freq_scale = self.fft_freq / 1e3 if self.fft_freq[-1] >= 1e5 else self.fft_freq
        self.ax_waterfall.set_xlabel("Frequenz (kHz)" if self.fft_freq[-1] >= 1e5 else "Frequenz (Hz)")
        self.ax_waterfall.set_ylabel("Zeit (s)")
        
        dec = 10 if len(freq_scale) > 2000 else 1 
        
        X, Y = np.meshgrid(freq_scale[::dec], self.time_data)
        
        mesh = self.ax_waterfall.pcolormesh(X, Y, self.fft_data[:, ::dec], shading='nearest', cmap='viridis')
        
        self.waterfall_line = self.ax_waterfall.axhline(self.time_data[0], color='red', linewidth=2)
        
        self.ax_waterfall.set_title("Spektrogramm (Wasserfall)")
        self.canvas.draw_idle()

    def on_slider_change(self, value):
        idx = int(round(value))
        if idx != self.current_index: 
            self.update_view(idx)

    def step_prev(self):
        if self.current_index > 0:
            self.time_slider.set(self.current_index - 1)
            self.update_view(self.current_index - 1)

    def step_next(self):
        if self.current_index < len(self.time_data) - 1:
            self.time_slider.set(self.current_index + 1)
            self.update_view(self.current_index + 1)

    def jump_to_event(self, event):
        selection = self.event_listbox.curselection()
        if not selection: return
        
        target_time = self.events_time[selection[0]]
        idx = (np.abs(self.time_data - target_time)).argmin()
        self.time_slider.set(idx)
        self.update_view(idx)

    def update_view(self, index):
        if index < 0 or index >= len(self.time_data): return
        self.current_index = index
        
        rel_time = self.time_data[index]
        vals = self.stat_data[index]
        
        self.time_label.configure(text=f"Rel. Zeit: {rel_time:.2f}s")
        
        for i, label in enumerate(self.labels):
            if i < len(vals):
                val = vals[i]
                fmt = f"{val:.2f}%" if "THD" in label else f"{val:.3f}"
                if label in self.val_labels:
                    self.val_labels[label].configure(text=f"{label}: {fmt}")

        if self.fft_data is not None:
            freq_scale = self.fft_freq / 1e3 if self.fft_freq[-1] >= 1e5 else self.fft_freq
            curr = self.fft_data[index]
            
            dec = 5 if len(freq_scale) > 5000 else 1
            self.line_fft.set_data(freq_scale[::dec], curr[::dec])
            
            if self.fft_avg_data is not None and index < len(self.fft_avg_data):
                avg = self.fft_avg_data[index]
                self.line_fft_avg.set_data(freq_scale[::dec], avg[::dec])
            else:
                self.line_fft_avg.set_data([], [])
            
            self.ax.set_xlim(freq_scale[0], freq_scale[-1])
            self.ax.set_ylim(np.min(curr)-10, np.max(curr)+10)
            self.ax.set_xlabel("Frequenz (kHz)" if self.fft_freq[-1] >= 1e5 else "Frequenz (Hz)")
            
            if hasattr(self, 'waterfall_line'):
                self.waterfall_line.set_ydata([rel_time, rel_time])
                
        if self.wave_data is not None and index < len(self.wave_data):
            wave = self.wave_data[index]
            
            x = np.arange(len(wave)) * self.x_inc * 1000
            
            dec = 2 if len(wave) > 5000 else 1
            self.line_wave.set_data(x[::dec], wave[::dec])
            self.ax_wave.set_xlim(x[0], x[-1])
            self.ax_wave.set_ylim(np.min(wave) * 1.1, np.max(wave) * 1.1)
        
        self.canvas.draw_idle()