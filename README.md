# RTB2004 Sync Logger & Viewer

Ein leistungsstarkes Python-Tool zur synchronen Datenerfassung, Analyse und Berichterstellung von Messdaten zur Wellenspannung, aufgenommen mit Oszilloskopen wie dem Rohde & Schwarz RTB2004.

## Features

### 🔴 Live Datalogger
- LAN-Verbindung via PyVISA
- Erfassung von RMS, Mean, Std, Peak+, Peak-
- THD (Total Harmonic Distortion)
- Pulse Counts
- Optional: FFT & Wellenform Logging
- Live-Plots (Waveform, FFT, THD, Statistik)
- Event-Marker
- Speicherung als HDF5 (.h5)

### 📊 Log Viewer
- Laden von HDF5-Dateien oder via Datenbank
- Visualisierung: Wave, FFT, Waterfall
- Zeitleiste & Event-Sprung
- Boxplot & Zeitverlauf-Analyse
- PDF Export

### 📑 Vergleichsbericht
- Vergleich „ohne“ vs. „mit“ Ableitsystem
- Automatische KPI-Auswertung (RMS, Vpp, THD, Dämpfung)
- Wave + FFT Analyse
- Professioneller PDF-Report

## 🧰 Technologien

- Python
- CustomTkinter
- Matplotlib
- NumPy
- h5py (HDF5)
- PyVISA
- SQLite

## 📂 Struktur

src/
  gui/
  utils/
data/

## ▶️ Installation

pip install customtkinter numpy matplotlib pyvisa pyvisa-py h5py

## ▶️ Start

python main.py

## ⚠️ Voraussetzung

- SCPI-fähiges Oszilloskop im Netzwerk
- Microsoft Edge für PDF Export

## 📌 Use Case

- Wellenspannungsanalyse
- Lagerstrom-Überwachung
- EMV Analyse
- Vergleich von Ableitsystemen

