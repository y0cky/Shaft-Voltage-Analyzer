import numpy as np

def calculate_thd(frequencies, fft_db):
    """Berechnet die Total Harmonic Distortion (THD) in % aus dB-Werten."""
    try:
        # Konvertiere dB in lineare Werte (angenommen dB = 20*log10(V))
        lin_mag = 10**(fft_db / 20.0)
        
        # Ignoriere DC-Komponente (alles unter 5 Hz)
        valid_indices = np.where(frequencies > 5.0)[0]
        if len(valid_indices) == 0: return 0.0
        
        # Finde Grundfrequenz (Fundamental) nur im gültigen Bereich
        peak_idx = valid_indices[np.argmax(lin_mag[valid_indices])]
        f0 = frequencies[peak_idx]
        v1 = lin_mag[peak_idx]
        
        if v1 == 0 or f0 <= 0: return 0.0

        # Summiere die Quadrate der Harmonischen (bis zur 9. Harmonischen)
        harmonics_sq_sum = 0
        for h in range(2, 10):
            hf = h * f0
            if hf > frequencies[-1]: break  # Über Nyquist-Frequenz
            # Finde den nächstgelegenen Index zur Harmonischen
            idx = np.argmin(np.abs(frequencies - hf))
            harmonics_sq_sum += lin_mag[idx]**2

        thd = (np.sqrt(harmonics_sq_sum) / v1) * 100.0
        return min(thd, 100.0)  # Begrenze auf max 100% für saubere Plots
    except Exception:
        return 0.0