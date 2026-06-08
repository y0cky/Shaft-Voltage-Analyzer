import os
import tkinter as tk
from tkinter import filedialog, messagebox
import tkinter.ttk as ttk  # <-- NEU für die Tabelle
import customtkinter as ctk
import numpy as np
import h5py
import base64
from io import BytesIO
from datetime import datetime
import subprocess  # Steuert Microsoft Edge für den PDF-Druck an

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# <-- NEU: Import für die SQLite-Datenbank
from src.utils.db_utils import MetadataDB

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

        groups = {
            "Spannung / Amplitude": [],
            "Prozent (z.B. THD)": [],
            "Anzahl / Pulse": []
        }
        
        current_labels = self.labels.copy()
        num_cols = self.stat_data.shape[1]
        
        if len(current_labels) < num_cols:
            for i in range(len(current_labels), num_cols):
                current_labels.append(f"Var_{i}")
        elif len(current_labels) > num_cols:
            current_labels = current_labels[:num_cols]

        for idx, label in enumerate(current_labels):
            label_upper = label.upper()
            if "THD" in label_upper or "%" in label_upper:
                groups["Prozent (z.B. THD)"].append(idx)
            elif "PULSE" in label_upper or "CNT" in label_upper or "ANZAHL" in label_upper:
                groups["Anzahl / Pulse"].append(idx)
            else:
                groups["Spannung / Amplitude"].append(idx)

        active_groups = {k: v for k, v in groups.items() if len(v) > 0}
        num_subplots = len(active_groups)

        fig, axes = plt.subplots(num_subplots, 1, figsize=(10, 4 * num_subplots), sharex=False)
        fig.patch.set_facecolor('#2b2b2b')
        
        if num_subplots == 1:
            axes = [axes]

        for ax, (group_name, indices) in zip(axes, active_groups.items()):
            ax.set_facecolor('#333333')
            
            data_to_plot = [self.stat_data[:, idx] for idx in indices]
            labels_to_plot = [current_labels[idx] for idx in indices]
            
            bp = ax.boxplot(data_to_plot, labels=labels_to_plot, patch_artist=True)
            
            for box in bp['boxes']:
                box.set(facecolor='#1f77b4', color='white', alpha=0.7)
            for median in bp['medians']:
                median.set(color='yellow', linewidth=2)
            for whisker in bp['whiskers']:
                whisker.set(color='white', linestyle='--')
            for cap in bp['caps']:
                cap.set(color='white')
            for flier in bp['fliers']:
                flier.set(marker='o', color='red', alpha=0.5)

            ax.set_ylabel(group_name, color='white', fontsize=10)
            ax.tick_params(colors='white', labelsize=9)
            ax.grid(True, linestyle=":", alpha=0.3, color='gray')
            ax.set_xticklabels(labels_to_plot, rotation=15, ha='right')

        fig.suptitle("Statistische Verteilung nach Datentyp", color='white', fontsize=14, weight='bold')
        
        plt.tight_layout()
        plt.show()
        
    def _generate_time_plots_base64_for_pdf(self):
        """Generiert die zeitlichen Verläufe der Messgrößen in 4 Subplots für den PDF-Bericht."""
        if self.stat_data is None or len(self.stat_data) == 0 or self.time_data is None or len(self.time_data) == 0:
            return ""

        fig, axes = plt.subplots(4, 1, figsize=(10, 12), sharex=True)
        fig.patch.set_facecolor('#ffffff')

        lbl_indices = {lbl.upper(): idx for idx, lbl in enumerate(self.labels)}
        
        def get_data(name, fallback_idx):
            for k, v in lbl_indices.items():
                if name in k:
                    return self.stat_data[:, v], self.labels[v]
            if fallback_idx < self.stat_data.shape[1]:
                return self.stat_data[:, fallback_idx], self.labels[fallback_idx]
            return None, name

        t = self.time_data

        ax1 = axes[0]
        ax1.set_facecolor('#ffffff')
        rms_d, rms_l = get_data("RMS", 0)
        mean_d, mean_l = get_data("MEAN", 1)
        std_d, std_l = get_data("STD", 2)
        
        if rms_d is not None: ax1.plot(t, rms_d, label=rms_l, color='#1f77b4', linewidth=1.5)
        if mean_d is not None: ax1.plot(t, mean_d, label=mean_l, color='#2ca02c', linewidth=1.5)
        if std_d is not None: ax1.plot(t, std_d, label=std_l, color='#9467bd', linewidth=1.5)
        ax1.set_ylabel("Spannung (V)", color='#2d3748')
        ax1.title.set_text("Statistische Kennwerte (RMS, Mean, Std)")
        ax1.legend(loc="upper right")

        ax2 = axes[1]
        ax2.set_facecolor('#ffffff')
        p_pos_d, p_pos_l = get_data("PEAK+", 3)
        p_neg_d, p_neg_l = get_data("PEAK-", 4)
        if p_pos_d is not None: ax2.plot(t, p_pos_d, label=p_pos_l, color='#e53e3e', linewidth=1.5)
        if p_neg_d is not None: ax2.plot(t, p_neg_d, label=p_neg_l, color='#ff7f0e', linewidth=1.5)
        ax2.set_ylabel("Spannung (V)", color='#2d3748')
        ax2.title.set_text("Spitzenwerte (Peak+, Peak-)")
        ax2.legend(loc="upper right")

        ax3 = axes[2]
        ax3.set_facecolor('#ffffff')
        pulse_pos_d, pulse_pos_l = get_data("POS_PULSE", 5)
        pulse_neg_d, pulse_neg_l = get_data("NEG_PULSE", 6)
        if pulse_pos_d is not None: ax3.plot(t, pulse_pos_d, label=pulse_pos_l, color='#17a2b8', linewidth=1.2)
        if pulse_neg_d is not None: ax3.plot(t, pulse_neg_d, label=pulse_neg_l, color='#6610f2', linewidth=1.2)
        ax3.set_ylabel("Anzahl", color='#2d3748')
        ax3.title.set_text("Impulszähler (Pos. / Neg. Pulse)")
        ax3.legend(loc="upper right")

        ax4 = axes[3]
        ax4.set_facecolor('#ffffff')
        thd_d, thd_l = get_data("THD", 7)
        if thd_d is not None: ax4.plot(t, thd_d, label=thd_l, color='#d62728', linewidth=1.5)
        ax4.set_ylabel("Klirrfaktor (%)", color='#2d3748')
        ax4.set_xlabel("Zeit (s)", color='#2d3748')
        ax4.title.set_text("Total Harmonic Distortion (THD)")
        ax4.legend(loc="upper right")

        for ax in axes:
            ax.tick_params(colors='#2d3748', labelsize=9)
            ax.grid(True, linestyle=":", alpha=0.6, color='#a0aec0')
            ax.title.set_color('#1a365d')
            ax.title.set_weight('bold')
            ax.title.set_fontsize(11)

        plt.tight_layout()
        
        buf = BytesIO()
        fig.savefig(buf, format="png", bbox_inches='tight', dpi=140, facecolor='#ffffff')
        plt.close(fig) 
        
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        return f"data:image/png;base64,{img_base64}"
        
    def _generate_boxplot_base64_for_pdf(self):
        if self.stat_data is None or len(self.stat_data) == 0:
            return ""

        groups = {
            "Spannung / Amplitude": [],
            "Prozent (z.B. THD)": [],
            "Anzahl / Pulse": []
        }
        
        current_labels = self.labels.copy()
        num_cols = self.stat_data.shape[1]
        
        if len(current_labels) < num_cols:
            for i in range(len(current_labels), num_cols):
                current_labels.append(f"Var_{i}")
        elif len(current_labels) > num_cols:
            current_labels = current_labels[:num_cols]

        for idx, label in enumerate(current_labels):
            label_upper = label.upper()
            if "THD" in label_upper or "%" in label_upper:
                groups["Prozent (z.B. THD)"].append(idx)
            elif "PULSE" in label_upper or "CNT" in label_upper or "ANZAHL" in label_upper:
                groups["Anzahl / Pulse"].append(idx)
            else:
                groups["Spannung / Amplitude"].append(idx)

        active_groups = {k: v for k, v in groups.items() if len(v) > 0}
        num_subplots = len(active_groups)
        
        if num_subplots == 0:
            return ""

        fig, axes = plt.subplots(num_subplots, 1, figsize=(10, 4 * num_subplots), sharex=False)
        fig.patch.set_facecolor('#ffffff') 
        
        if num_subplots == 1:
            axes = [axes]

        for ax, (group_name, indices) in zip(axes, active_groups.items()):
            ax.set_facecolor('#ffffff')
            
            data_to_plot = [self.stat_data[:, idx] for idx in indices]
            labels_to_plot = [current_labels[idx] for idx in indices]
            
            bp = ax.boxplot(data_to_plot, labels=labels_to_plot, patch_artist=True)
            
            for box in bp['boxes']:
                box.set(facecolor='#2b6cb0', color='#1a365d', alpha=0.7)
            for median in bp['medians']:
                median.set(color='#e53e3e', linewidth=2)
            for whisker in bp['whiskers']:
                whisker.set(color='#2d3748', linestyle='--')
            for cap in bp['caps']:
                cap.set(color='#2d3748')
            for flier in bp['fliers']:
                flier.set(marker='o', color='#e53e3e', alpha=0.5)

            ax.set_ylabel(group_name, color='#2d3748', fontsize=10)
            ax.tick_params(colors='#2d3748', labelsize=9)
            ax.grid(True, linestyle=":", alpha=0.6, color='#a0aec0')
            ax.set_xticklabels(labels_to_plot, rotation=15, ha='right')

        fig.suptitle("Statistische Verteilung nach Datentyp", color='#1a365d', fontsize=14, weight='bold')
        plt.tight_layout()
        
        buf = BytesIO()
        fig.savefig(buf, format="png", bbox_inches='tight', dpi=140, facecolor='#ffffff')
        plt.close(fig)
        
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        return f"data:image/png;base64,{img_base64}"

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(self.sidebar, text="Sync Offline Viewer", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        
        # --- NEU: Datenbank-Suche ---
        ctk.CTkButton(self.sidebar, text="🔍 In Datenbank suchen", command=self.open_db_browser, font=ctk.CTkFont(weight="bold"), fg_color="#2b6cb0").pack(fill="x", padx=15, pady=(10, 5))
        
        # --- ALTER BUTTON (als Fallback für manuelle Ordnerauswahl) ---
        ctk.CTkButton(self.sidebar, text="📂 HDF5 manuell laden", command=self.load_log_folder).pack(fill="x", padx=15, pady=(0, 10))
        
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
                      command=self.show_boxplot, fg_color="#444444").pack(fill="x", padx=15, pady=10)

        # --- PDF Export Button ---
        ctk.CTkButton(self.sidebar, text="📄 PDF Report generieren", 
                      command=self.export_pdf, fg_color="#2b6cb0", hover_color="#1a365d", 
                      font=ctk.CTkFont(weight="bold")).pack(fill="x", padx=15, pady=15)

    def export_pdf(self):
        if self.stat_data is None or len(self.stat_data) == 0:
            messagebox.showwarning("Fehler", "Keine Daten geladen. Bitte lade zuerst einen Log-Ordner.")
            return

        current_date = datetime.now().strftime("%d.%m.%Y %H:%M")
        total_epochs = len(self.time_data)
        total_time = self.time_data[-1] if total_epochs > 0 else 0
        x_inc_str = f"{self.x_inc} s"
        folder_display = getattr(self, 'current_folder_path', "Nicht definiert")
        
        current_date = datetime.now().strftime("%d.%m.%Y")
        current_time = datetime.now().strftime("%H:%M")
        
        self.mess_kommentar = self.h5_file.attrs.get('comment', 'Kein Kommentar hinterlegt.')
        
        elapsed_seconds = self.time_data[-1] if len(self.time_data) > 0 else 0
        minutes = int(elapsed_seconds // 60)
        seconds = int(elapsed_seconds % 60)
        elapsed_str = f"{minutes}m {seconds}s"
        
        datum_str = getattr(self, 'mess_datum', 'Nicht protokolliert')
        uhrzeit_str = getattr(self, 'mess_uhrzeit', 'Nicht protokolliert')
        
        stats_html = ""
        for i, label in enumerate(self.labels):
            if i < self.stat_data.shape[1]:
                mean_val = self.stat_data[:, i].mean()
                min_val = self.stat_data[:, i].min()
                max_val = self.stat_data[:, i].max()
                std_val = self.stat_data[:, i].std()
                
                unit = "%" if "THD" in label else "V"
                if "PULSE" in label.upper() or "CNT" in label.upper(): unit = "Anzahl"
                
                stats_html += f"""
                <tr>
                    <td><strong>{label}</strong></td>
                    <td>{min_val:.3f}</td>
                    <td>{max_val:.3f}</td>
                    <td>{mean_val:.3f}</td>
                    <td>{std_val:.3f}</td>
                    <td>{unit}</td>
                </tr>
                """

        events_html = ""
        if len(self.events_time) > 0:
            for t, txt in zip(self.events_time[:15], self.events_text[:15]):
                decoded_txt = txt.decode('utf-8') if isinstance(txt, bytes) else txt
                events_html += f"""
                <tr>
                    <td>{t:.1f} s</td>
                    <td><span class="badge badge-info">System</span></td>
                    <td>{decoded_txt}</td>
                </tr>
                """
        else:
            events_html = "<tr><td colspan='3' style='text-align:center; color:gray;'>Keine System-Events aufgezeichnet.</td></tr>"

        buf = BytesIO()
        orig_fig_color = self.fig.get_facecolor()
        
        self.fig.patch.set_facecolor('#ffffff')
        for ax in [self.ax_wave, self.ax, self.ax_waterfall]:
            ax.set_facecolor('#ffffff')
            ax.title.set_color('#1a365d')
            ax.xaxis.label.set_color('#2d3748')
            ax.yaxis.label.set_color('#2d3748')
            ax.tick_params(colors='#2d3748')
        
        self.canvas.draw()
        self.fig.savefig(buf, format="png", bbox_inches='tight', dpi=140, facecolor='#ffffff')
        
        self.fig.patch.set_facecolor(orig_fig_color)
        for ax in [self.ax_wave, self.ax, self.ax_waterfall]:
            ax.set_facecolor('#2b2b2b' if ax != self.ax_waterfall else '#ffffff')
            ax.title.set_color('black')
            ax.tick_params(colors='black')
        self.canvas.draw_idle()
        
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        graphs_uri = f"data:image/png;base64,{img_base64}"

        boxplot_uri = self._generate_boxplot_base64_for_pdf()
        boxplot_html = ""
        if boxplot_uri:
            boxplot_html = f"""
            <div class="chart-box" style="margin-top: 20px;">
                <div class="chart-title">Statistische Verteilung der Gesamtmessung (Boxplot)</div>
                <img src="{boxplot_uri}" class="img-fluid" />
            </div>
            """

        time_plots_uri = self._generate_time_plots_base64_for_pdf()
        time_plots_html = ""
        if time_plots_uri:
            time_plots_html = f"""
            <div class="chart-box" style="margin-top: 20px;">
                <div class="chart-title">Zeitliche Signalverläufe der Messparameter (Gesamtmessung)</div>
                <img src="{time_plots_uri}" class="img-fluid" />
            </div>
            """

        css = """
        @media print {
            body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
            .page-break { page-break-after: always; break-after: page; }
        }
        body { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #2d3748; line-height: 1.6; font-size: 10pt; margin: 10mm; background-color: #ffffff; }
        *, *::before, *::after { box-sizing: border-box; }
        .header-table { width: 100%; border-collapse: collapse; margin-bottom: 25px; border-bottom: 3px solid #2b6cb0; }
        .header-table td { padding-bottom: 15px; vertical-align: bottom; }
        .report-title { font-size: 24pt; color: #1a365d; margin: 0; font-weight: 700; letter-spacing: -0.5px; line-height: 1.1; }
        .report-subtitle { font-size: 10.5pt; color: #4a5568; margin: 5px 0 0 0; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 600; }
        .meta-table { width: 100%; margin-bottom: 30px; border-collapse: collapse; background-color: #f7fafc; border: 1px solid #e2e8f0; }
        .meta-table td { padding: 10px 14px; font-size: 9.5pt; border-bottom: 1px solid #e2e8f0; }
        .meta-label { font-weight: bold; color: #4a5568; width: 28%; background-color: #edf2f7; }
        h2 { font-size: 14pt; color: #1a365d; border-left: 4px solid #2b6cb0; padding-left: 10px; margin-top: 30px; margin-bottom: 15px; break-after: avoid; }
        p { color: #4a5568; text-align: justify; }
        .stats-table, .event-table { width: 100%; border-collapse: collapse; margin-bottom: 25px; }
        .stats-table th, .event-table th { background-color: #2b6cb0; color: white; text-align: left; padding: 10px; font-size: 9.5pt; font-weight: 600; }
        .event-table th { background-color: #4a5568; }
        .stats-table td, .event-table td { padding: 9px; border: 1px solid #e2e8f0; font-size: 9.5pt; }
        .stats-table tr:nth-child(even), .event-table tr:nth-child(even) { background-color: #f7fafc; }
        .badge { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 8pt; font-weight: bold; text-transform: uppercase; background-color: #ebf8ff; color: #2b6cb0; }
        .chart-box { border: 1px solid #e2e8f0; padding: 15px; margin-bottom: 25px; text-align: center; break-inside: avoid; }
        .chart-title { font-size: 10pt; font-weight: bold; color: #2d3748; margin-bottom: 12px; text-align: left; }
        .img-fluid { max-width: 100%; height: auto; display: block; margin: 0 auto; }
        """

        html_content = f"""
        <!DOCTYPE html>
        <html lang="de">
        <head>
            <meta charset="UTF-8">
            <style>{css}</style>
        </head>
        <body>
            <table class="header-table">
                <tr>
                    <td>
                        <div class="report-title">Shaft Voltage Monitor</div>
                        <div class="report-subtitle">Automatisierter Mess- und Analysebericht</div>
                    </td>
                    <td style="text-align: right; color: #4a5568; font-size: 9pt;">
                        <strong>Mess-Datum:</strong> {datum_str}<br>
                        <strong>Mess-Zeit:</strong> {uhrzeit_str}<br>
                        <strong>Dauer:</strong> {elapsed_str}<br>
                        Status: <span class="badge">Abgeschlossen</span>
                    </td>
                </tr>
            </table>
            
            <h2>Prüfer-Bemerkungen</h2>
            <p style="background-color: #f7fafc; padding: 15px; border: 1px solid #e2e8f0;">
                {getattr(self, 'mess_kommentar', 'Kein Kommentar')}
            </p>

            <h2>1. Allgemeine Systemmetadaten</h2>
            <table class="meta-table">
                <tr><td class="meta-label">Quell-Ordner</td><td>{folder_display}</td></tr>
                <tr><td class="meta-label">Anzahl Datenpunkte</td><td>{total_epochs} Zeitfenster (Epochen)</td></tr>
                <tr><td class="meta-label">Abtastintervall (x_inc)</td><td>{x_inc_str}</td></tr>
                <tr><td class="meta-label">Gesamte Messdauer</td><td>{total_time:.2f} Sekunden</td></tr>
            </table>

            <h2>2. Statistische Kennwerte (Gesamtmessung)</h2>
            <table class="stats-table">
                <thead>
                    <tr>
                        <th>Messgröße (Label)</th><th>Minimalwert</th><th>Maximalwert</th><th>Mittelwert (&mu;)</th><th>Standardabw. (&sigma;)</th><th>Einheit</th>
                    </tr>
                </thead>
                <tbody>
                    {stats_html}
                </tbody>
            </table>

            {boxplot_html}

            <div class="page-break"></div>
            <h2>3. Zeitliche Parameter-Verläufe (Gesamtmessung)</h2>
            <p>Die nachfolgende Diagrammserie zeigt die Dynamik der einzelnen Kennwerte über die gesamte aufgezeichnete Messdauer:</p>
            {time_plots_html}

            <div class="page-break"></div>

            <h2>4. Signal- und Frequenzanalyse (Aktueller Punkt)</h2>
            <p>Die nachfolgenden Diagramme dokumentieren den Zustand des aktuell in der Software angewählten Datenpunkts (Datenfenster-Index: {self.current_index} bei relativer Systemzeit: {self.time_data[self.current_index] if self.time_data else 0:.2f}s).</p>
            <div class="chart-box">
                <div class="chart-title">Wellenform, FFT Spektrum & Spektrogramm</div>
                <img src="{graphs_uri}" class="img-fluid" />
            </div>

            <h2>5. Protokollierte System-Events (Auszug)</h2>
            <table class="event-table">
                <thead>
                    <tr><th style="width: 15%;">Zeitstempel</th><th style="width: 20%;">Typ</th><th>Event-Text / Beschreibung</th></tr>
                </thead>
                <tbody>
                    {events_html}
                </tbody>
            </table>
            
            <table style="width: 100%; margin-top: 40px; break-inside: avoid;">
                <tr>
                    <td style="width: 50%; border-top: 1px solid #a0aec0; padding-top: 8px;">
                        <font style="font-size: 9pt; color: #718096;">Automatisches Prüfsystem</font><br>
                        <strong>Sync Offline Viewer Engine</strong>
                    </td>
                    <td style="width: 50%;"></td>
                </tr>
            </table>
        </body>
        </html>
        """

        temp_html = os.path.join(os.getcwd(), "temp_report.html")
        output_filename = f"Messbericht_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        output_path = os.path.join(os.getcwd(), output_filename)
        
        try:
            with open(temp_html, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
            if not os.path.exists(edge_path):
                edge_path = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

            cmd = [
                edge_path,
                "--headless",
                "--disable-gpu",
                f"--print-to-pdf={output_path}",
                "--no-margins",
                temp_html
            ]
            
            subprocess.run(cmd, check=True)
            
            if os.path.exists(temp_html):
                os.remove(temp_html)
                
            messagebox.showinfo("Erfolg", f"Report erfolgreich generiert:\n{output_path}")
            
            if os.name == 'nt':
                os.startfile(output_path)
                
        except Exception as e:
            messagebox.showerror("Export Fehler", f"Das PDF konnte nicht erstellt werden.\nFehler: {e}")

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
        """Manueller Fallback über den Windows-Ordner-Dialog."""
        initial_dir = os.path.join(os.getcwd(), "data") if os.path.exists("data") else "/"
        folder_path = filedialog.askdirectory(initialdir=initial_dir)
        if not folder_path: return
        self._load_h5_from_path(folder_path)

    def _load_h5_from_path(self, folder_path):
        """Die ausgelagerte HDF5 Lade-Logik."""
        self.current_folder_path = folder_path
        h5_path = os.path.join(folder_path, "datalog.h5")
        if not os.path.exists(h5_path):
            messagebox.showerror("Fehler", f"Ausgewählter Ordner enthält keine 'datalog.h5':\n{folder_path}")
            return
            
        try:
            self.h5_file = h5py.File(h5_path, "r")
            
            self.mess_datum = self.h5_file.attrs.get('date', 'Unbekannt')
            self.mess_uhrzeit = self.h5_file.attrs.get('time', 'Unbekannt')
            
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

    def open_db_browser(self):
        """Öffnet das Datenbank-Suchfenster (Treeview)."""
        db_window = ctk.CTkToplevel(self)
        db_window.title("Messungs-Katalog durchsuchen")
        db_window.geometry("950x400")
        db_window.transient(self) 

        search_frame = ctk.CTkFrame(db_window)
        search_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(search_frame, text="Suchen (Datum / Kommentar):", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=10)
        search_entry = ctk.CTkEntry(search_frame, width=350, placeholder_text="Tippen zum Filtern...")
        search_entry.pack(side="left", padx=5)

        # Tabellen-Struktur
        columns = ("id", "Datum", "Dauer (s)", "THD (%)", "RMS (V)", "Vpp Max (V)", "Kommentar")
        tree = ttk.Treeview(db_window, columns=columns, show="headings")
        
        tree.column("id", width=40, anchor="center")
        tree.column("Datum", width=140)
        tree.column("Dauer (s)", width=80, anchor="e")
        tree.column("THD (%)", width=80, anchor="e")
        tree.column("RMS (V)", width=80, anchor="e")
        tree.column("Vpp Max (V)", width=80, anchor="e")
        tree.column("Kommentar", width=400)
        
        for col in columns:
            tree.heading(col, text=col)
            
        tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        db = MetadataDB()

        def refresh_table(event=None):
            for row in tree.get_children():
                tree.delete(row)
            
            term = search_entry.get().strip()
            records = db.search_measurements(term)
            
            for r in records:
                tree.insert("", "end", iid=r["folder_path"], values=(
                    r["id"],
                    r["timestamp"],
                    f"{r['duration_sec']:.1f}",
                    f"{r['thd_mean']:.2f}",
                    f"{r['rms_mean']:.3f}",
                    f"{r['vpp_max']:.3f}",
                    r["comment"]
                ))

        refresh_table()
        search_entry.bind("<KeyRelease>", refresh_table)

        def on_double_click(event):
            item_id = tree.focus()
            if item_id:
                folder_path = item_id 
                if os.path.exists(folder_path):
                    self._load_h5_from_path(folder_path)
                    db_window.destroy()
                else:
                    messagebox.showerror("Fehler", f"Der Ordner existiert nicht mehr auf der Festplatte!\nPfad: {folder_path}")

        tree.bind("<Double-1>", on_double_click)

    def render_waterfall(self):
        self.ax_waterfall.clear()
        if self.fft_data is None or len(self.fft_data) == 0: return
        
        freq_scale = self.fft_freq / 1e3 if self.fft_freq[-1] >= 1e5 else self.fft_freq
        self.ax_waterfall.set_xlabel("Frequenz (kHz)" if self.fft_freq[-1] >= 1e5 else "Frequenz (Hz)")
        self.ax_waterfall.set_ylabel("Zeit (s)")
        
        dec = 10 if len(freq_scale) > 2000 else 1 
        
        X, Y = np.meshgrid(freq_scale[::dec], self.time_data)
        self.ax_waterfall.pcolormesh(X, Y, self.fft_data[:, ::dec], shading='nearest', cmap='viridis')
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