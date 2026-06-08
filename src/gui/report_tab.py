import os
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import numpy as np
import h5py
import base64
from io import BytesIO
from datetime import datetime
import subprocess
import matplotlib.pyplot as plt

class SyncReportFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)

        self.path_without = None
        self.path_with = None

        self._build_ui()

    def _build_ui(self):
        title_label = ctk.CTkLabel(self, text="HDF5 Wellenform & FFT Analysator", font=ctk.CTkFont(size=20, weight="bold"))
        title_label.pack(pady=(15, 5))

        subtitle_label = ctk.CTkLabel(self, text="Vergleich von Zeitbereich & Spektrum in einem kombinierten Bericht", text_color="gray")
        subtitle_label.pack(pady=(0, 15))

        file_frame = ctk.CTkFrame(self, corner_radius=10)
        file_frame.pack(fill="x", padx=40, pady=10)

        # 1. Ohne Ableitsystem
        ctk.CTkLabel(file_frame, text="1. Referenz-Messung (OHNE Ableitsystem):", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=20, pady=(15, 5))
        self.btn_without = ctk.CTkButton(file_frame, text="Datei laden (.h5)", command=self.load_without, fg_color="#cb4b16", hover_color="#a03b10")
        self.btn_without.grid(row=1, column=0, padx=20, pady=(0, 15), sticky="w")
        self.lbl_without = ctk.CTkLabel(file_frame, text="Keine Datei ausgewählt", text_color="gray", justify="left")
        self.lbl_without.grid(row=1, column=1, padx=10, pady=(0, 15), sticky="w")

        # 2. Mit Ableitsystem
        ctk.CTkLabel(file_frame, text="2. Optimierte Messung (MIT Ableitsystem):", font=ctk.CTkFont(weight="bold")).grid(row=2, column=0, sticky="w", padx=20, pady=(15, 5))
        self.btn_with = ctk.CTkButton(file_frame, text="Datei laden (.h5)", command=self.load_with, fg_color="#2aa198", hover_color="#207a73")
        self.btn_with.grid(row=3, column=0, padx=20, pady=(0, 15), sticky="w")
        self.lbl_with = ctk.CTkLabel(file_frame, text="Keine Datei ausgewählt", text_color="gray", justify="left")
        self.lbl_with.grid(row=3, column=1, padx=10, pady=(0, 15), sticky="w")

        options_frame = ctk.CTkFrame(self, corner_radius=10)
        options_frame.pack(fill="x", padx=40, pady=15)
        
        ctk.CTkLabel(options_frame, text="Zusätzliche Berichtsnotiz (optional):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=(10,5))
        self.txt_comment = ctk.CTkEntry(options_frame, placeholder_text="z.B. Betrachtung bei 1500 U/min...", width=580)
        self.txt_comment.pack(padx=20, pady=(0,15))

        self.btn_report_full = ctk.CTkButton(self, text="📑 Vollständigen Vergleichsbericht generieren (Wave + FFT)", font=ctk.CTkFont(size=15, weight="bold"),
                                             height=45, width=400, fg_color="#6b46c1", hover_color="#553c9a", command=self.generate_full_report)
        self.btn_report_full.pack(pady=15)

    def load_without(self):
        path = filedialog.askopenfilename(filetypes=[("HDF5-Dateien", "*.h5")])
        if path:
            self.path_without = path
            self.lbl_without.configure(text=os.path.basename(path), text_color="white")

    def load_with(self):
        path = filedialog.askopenfilename(filetypes=[("HDF5-Dateien", "*.h5")])
        if path:
            self.path_with = path
            self.lbl_with.configure(text=os.path.basename(path), text_color="white")

    def _compute_change_dynamics(self, wo_val, w_val, is_positive_good=False):
        if wo_val == 0:
            return "0.0%", "badge-neutral", "#4a5568"
        pct_change = ((w_val - wo_val) / abs(wo_val)) * 100
        if (pct_change < -0.05 and not is_positive_good) or (pct_change > 0.05 and is_positive_good):
            sign = "+" if pct_change > 0 else ""
            return f"{sign}{pct_change:.1f}%", "badge-improvement", "#2f855a"
        elif (pct_change > 0.05 and not is_positive_good) or (pct_change < -0.05 and is_positive_good):
            sign = "+" if pct_change > 0 else ""
            return f"{sign}{pct_change:.1f}%", "badge-degradation", "#e53e3e"
        else:
            return "0.0%", "badge-neutral", "#4a5568"

    def _extract_wave_data(self, file_path):
        metrics = {}
        with h5py.File(file_path, "r") as h5:
            if "wave" not in h5:
                raise ValueError(f"Datei {os.path.basename(file_path)} enthält keine 'wave' Daten.")
            
            wave_matrix = h5["wave"][:]
            metrics["wave_matrix"] = wave_matrix
            x_inc = h5.attrs.get("x_inc", 1.0)
            metrics["time_scale"] = np.arange(wave_matrix.shape[1]) * x_inc * 1000 
            metrics["time"] = h5["time"][:] if "time" in h5 else np.arange(wave_matrix.shape[0])
            
            if "stats" in h5 and "labels" in h5.attrs:
                stats = h5["stats"][:]
                labels = h5.attrs["labels"]
                if isinstance(labels, bytes):
                    labels = labels.decode('utf-8')
                labels_list = labels.split(";")
                
                def get_stat(name):
                    idx = next((i for i, l in enumerate(labels_list) if name.upper() in l.upper()), None)
                    return stats[:, idx].mean() if idx is not None else 0.0
                metrics["rms"] = get_stat("RMS")
                metrics["peak_pos"] = get_stat("PEAK+")
                metrics["peak_neg"] = get_stat("PEAK-")
                metrics["vpp"] = metrics["peak_pos"] - metrics["peak_neg"]
            else:
                metrics["rms"] = np.mean(np.sqrt(np.mean(wave_matrix**2, axis=1)))
                metrics["peak_pos"] = np.mean(np.max(wave_matrix, axis=1))
                metrics["peak_neg"] = np.mean(np.min(wave_matrix, axis=1))
                metrics["vpp"] = metrics["peak_pos"] - metrics["peak_neg"]

            metrics["envelope_max"] = np.max(wave_matrix, axis=0)
            metrics["envelope_min"] = np.min(wave_matrix, axis=0)
            max_idx = np.argmax(np.max(np.abs(wave_matrix), axis=1))
            metrics["wave_example"] = wave_matrix[max_idx]
        return metrics

    def _extract_fft_data(self, file_path):
        metrics = {}
        with h5py.File(file_path, "r") as h5:
            if "fft" not in h5:
                raise ValueError(f"Datei {os.path.basename(file_path)} enthält keine 'fft' Daten.")
            
            metrics["fft_matrix"] = h5["fft"][:]
            metrics["freq"] = h5["freq"][:] if "freq" in h5 else np.arange(metrics["fft_matrix"].shape[1])
            metrics["time"] = h5["time"][:] if "time" in h5 else np.arange(metrics["fft_matrix"].shape[0])
            metrics["fft_avg"] = np.mean(metrics["fft_matrix"], axis=0)
                
            if "stats" in h5 and "labels" in h5.attrs:
                stats = h5["stats"][:]
                labels = h5.attrs["labels"]
                if isinstance(labels, bytes):
                    labels = labels.decode('utf-8')
                labels_list = labels.split(";")
                thd_idx = next((i for i, l in enumerate(labels_list) if "THD" in l.upper()), None)
                metrics["thd"] = stats[:, thd_idx] if thd_idx is not None else np.zeros(len(stats))
            else:
                metrics["thd"] = np.zeros(len(metrics["time"]))
        return metrics

    def _generate_wave_plots(self, m_wo, m_w):
        fig = plt.figure(figsize=(10, 15), constrained_layout=True)
        fig.patch.set_facecolor("#ffffff")
        
        min_len = min(len(m_wo["time_scale"]), len(m_w["time_scale"]))
        t_scale = m_wo["time_scale"][:min_len]
        
        ax1 = fig.add_subplot(311)
        ax1.fill_between(t_scale, m_wo["envelope_min"][:min_len], m_wo["envelope_max"][:min_len], color="#e53e3e", alpha=0.3, label="Ref. Rauschband (Min/Max)")
        ax1.fill_between(t_scale, m_w["envelope_min"][:min_len], m_w["envelope_max"][:min_len], color="#2b6cb0", alpha=0.5, label="Opt. Rauschband (Min/Max)")
        ax1.plot(t_scale, m_wo["wave_example"][:min_len], color="#c53030", alpha=0.9, linewidth=1, label="Ref. Peak-Beispiel")
        ax1.plot(t_scale, m_w["wave_example"][:min_len], color="#2c5282", alpha=1.0, linewidth=1, label="Opt. Peak-Beispiel")
        ax1.set_ylabel("Spannung (V)", fontweight="bold")
        ax1.set_title("1. Wellenform-Hüllkurven & Absolutes Maximum", fontsize=12, fontweight="bold", color="#1a365d")
        ax1.legend(loc="upper right")

        min_rows = min(m_wo["wave_matrix"].shape[0], m_w["wave_matrix"].shape[0])
        dec_x = max(1, len(t_scale) // 1500) 
        t_dec = t_scale[::dec_x]
        time_y = m_wo["time"][:min_rows]
        X, Y = np.meshgrid(t_dec, time_y)
        mat_wo = m_wo["wave_matrix"][:min_rows, :min_len:dec_x]
        mat_w = m_w["wave_matrix"][:min_rows, :min_len:dec_x]
        
        # --- START DER OPTIMIERUNG FÜR DAS OSZILLOGRAMM ---
        # 99.5-Perzentil statt absolutes Maximum ignoriert einzelne Ausreißer
        v_limit_wo = np.percentile(np.abs(mat_wo), 99.5)
        v_limit_w  = np.percentile(np.abs(mat_w), 99.5)
        
        v_abs_max = max(v_limit_wo, v_limit_w)
        
        # Verhindert, dass reines Rauschen bei perfekten Messungen extrem verstärkt wird
        if v_abs_max < 0.01: 
            v_abs_max = 0.01
        # --- ENDE DER OPTIMIERUNG ---

        ax3 = fig.add_subplot(312)
        # rasterized=True hinzugefügt
        ax3.pcolormesh(X, Y, mat_wo, shading="nearest", cmap="coolwarm", vmin=-v_abs_max, vmax=v_abs_max, rasterized=True)
        ax3.set_ylabel("Mess-Zeitpunkt (s)", fontweight="bold")
        ax3.set_title("2. Oszillogramm-Historie - OHNE Ableitsystem", fontsize=12, fontweight="bold", color="#1a365d")

        ax4 = fig.add_subplot(313)
        # rasterized=True hinzugefügt
        ax4.pcolormesh(X, Y, mat_w, shading="nearest", cmap="coolwarm", vmin=-v_abs_max, vmax=v_abs_max, rasterized=True)
        ax4.set_xlabel("Zeit (ms)", fontweight="bold")
        ax4.set_ylabel("Mess-Zeitpunkt (s)", fontweight="bold")
        ax4.set_title("3. Oszillogramm-Historie - MIT Ableitsystem", fontsize=12, fontweight="bold", color="#1a365d")

        for ax in [ax1, ax3, ax4]:
            ax.set_xlim(t_scale[0], t_scale[-1])
            ax.tick_params(colors="#2d3748", labelsize=9)
            if ax == ax1:
                ax.grid(True, linestyle=":", alpha=0.6, color="#a0aec0")
                
        buf = BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=140, facecolor="#ffffff")
        plt.close(fig)
        buf.seek(0)
        return f"data:image/png;base64,{base64.b64encode(buf.read()).decode('utf-8')}"

    def _generate_fft_plots(self, m_wo, m_w):
        # Gemeinsame Vorbereitungen
        freq_scale = m_wo["freq"] / 1e3 if m_wo["freq"][-1] >= 1e5 else m_wo["freq"]
        x_label = "Frequenz (kHz)" if m_wo["freq"][-1] >= 1e5 else "Frequenz (Hz)"
        
        min_rows = min(m_wo["fft_matrix"].shape[0], m_w["fft_matrix"].shape[0])
        dec_f = 10 if len(freq_scale) > 2000 else 1
        freq_dec = freq_scale[::dec_f]
        time_subset = m_wo["time"][:min_rows]
        X, Y = np.meshgrid(freq_dec, time_subset)
        
        mat_wo = m_wo["fft_matrix"][:min_rows, ::dec_f]
        mat_w = m_w["fft_matrix"][:min_rows, ::dec_f]
        vmin = min(mat_wo.min(), mat_w.min())
        vmax = max(mat_wo.max(), mat_w.max())

        # ==========================================
        # BILD 1: Liniendiagramme (Overlay & Dämpfung)
        # ==========================================
        fig1 = plt.figure(figsize=(10, 8), constrained_layout=True)
        fig1.patch.set_facecolor("#ffffff")

        ax1 = fig1.add_subplot(211)
        ax1.plot(freq_scale, m_wo["fft_avg"], color="#e53e3e", alpha=0.7, label="Ref. Ohne Ableitsystem", linewidth=1.2)
        ax1.plot(freq_scale, m_w["fft_avg"], color="#2b6cb0", alpha=0.8, label="Opt. Mit Ableitsystem", linewidth=1.2)
        ax1.set_ylabel("Amplitude (dB)", fontweight="bold")
        ax1.set_title("1. Gemitteltes Frequenzspektrum (FFT Overlay)", fontsize=12, fontweight="bold", color="#1a365d")
        ax1.legend(loc="upper right")

        ax2 = fig1.add_subplot(212)
        damping_db = m_wo["fft_avg"] - m_w["fft_avg"]
        ax2.fill_between(freq_scale, 0, damping_db, where=(damping_db >= 0), color='#48bb78', alpha=0.5, label="Dämpfungsgewinn")
        ax2.fill_between(freq_scale, 0, damping_db, where=(damping_db < 0), color='#f56565', alpha=0.5, label="Pegelerhöhung")
        ax2.plot(freq_scale, damping_db, color='#2d3748', linewidth=1)
        ax2.set_xlabel(x_label, fontweight='bold')
        ax2.set_ylabel("Dämpfung (dB)", fontweight='bold')
        ax2.set_title("2. Spektrales Dämpfungsprofil (Differenz Ref - Opt)", fontsize=12, fontweight='bold', color='#1a365d')
        ax2.legend(loc="upper right")

        for ax in [ax1, ax2]:
            ax.set_xlim(freq_scale[0], freq_scale[-1])
            ax.tick_params(colors="#2d3748", labelsize=9)
            ax.grid(True, linestyle=":", alpha=0.6, color="#a0aec0")

        buf1 = BytesIO()
        fig1.savefig(buf1, format="png", bbox_inches="tight", dpi=140, facecolor="#ffffff")
        plt.close(fig1)
        b64_1 = f"data:image/png;base64,{base64.b64encode(buf1.getvalue()).decode('utf-8')}"

        # ==========================================
        # BILD 2: Spektrogramme (Matrizen) -> mit rasterized=True !
        # ==========================================
        fig2 = plt.figure(figsize=(10, 14), constrained_layout=True)
        fig2.patch.set_facecolor("#ffffff")

        ax3 = fig2.add_subplot(311)
        diff_matrix = mat_wo - mat_w
        vmax_diff = np.max(np.abs(diff_matrix))
        ax3.pcolormesh(X, Y, diff_matrix, shading='nearest', cmap='bwr', vmin=-vmax_diff, vmax=vmax_diff, rasterized=True)
        ax3.set_ylabel("Zeit (s)", fontweight='bold')
        ax3.set_title("3. Differenz-Spektrogramm (Ref - Opt)", fontsize=12, fontweight='bold', color='#1a365d')

        ax4 = fig2.add_subplot(312)
        ax4.pcolormesh(X, Y, mat_wo, shading="nearest", cmap="turbo", vmin=vmin, vmax=vmax, rasterized=True)
        ax4.set_ylabel("Zeit (s)", fontweight="bold")
        ax4.set_title("4. Spektrogramm / Wasserfall - OHNE Ableitsystem", fontsize=12, fontweight="bold", color="#1a365d")

        ax5 = fig2.add_subplot(313)
        ax5.pcolormesh(X, Y, mat_w, shading="nearest", cmap="turbo", vmin=vmin, vmax=vmax, rasterized=True)
        ax5.set_xlabel(x_label, fontweight="bold")
        ax5.set_ylabel("Zeit (s)", fontweight="bold")
        ax5.set_title("5. Spektrogramm / Wasserfall - MIT Ableitsystem", fontsize=12, fontweight="bold", color="#1a365d")

        for ax in [ax3, ax4, ax5]:
            ax.set_xlim(freq_scale[0], freq_scale[-1])
            ax.tick_params(colors="#2d3748", labelsize=9)

        buf2 = BytesIO()
        fig2.savefig(buf2, format="png", bbox_inches="tight", dpi=140, facecolor="#ffffff")
        plt.close(fig2)
        b64_2 = f"data:image/png;base64,{base64.b64encode(buf2.getvalue()).decode('utf-8')}"

        return b64_1, b64_2

    def generate_full_report(self):
        if not self.path_without or not self.path_with:
            messagebox.showwarning("Fehler", "Bitte lade beide .h5 Dateien.")
            return

        self.btn_report_full.configure(text="Generiere Bericht... Bitte warten", state="disabled")
        self.update()

        try:
            w_wo = self._extract_wave_data(self.path_without)
            w_w = self._extract_wave_data(self.path_with)
            f_wo = self._extract_fft_data(self.path_without)
            f_w = self._extract_fft_data(self.path_with)

            txt_vpp, class_vpp, col_vpp = self._compute_change_dynamics(w_wo["vpp"], w_w["vpp"])
            txt_rms, class_rms, col_rms = self._compute_change_dynamics(w_wo["rms"], w_w["rms"])

            # Berechnung der Peak-Dynamik hinzufügen
            txt_peak_pos, class_peak_pos, col_peak_pos = self._compute_change_dynamics(w_wo["peak_pos"], w_w["peak_pos"])
            
            txt_thd, class_thd, col_thd = self._compute_change_dynamics(f_wo["thd"].mean(), f_w["thd"].mean())
            damping_profile = f_wo["fft_avg"] - f_w["fft_avg"]
            avg_broadband_damping = np.mean(damping_profile)

            # Definition der Zielwerte
            ideal_db = 5.0  # Ein Wert von 5 dB erreicht ca. 50% Balkenfüllung
            # Berechnung der prozentualen Füllung
            # Wir nutzen eine leicht gedämpfte lineare Skalierung, damit 
            # sehr hohe Werte nicht sofort über 100% schießen.
            abs_damping = abs(avg_broadband_damping)
            efficacy_pct = min(100, (abs_damping / ideal_db) * 50)

            wave_chart_b64 = self._generate_wave_plots(w_wo, w_w)
            fft_chart1_b64, fft_chart2_b64 = self._generate_fft_plots(f_wo, f_w)

            user_comment = self.txt_comment.get() if self.txt_comment.get() else "Kombinierte Zeitbereichs- & Spektralanalyse"
            current_time_str = datetime.now().strftime("%d.%m.%Y %H:%M")

            # Berechnung der Peak-Werte
            peak_wo = np.max(f_wo["fft_avg"])
            peak_w = np.max(f_w["fft_avg"])
            diff_peak = peak_w - peak_wo  # Negative Differenz ist gut (Dämpfung)

            # HIER WIRD DIE FARBE DEFINIERT
            if diff_peak < -0.5:
                col_peak = "#2f855a"  # Grün (Verbesserung)
            elif diff_peak > 0.5:
                col_peak = "#e53e3e"  # Rot (Verschlechterung)
            else:
                col_peak = "#4a5568"  # Grau (Neutral)

            

            css = """
            @media print { body { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
            body { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #2d3748; line-height: 1.5; font-size: 10pt; margin: 12mm; background-color: #ffffff; }
            *, *::before, *::after { box-sizing: border-box; }
            .header-table { width: 100%; border-collapse: collapse; margin-bottom: 20px; border-bottom: 3px solid #3182ce; }
            .header-table td { padding-bottom: 12px; vertical-align: bottom; }
            .report-title { font-size: 22pt; color: #2a4365; margin: 0; font-weight: 700; }
            .report-subtitle { font-size: 10pt; color: #4a5568; margin: 4px 0 0 0; text-transform: uppercase; font-weight: 600; }
            .kpi-grid { width: 100%; border-collapse: collapse; margin-bottom: 20px; table-layout: fixed; }
            .kpi-card { background-color: #f7fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; text-align: center; }
            .kpi-value { font-size: 16pt; font-weight: bold; margin: 5px 0; }
            .kpi-label { font-size: 8.5pt; text-transform: uppercase; color: #4a5568; font-weight: 600; }
            .badge-improvement { color: #2f855a; } 
            .badge-degradation { color: #e53e3e; }
            .badge-neutral { color: #4a5568; }
            h2 { font-size: 13pt; color: #2a4365; border-bottom: 2px solid #e2e8f0; padding-bottom: 4px; margin-top: 20px; margin-bottom: 12px; }
            .compare-table { width: 100%; border-collapse: collapse; margin-bottom: 15px; }
            .compare-table th { background-color: #edf2f7; color: #2d3748; text-align: left; padding: 8px; font-size: 9.5pt; font-weight: 600; border-bottom: 2px solid #cbd5e0; }
            .compare-table td { padding: 8px; border-bottom: 1px solid #e2e8f0; font-size: 9.5pt; }
            .chart-box { border: 1px solid #e2e8f0; padding: 10px; margin-top: 10px; text-align: center; page-break-inside: avoid; break-inside: avoid; }
            .img-fluid { max-width: 100%; height: auto; display: block; margin: 0 auto; }
            .page-break { page-break-before: always; }
            .progress-bar-container { background-color: #e2e8f0; border-radius: 10px; height: 15px; width: 100%; margin: 10px 0; overflow: hidden; }
            .progress-bar-fill { height: 100%; background-color: #38a169; width: 0%; transition: width 1s; }
            """

            html_content = f"""
            <!DOCTYPE html>
            <html lang="de">
            <head><meta charset="UTF-8"><style>{css}</style></head>
            <body>
                <table class="header-table">
                    <tr>
                        <td>
                            <div class="report-title">Wirksamkeit des Ableitsystems</div>
                            <div class="report-subtitle">Wellenform (Zeit) & FFT (Frequenz)</div>
                        </td>
                        <td style="text-align: right; color: #4a5568; font-size: 9pt;">
                            <strong>Berichtsdatum:</strong> {current_time_str}<br>
                            <strong>Status:</strong> Messdaten kombiniert ausgewertet
                        </td>
                    </tr>
                </table>
                
                <p style="font-size: 9.5pt; color: #4a5568; font-style: italic; margin-top:-10px; margin-bottom: 15px;">Fokus / Notiz: {user_comment}</p>

                <table class="kpi-grid">
                    <tr>
                        <td><div class="kpi-card"><div class="kpi-label">Vpp (Spitze-Spitze)</div><div class="kpi-value {class_vpp}">{txt_vpp}</div></div></td>
                        <td><div class="kpi-card"><div class="kpi-label">RMS (Effektivwert)</div><div class="kpi-value {class_rms}">{txt_rms}</div></div></td>
                        <td><div class="kpi-card"><div class="kpi-label">Breitband-Dämpfung</div><div class="kpi-value" style="color:#2f855a;">{avg_broadband_damping:+.1f} dB</div></div></td>
                        <td><div class="kpi-card"><div class="kpi-label">THD (Oberwellen)</div><div class="kpi-value {class_thd}">{txt_thd}</div></div></td>
                    </tr>
                </table>

                <div style="margin: 20px 0;">
                    <div style="display: flex; justify-content: space-between; font-weight:bold; font-size: 9pt;">
                        <span>System-Effizienz (Dämpfung)</span>
                        <span>{efficacy_pct:.0f}%</span>
                    </div>
                    <div class="progress-bar-container">
                        <div class="progress-bar-fill" style="width: {efficacy_pct}%; background-color: #38a169;"></div>
                        <div style="text-align: right; font-size: 8pt; color: #718096;">{abs_damping:.1f} dB Dämpfung erreicht</div>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 8pt; color: #718096;">
                        <span>Keine Wirkung</span>
                        <span>Exzellente Ableitung (10db)</span>
                    </div>
                </div>
                
                <h2>1. Zeitbereichsanalyse (Wellenform)</h2>
                <table class="compare-table">
                    <thead><tr><th>Parameter</th><th>Ohne Ableitsystem (Ref.)</th><th>Mit Ableitsystem (Opt.)</th></tr></thead>
                    <tbody>
                        <tr><td><strong>Spitze-Spitze Spannung (Vpp)</strong></td><td>{w_wo["vpp"]:.2f} V</td><td>{w_w["vpp"]:.2f} V <span style="font-weight:bold; color:{col_vpp};">({txt_vpp})</span></td></tr>
                        <tr><td><strong>Effektivspannung (RMS)</strong></td><td>{w_wo["rms"]:.2f} V</td><td>{w_w["rms"]:.2f} V <span style="font-weight:bold; color:{col_rms};">({txt_rms})</span></td></tr>
                        <tr><td><strong>Max. Positiver Peak</strong></td><td>{w_wo["peak_pos"]:.2f} V</td><td>{w_w["peak_pos"]:.2f} V <span style="font-weight:bold; color:{col_peak_pos};">({txt_peak_pos})</span></td></tr>
                    </tbody>
                </table>
                <div class="chart-box"><img src="{wave_chart_b64}" class="img-fluid" /></div>

                <div class="page-break"></div>
                <h2>2. Spektralanalyse (FFT) - Pegel & Dämpfung</h2>
                <table class="compare-table">
                    <thead><tr><th>Parameter</th><th>Ohne Ableitsystem (Ref.)</th><th>Mit Ableitsystem (Opt.)</th></tr></thead>
                    <tbody>
                        <tr><td><strong>Mittlerer Klirrfaktor (THD &mu;)</strong></td><td>{f_wo["thd"].mean():.2f} %</td><td>{f_w["thd"].mean():.2f} % <span style="font-weight:bold; color:{col_thd};">({txt_thd})</span></td></tr>
                        <tr><td><strong>Absoluter Spektral-Peak</strong></td><td>{np.max(f_wo["fft_avg"]):.1f} dB</td><td>{np.max(f_w["fft_avg"]):.1f} dB <span style="font-weight:bold; color:{col_peak};">({diff_peak:+.1f} dB)</span></td></tr>
                    </tbody>
                </table>
                <div class="chart-box"><img src="{fft_chart1_b64}" class="img-fluid" /></div>

                <div class="page-break"></div>
                
                <h2>3. Spektralanalyse (FFT) - Spektrogramme</h2>
                <div class="chart-box"><img src="{fft_chart2_b64}" class="img-fluid" /></div>
            </body>
            </html>
            """
            
            temp_html = os.path.join(os.getcwd(), "temp_full_report.html")
            output_filename = f"Kombinierter_Bericht_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            output_path = os.path.join(os.getcwd(), output_filename)

            with open(temp_html, "w", encoding="utf-8") as f:
                f.write(html_content)

            edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
            if not os.path.exists(edge_path):
                edge_path = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

            cmd = [
                edge_path, "--headless", "--disable-gpu",
                f"--print-to-pdf={output_path}", "--no-margins", temp_html
            ]
            subprocess.run(cmd, check=True)

            if os.path.exists(temp_html):
                os.remove(temp_html)

            messagebox.showinfo("Erfolg", f"Kombinierter Bericht erfolgreich erstellt:\n{output_path}")
            if os.name == "nt":
                os.startfile(output_path)

        except Exception as e:
            messagebox.showerror("Fehler", f"Es gab ein Problem bei der Berichterstellung:\n{e}")
        finally:
            self.btn_report_full.configure(text="📑 Vollständigen Vergleichsbericht generieren (Wave + FFT)", state="normal")