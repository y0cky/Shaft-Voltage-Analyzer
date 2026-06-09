# RTB2004 Sync Logger & Viewer

A powerful Python tool for synchronized data acquisition, analysis, and reporting of shaft voltage measurement data, captured with oscilloscopes such as the Rohde & Schwarz RTB2004.

## Features

### 🔴 Live Datalogger
- LAN connection via PyVISA
- Acquisition of RMS, Mean, Std, Peak+, Peak−
- THD (Total Harmonic Distortion)
- Pulse counts
- Optional FFT & waveform logging
- Live visualization (waveform, FFT, THD, statistics)
- Event markers during measurement
- Data storage in HDF5 format (.h5)

### 📊 Log Viewer
- Load HDF5 files or browse via database
- Visualization: waveform, FFT, waterfall (spectrogram)
- Timeline navigation & event jumping
- Boxplot & time-series analysis
- PDF export

### 📑 Comparison Report
- Compare measurements:
  - without vs. with discharge system
- Automatic KPI evaluation:
  - RMS, Vpp, THD, damping
- Combined waveform & FFT analysis
- Professional PDF report generation

## 🧰 Technologies

- Python
- CustomTkinter
- Matplotlib
- NumPy
- h5py (HDF5)
- PyVISA
- SQLite

## 📂 Project Structure

```
src/
  gui/
  utils/
data/
```

## ▶️ Installation

pip install customtkinter numpy matplotlib pyvisa pyvisa-py h5py

## ▶️ Run

python main.py

## ⚠️ Requirements

- SCPI-capable oscilloscope connected via network
- Microsoft Edge (for PDF export)

## 📌 Use Case

- Shaft voltage analysis
- Bearing current monitoring
- EMI / high-frequency noise analysis
- Evaluation of shaft grounding / discharge systems

