import numpy as np

def calculate_thd(frequencies, fft_db, min_freq=20.0, search_window=3):
    """
    Berechnet die Total Harmonic Distortion (THD) in % aus dB-Werten.
    
    :param frequencies: Array der Frequenzen
    :param fft_db: Array der Amplituden in dB
    :param min_freq: Frequenz (Hz), ab der gesucht wird (vermeidet 1/f Rauschen)
    :param search_window: Anzahl der Bins links/rechts, in denen nach dem Peak gesucht wird
    """
    try:
        # 1. Konvertiere dB in lineare Werte (angenommen dB = 20*log10(V))
        lin_mag = 10**(fft_db / 20.0)
        
        # 2. Ignoriere DC-Komponente und extremes Niederfrequenz-Rauschen
        valid_indices = np.where(frequencies > min_freq)[0]
        if len(valid_indices) == 0: 
            return 0.0
        
        # 3. Finde Grundfrequenz (Fundamental)
        peak_idx = valid_indices[np.argmax(lin_mag[valid_indices])]
        f0 = frequencies[peak_idx]
        
        # Lokales Maximum für die Grundwelle suchen (Leakage-Ausgleich)
        start_f0 = max(0, peak_idx - search_window)
        end_f0 = min(len(lin_mag), peak_idx + search_window + 1)
        v1 = np.max(lin_mag[start_f0:end_f0])
        
        if v1 == 0 or f0 <= 0: 
            return 0.0

        # 4. Summiere die Quadrate der Harmonischen (bis zur 9. Harmonischen)
        harmonics_sq_sum = 0.0
        for h in range(2, 10):
            hf = h * f0
            if hf > frequencies[-1]: 
                break  # Über Nyquist-Frequenz
                
            # Finde den nächstgelegenen Index zur Harmonischen
            center_idx = np.argmin(np.abs(frequencies - hf))
            
            # Definiere ein Suchfenster um diesen Index herum
            start_idx = max(0, center_idx - search_window)
            end_idx = min(len(lin_mag), center_idx + search_window + 1)
            
            # Nimm den höchsten Peak in diesem Fenster
            v_harmonic = np.max(lin_mag[start_idx:end_idx])
            harmonics_sq_sum += v_harmonic**2

        # 5. THD berechnen
        thd = (np.sqrt(harmonics_sq_sum) / v1) * 100.0
        
        # Wenn THD unrealistisch groß ist, liegt zu 99% ein Trigger-Verlust vor.
        # Wir begrenzen es hier hart auf 100% für saubere Plots.
        return min(thd, 100.0)
        
    except Exception as e:
        print(f"THD Berechnung fehlgeschlagen: {e}")
        return 0.0