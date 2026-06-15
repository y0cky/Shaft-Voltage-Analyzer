import os
import csv
import math
import threading
import traceback
import datetime
from dataclasses import dataclass
from typing import List, Tuple, Optional

import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk

try:
    from RsInstrument import RsInstrument, ResourceError
    RS_AVAILABLE = True
except Exception:
    RsInstrument = None
    ResourceError = Exception
    RS_AVAILABLE = False


# =====================================================================================
#   eCON Sweep Tab for Shaft-Voltage-Analyzer
#   - integriert die Standalone-eCON-Messung als CustomTkinter-Tab
#   - Sweep 10 kHz ... 100 kHz
#   - CSV-Logging im Stil des bisherigen Programms
#   - KEIN UDP, alle Parameter werden in der GUI gesetzt
# =====================================================================================

APP_TITLE = "eCON Sweep"
APP_VERSION = "1.0"

# ---- Messkonstanten (bitte bei Bedarf an den Prüfstand anpassen) --------------------
RSHUNT = 1.0        # Shunt-Widerstand [Ohm] -> an reale Hardware anpassen
KDV = 1.0           # Verstärkungs-/Teilerfaktor -> an reale Hardware anpassen
KV = 1.0            # Faktor für Generatorspannung -> Generator = 2.0 / KV * eCON-Spannung
BODETIMEOUT = 120   # Polling-Zyklen á 0.1 s => 12 s
DOCU_VERSION_BASE = "eCON_GUI"

# DSO-Bode-Konfiguration analog zum Altprogramm
FREQ_START_HZ = 1.0e4
FREQ_STOP_HZ = 1.0e5
LOG_POINTS = 12  # liefert typisch 13 Punkte inkl. Start/Stop
SELECTED_FREQ_INDEXES = {2, 8}  # ≈ 14.7/46.4 kHz wie im Altprogramm

# Simulationsdaten analog zum Bestandscode
SIM_TXT_FRQ = "10.0,12.1,14.7,17.8,21.5,26.1,31.6,38.3,46.4,56.2,68.1,82.5,100.0"
SIM_TXT_PHASE = "-1.0,-2.0,-3.0,-4.0,-5.0,-6.0,-7.0,-8.0,-9.0,-10.0,-11.0,-12.0,-13.0"
SIM_FLOAT_ARRAY_FRQ = [1000.0 * float(number) for number in SIM_TXT_FRQ.split(",")]
SIM_FLOAT_ARRAY_PHASE = [float(number) for number in SIM_TXT_PHASE.split(",")]


# -------------------------------------------------------------------------------------
# Hilfsfunktionen
# -------------------------------------------------------------------------------------
def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def convert_seconds(seconds: int, fmt: int = 4) -> str:
    days = seconds // 86400
    seconds %= 86400
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    if fmt == 2:
        return f"{minutes:02d}:{seconds:02d}"
    if fmt == 3:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    if fmt == 4:
        return f"{days:03d}:{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def parse_runtime_to_seconds(runtime_text: str) -> int:
    """
    Erwartet d:hh:mm:ss oder dd:hh:mm:ss oder ddd:hh:mm:ss.
    Fallback: hh:mm:ss.
    """
    rt = runtime_text.strip()
    parts = rt.split(":")
    if len(parts) == 4:
        d, h, m, s = [int(p) for p in parts]
        return d * 86400 + h * 3600 + m * 60 + s
    if len(parts) == 3:
        h, m, s = [int(p) for p in parts]
        return h * 3600 + m * 60 + s
    raise ValueError("Laufzeitformat ungültig. Erwartet z.B. 000:01:23:45 oder 01:23:45")


def fmt_num(value: float, width: int = 0, digits: int = 3) -> str:
    text = f"{value:{width}.{digits}f}" if width else f"{value:.{digits}f}"
    return text.replace(".", ",")


# -------------------------------------------------------------------------------------
# Kalibrierung
# -------------------------------------------------------------------------------------
def load_calibration_data(testbench: str) -> Tuple[np.ndarray, np.ndarray, str]:
    import sys
    tb = (testbench or "").strip().upper()

    if tb == "ZA":
        R_meas = np.zeros(16)
        R_meas[0] = sys.float_info.min
        R_meas[1] = 0.00
        R_meas[2] = 0.36
        R_meas[3] = 0.63
        R_meas[4] = 1.13
        R_meas[5] = 2.30
        R_meas[6] = 4.71
        R_meas[7] = 9.85
        R_meas[8] = 21.36
        R_meas[9] = 44.95
        R_meas[10] = 93.88
        R_meas[11] = 393.39
        R_meas[12] = 715.76
        R_meas[13] = 10000.0
        R_meas[14] = 100000.0
        R_meas[15] = sys.float_info.max

        R_cal = np.zeros(16)
        R_cal[0] = sys.float_info.min
        R_cal[1] = 0.00
        R_cal[2] = 0.22
        R_cal[3] = 0.47
        R_cal[4] = 1.0
        R_cal[5] = 2.2
        R_cal[6] = 4.7
        R_cal[7] = 10.0
        R_cal[8] = 22.0
        R_cal[9] = 47.0
        R_cal[10] = 100.0
        R_cal[11] = 470.0
        R_cal[12] = 1000.0
        R_cal[13] = 10000.0
        R_cal[14] = 100000.0
        R_cal[15] = sys.float_info.max
        txt = "Kalibrierdaten ZA (Stand 21.05.2024)"
    elif tb == "ZH":
        R_meas = np.zeros(16)
        R_meas[0] = sys.float_info.min
        R_meas[1] = 0.00
        R_meas[2] = 0.86
        R_meas[3] = 1.32
        R_meas[4] = 1.53
        R_meas[5] = 2.88
        R_meas[6] = 5.56
        R_meas[7] = 11.44
        R_meas[8] = 22.73
        R_meas[9] = 47.7
        R_meas[10] = 101.75
        R_meas[11] = 227.8
        R_meas[12] = 495.5
        R_meas[13] = 1000.0
        R_meas[14] = 10000.0
        R_meas[15] = sys.float_info.max

        R_cal = np.zeros(16)
        R_cal[0] = sys.float_info.min
        R_cal[1] = 0.00
        R_cal[2] = 0.05
        R_cal[3] = 0.492
        R_cal[4] = 1.184
        R_cal[5] = 2.35
        R_cal[6] = 4.85
        R_cal[7] = 10.82
        R_cal[8] = 22.14
        R_cal[9] = 47.07
        R_cal[10] = 100.44
        R_cal[11] = 221.9
        R_cal[12] = 469.7
        R_cal[13] = 1000.0
        R_cal[14] = 10000.0
        R_cal[15] = sys.float_info.max
        txt = "Kalibrierdaten ZH (variables voltage measurement, Anfang 2024)"
    else:
        R_meas = np.array([
            np.finfo(float).tiny, 0.00, 0.22, 0.47, 1.00, 2.2, 4.7, 10.0,
            22.0, 47.0, 100.0, 470.0, 1000.0, 10000.0, 100000.0, np.finfo(float).max
        ], dtype=float)
        R_cal = R_meas.copy()
        txt = "Keine spezifischen Kalibrierdaten gefunden – Standardwerte werden verwendet"
    return R_meas, R_cal, txt


def calib_01(Rm: float, R_meas: np.ndarray, R_cal: np.ndarray) -> float:
    if Rm <= R_meas[1]:
        return float(R_cal[1])
    for i in range(1, len(R_meas)):
        if Rm <= R_meas[i]:
            if R_meas[i] == R_meas[i - 1]:
                return float(R_cal[i])
            Rc = R_cal[i - 1] + (R_cal[i] - R_cal[i - 1]) / (R_meas[i] - R_meas[i - 1]) * (Rm - R_meas[i - 1])
            return float(Rc)
    return float(R_cal[-2])


# -------------------------------------------------------------------------------------
# VISA-Funktionen analog zum Altbestand
# -------------------------------------------------------------------------------------
class VisaDevice:
    def __init__(self, resource: str):
        self.resource = resource
        self.dev = None

    def connect(self) -> None:
        if not RS_AVAILABLE:
            raise RuntimeError("RsInstrument ist nicht installiert. Für reale Messung bitte Paket/Umgebung prüfen.")
        self.dev = RsInstrument(self.resource, True, False)
        self.dev.visa_timeout = 10000
        self.dev.opc_timeout = 10000
        self.dev.instrument_status_checking = True
        self.dev.clear_status()

    def close(self) -> None:
        try:
            if self.dev is not None:
                self.dev.close()
        except Exception:
            pass
        self.dev = None

    def write(self, cmd: str) -> None:
        if self.dev is None:
            raise RuntimeError("VISA-Gerät nicht verbunden")
        self.dev.write_str_with_opc(cmd)

    def query(self, cmd: str) -> str:
        if self.dev is None:
            raise RuntimeError("VISA-Gerät nicht verbunden")
        return self.dev.query_str_with_opc(cmd)

    def prepare_bode(self) -> None:
        self.write('BPLot:ENABle ON')
        self.write('CHAN1:STAT ON')
        self.write('CHAN1:COUPling DCLimit')
        self.write('CHAN2:COUPling DCLimit')
        self.write('CHAN1:BANDwidth B20')
        self.write('CHAN2:BANDwidth B20')
        self.write('CHAN2:STAT ON')
        self.write('CHAN3:STAT OFF')
        self.write('CHAN4:STAT OFF')
        self.write('WGENerator:OUTPut:LOAD HIGHz')
        self.write('WGENerator:VOLTage:OFFSet 0.0E-0')
        self.write('BPLot:INPut CH1')
        self.write('BPLot:OUTPut CH2')
        self.write('BPLot:MEASurement:DELay 0.0E-0')
        self.write('BPLot:MEASurement:POINt:DISPLAY ON')
        self.write(f'BPLot:FREQuency:STARt {FREQ_START_HZ:.0f}')
        self.write(f'BPLot:FREQuency:STOP {FREQ_STOP_HZ:.0f}')
        self.write(f'BPLot:POINts:LOGarithmic {LOG_POINTS}')
        self.write('BPLot:GAIN:SCALe 10')
        self.write('BPLot:GAIN:POSition 3')
        self.write('BPLot:PHASe:ENABle ON')
        self.write('BPLot:PHASe:POSition 0')
        self.write('BPLot:PHASe:SCALe 20')
        self.write('FORMAT ASCII')

    def wait_busy(self, timeout_loops: int = BODETIMEOUT) -> bool:
        cnt = 0
        while True:
            cnt += 1
            txt = self.query('BPLot:STATe?')
            if 'STOP' in txt:
                return True
            if cnt > timeout_loops:
                return False
            import time as _time
            _time.sleep(0.1)

    def run_bode(self, voltage_generator: float) -> Tuple[List[float], List[float], List[float], int]:
        self.write(f'WGENerator:VOLTage {voltage_generator:5.2f}')
        self.write('BPLot:STATe RUN')
        ok = self.wait_busy()
        if ok:
            txt_frq = self.query('BPLot:FREQ:DATA?')
            txt_gain = self.query('BPLot:GAIN:DATA?')
            txt_phase = self.query('BPLot:PHASE:DATA?')
            float_array_frq = [float(number) for number in txt_frq.split(',')]
            float_array_gain = [float(number) for number in txt_gain.split(',')]
            float_array_phase = [float(number) for number in txt_phase.split(',')]
            return float_array_frq, float_array_gain, float_array_phase, 0

        # Timeout: Dummy-Daten analog zum Altprogramm
        txt_frq = '1.000E+04,1.212E+04,1.468E+04,1.778E+04,2.154E+04,2.610E+04,3.162E+04,3.831E+04,4.642E+04,5.623E+04,6.813E+04,8.254E+04,1.000E+05'
        txt_gain = '-79.99999E+00,-79.99999E+00,-79.99999E+00,-79.99999E+00,-79.99999E+00,-79.99999E+00,-79.99999E+00,-79.99999E+00,-79.99999E+00,-79.99999E+00,-79.99999E+00,-79.99999E+00,-79.99999E+00'
        txt_phase = '0.000E+00,0.000E+00,0.000E+00,0.000E+00,0.000E+00,0.000E+00,0.000E+00,0.000E+00,0.000E+00,0.000E+00,0.000E+00,0.000E+00,0.000E+00'
        float_array_frq = [float(number) for number in txt_frq.split(',')]
        float_array_gain = [float(number) for number in txt_gain.split(',')]
        float_array_phase = [float(number) for number in txt_phase.split(',')]
        return float_array_frq, float_array_gain, float_array_phase, 1


# -------------------------------------------------------------------------------------
# Datenmodell + Messkern
# -------------------------------------------------------------------------------------
@dataclass
class MeasurementConfig:
    testbench: str
    connection_device: str
    out_dir: str
    trial_number: str
    trial_sequence: str
    trial_remark: str
    cell: int
    measurement_runtime: str
    ts_counter: int
    cycle_counter: int
    oiltemp_q: float
    oiltemp_c: float
    pressure: float
    speed: float
    voltages: List[int]
    use_calibration: bool
    simulation: bool


class EconMeasurementRunner:
    def __init__(self, app):
        self.app = app
        self.stop_requested = False

    def request_stop(self):
        self.stop_requested = True

    def log(self, text: str):
        self.app.log(text)

    def _docu_version(self, simulation: bool, use_calibration: bool) -> str:
        suffix = "_Sim" if simulation else "_Meas"
        suffix += "_cal" if use_calibration else "_ncal"
        return DOCU_VERSION_BASE + suffix

    def _csv_header(self) -> List[str]:
        return [
            "version", "timestamp1", "timestamp2", "meas_runtime", "t_ImpMeas", "t_ImpWait",
            "cntr_par", "trial_number", "trial_sequence", "trial_remark",
            "OC_testbench", "OC_cell", "OC_TSCnt", "OC_CycleCounter", "OC_index",
            "OC_Oiltemp_q", "OC_Oiltemp_c", "OC_Pressure", "OC_Speed",
            "OC_Voltage_PAM", "OC_Frequency", "Imp_Mag", "Imp_Phase", "Error_flag",
            "trial_remark2", "dummy1", "dummy2", "dummy3"
        ]

    def _open_csvs(self, cfg: MeasurementConfig):
        ensure_dir(cfg.out_dir)
        trial_safe = cfg.trial_number.replace(" ", "") or datetime.datetime.now().strftime("Trial_%Y%m%d_%H%M%S")
        fn_all = os.path.join(cfg.out_dir, f"{trial_safe}.csv")
        fn_sel = os.path.join(cfg.out_dir, f"{trial_safe}_selected.csv")

        exists_all = os.path.exists(fn_all)
        exists_sel = os.path.exists(fn_sel)

        f_all = open(fn_all, "a", newline="", encoding="utf-8")
        f_sel = open(fn_sel, "a", newline="", encoding="utf-8")
        w_all = csv.writer(f_all, delimiter=';')
        w_sel = csv.writer(f_sel, delimiter=';')

        if not exists_all:
            w_all.writerow(self._csv_header())
        if not exists_sel:
            w_sel.writerow(self._csv_header())
        return fn_all, fn_sel, f_all, f_sel, w_all, w_sel

    def _write_row(self, writer, *, docu_version: str, timestamp: str, excel_ts: str,
                   meas_runtime_hours: str, t_imp_meas: str, t_imp_wait: str, cntr_par: str,
                   cfg: MeasurementConfig, oc_index: str, oc_voltage_pam: str, oc_frq: str,
                   imp_mag: str, imp_phase: str, error_flag: str):
        writer.writerow([
            docu_version,
            timestamp,
            excel_ts,
            meas_runtime_hours,
            t_imp_meas,
            t_imp_wait,
            cntr_par,
            cfg.trial_number.replace(" ", ""),
            cfg.trial_sequence.replace(";", "_"),
            cfg.trial_remark.replace(";", "_"),
            cfg.testbench,
            str(cfg.cell),
            str(cfg.ts_counter),
            str(cfg.cycle_counter),
            oc_index,
            fmt_num(cfg.oiltemp_q, digits=1),
            fmt_num(cfg.oiltemp_c, digits=1),
            fmt_num(cfg.pressure, digits=1),
            fmt_num(cfg.speed, digits=0),
            oc_voltage_pam,
            oc_frq,
            imp_mag,
            imp_phase,
            error_flag,
            cfg.trial_remark.replace(";", "_"),
            "",
            "",
            "",
        ])

    def _simulate_econ(self, cfg: MeasurementConfig, voltage: int, runtime_seconds: int):
        frqs = SIM_FLOAT_ARRAY_FRQ
        phases = SIM_FLOAT_ARRAY_PHASE
        gains = []
        impedances = []
        for f in frqs:
            kt = 1.0 - 1.0 * (cfg.oiltemp_c - 20.0) / 200.0
            ks = 1.0 + cfg.speed / 15000.0
            kfr = 1.0939 - 0.0000063898 * f
            kv = 0.1 * (1.0 + 10.0 / float(voltage)) - 0.1 if voltage > 0 else 1.0
            krt = 1.0 + float(cfg.cell) * runtime_seconds / 60.0
            Z = 0.1 * float(cfg.cell) * kt * ks * kfr * kv * krt
            gains.append(-20.0 * math.log10(max(Z / max(RSHUNT * KDV, 1e-12), 1e-12)))
            impedances.append(Z)
        return frqs, gains, phases, impedances, 0

    def run(self, cfg: MeasurementConfig):
        self.stop_requested = False
        visa = None
        f_all = None
        f_sel = None
        start_time = datetime.datetime.now()
        excel_ts = str((start_time - datetime.datetime(1899, 12, 30)).total_seconds() / 86400.0).replace('.', ',')
        timestamp = start_time.strftime('%d.%m.%y %H:%M:%S')
        timestamp_short = start_time.strftime('%d.%m %H:%M:%S')

        runtime_seconds = parse_runtime_to_seconds(cfg.measurement_runtime)
        meas_runtime_hours = fmt_num(runtime_seconds / 3600.0, width=10, digits=5)
        t_imp_meas = fmt_num(0.0, width=10, digits=5)
        t_imp_wait = fmt_num(0.0, width=10, digits=5)

        if not cfg.voltages:
            raise ValueError("Es wurde keine Spannung ausgewählt.")

        docu_version = self._docu_version(cfg.simulation, cfg.use_calibration)
        cntr_par_int = 32 | 8 | (1 if cfg.use_calibration else 0)  # FLAG_IMPMEAS | FLAG_PART | FLAG_CALIB
        cntr_par = f"{cntr_par_int:3d}"

        R_meas, R_cal, calib_txt = load_calibration_data(cfg.testbench)
        self.log(f"Kalibrierung: {calib_txt}")

        fn_all, fn_sel, f_all, f_sel, w_all, w_sel = self._open_csvs(cfg)
        self.log(f"CSV (alle Punkte): {fn_all}")
        self.log(f"CSV (Selektion): {fn_sel}")

        measurement_start_monotonic = datetime.datetime.now().timestamp()
        try:
            if not cfg.simulation:
                visa = VisaDevice(cfg.connection_device)
                self.log(f"Verbinde DSO/VISA: {cfg.connection_device}")
                visa.connect()
                idn = visa.query('*IDN?').strip()
                self.log(f"Verbunden mit: {idn}")
                visa.prepare_bode()
                self.log("Bode-Setup geladen (10 kHz ... 100 kHz)")
            else:
                if not RS_AVAILABLE:
                    self.log("Hinweis: RsInstrument nicht gefunden – Simulationsmodus ist trotzdem verfügbar.")
                self.log("Simulationsmodus aktiv")

            for idx_v, voltage in enumerate(cfg.voltages, start=1):
                if self.stop_requested:
                    self.log("Messung wurde vom Benutzer gestoppt.")
                    break

                self.log(f"\n[{idx_v}/{len(cfg.voltages)}] eCON-Sweep für {voltage} V")
                generator_voltage = float(voltage) * 2.0 / KV
                self.log(f"Generatorspannung = {generator_voltage:.2f} V")

                if cfg.simulation:
                    frqs, gains, phases, impedances, error_flag = self._simulate_econ(cfg, voltage, runtime_seconds)
                else:
                    frqs, gains, phases, error_flag = visa.run_bode(generator_voltage)
                    impedances = []
                    for g in gains:
                        Z = RSHUNT * KDV * 10.0 ** (-g / 20.0)
                        impedances.append(max(Z, 0.001))

                for i, f_hz in enumerate(frqs):
                    if self.stop_requested:
                        break
                    Z = float(impedances[i])
                    if cfg.use_calibration:
                        Z = calib_01(Z, R_meas, R_cal)
                    if Z < 0.001:
                        Z = 0.001

                    oc_index = str(len(frqs) * voltage + i)
                    oc_voltage_pam = f"{voltage:d}"
                    oc_frq = fmt_num(f_hz / 1000.0, width=5, digits=1)
                    imp_mag = fmt_num(Z, width=8, digits=3)
                    imp_phase = fmt_num(phases[i], width=6, digits=1)
                    error_flag_str = str(error_flag)

                    self._write_row(
                        w_all,
                        docu_version=docu_version,
                        timestamp=timestamp,
                        excel_ts=excel_ts,
                        meas_runtime_hours=meas_runtime_hours,
                        t_imp_meas=t_imp_meas,
                        t_imp_wait=t_imp_wait,
                        cntr_par=cntr_par,
                        cfg=cfg,
                        oc_index=oc_index,
                        oc_voltage_pam=oc_voltage_pam,
                        oc_frq=oc_frq,
                        imp_mag=imp_mag,
                        imp_phase=imp_phase,
                        error_flag=error_flag_str,
                    )

                    if i in SELECTED_FREQ_INDEXES:
                        self._write_row(
                            w_sel,
                            docu_version=docu_version,
                            timestamp=timestamp,
                            excel_ts=excel_ts,
                            meas_runtime_hours=meas_runtime_hours,
                            t_imp_meas=t_imp_meas,
                            t_imp_wait=t_imp_wait,
                            cntr_par=cntr_par,
                            cfg=cfg,
                            oc_index=oc_index,
                            oc_voltage_pam=oc_voltage_pam,
                            oc_frq=oc_frq,
                            imp_mag=imp_mag,
                            imp_phase=imp_phase,
                            error_flag=error_flag_str,
                        )

                    if i in SELECTED_FREQ_INDEXES:
                        self.log(
                            f"{timestamp_short} | Zelle {cfg.cell} | {voltage:>2} V | "
                            f"{f_hz/1000.0:>5.1f} kHz | Z={Z:>8.3f} Ohm | Phase={phases[i]:>6.1f} °"
                        )

                f_all.flush()
                f_sel.flush()

            elapsed = datetime.datetime.now().timestamp() - measurement_start_monotonic
            self.log(f"\nMessung abgeschlossen in {elapsed:.1f} s")
            self.log(f"Dateien gespeichert:\n - {fn_all}\n - {fn_sel}")
        finally:
            try:
                if f_all is not None:
                    f_all.close()
                if f_sel is not None:
                    f_sel.close()
            except Exception:
                pass
            if visa is not None:
                visa.close()


# -------------------------------------------------------------------------------------
# GUI-Frame für Integration in UltimateSyncApp
# -------------------------------------------------------------------------------------
class EconSweepFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)

        self.runner = EconMeasurementRunner(self)
        self.measurement_thread: Optional[threading.Thread] = None

        self._build_vars()
        self._build_ui()
        self.log(f"{APP_TITLE} v{APP_VERSION} bereit")
        self.log("Hinweis: UDP ist komplett entfernt. Alle Mess-/OC-Parameter kommen direkt aus der GUI.")

    def _build_vars(self):
        self.var_connection = tk.StringVar(value="TCPIP::192.168.0.10::INSTR")
        self.var_out_dir = tk.StringVar(value=os.path.abspath("./econ_output"))
        self.var_testbench = tk.StringVar(value="ZH")
        self.var_trial_number = tk.StringVar(value="Trial_001")
        self.var_trial_sequence = tk.StringVar(value="SEQ_A")
        self.var_trial_remark = tk.StringVar(value="Standalone GUI ohne UDP")
        self.var_cell = tk.IntVar(value=1)
        self.var_runtime = tk.StringVar(value="000:00:10:00")
        self.var_ts_counter = tk.IntVar(value=1)
        self.var_cycle_counter = tk.IntVar(value=0)
        self.var_oiltemp_q = tk.DoubleVar(value=25.0)
        self.var_oiltemp_c = tk.DoubleVar(value=25.0)
        self.var_pressure = tk.DoubleVar(value=1.0)
        self.var_speed = tk.DoubleVar(value=0.0)
        self.var_calibration = tk.BooleanVar(value=True)
        self.var_simulation = tk.BooleanVar(value=not RS_AVAILABLE)

        self.var_rshunt = tk.StringVar(value=str(RSHUNT))
        self.var_kdv = tk.StringVar(value=str(KDV))
        self.var_kv = tk.StringVar(value=str(KV))

        self.voltage_vars = []
        for i in range(1, 11):
            v = tk.BooleanVar(value=(i in (1, 5, 10)))
            self.voltage_vars.append(v)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=0, minsize=380)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkScrollableFrame(self, width=380)
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 6), pady=8)

        right = ctk.CTkFrame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 8), pady=8)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass

        self._build_settings_panel(left)
        self._build_log_panel(right)

    def _build_settings_panel(self, parent):
        title = ctk.CTkLabel(parent, text="eCON Sweep Messung", font=ctk.CTkFont(size=18, weight="bold"))
        title.pack(anchor="w", padx=12, pady=(12, 6))
        subtitle = ctk.CTkLabel(parent, text="Standalone-Funktionalität als integrierter Tab", text_color="gray")
        subtitle.pack(anchor="w", padx=12, pady=(0, 10))

        frm_hw = ctk.CTkFrame(parent)
        frm_hw.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(frm_hw, text="Hardware / Modus", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(10, 6))

        self._add_labeled_entry(frm_hw, "VISA Resource", self.var_connection, width=240)
        self._add_labeled_entry(frm_hw, "Output-Ordner", self.var_out_dir, width=240)
        ctk.CTkButton(frm_hw, text="Ordner wählen", width=120, command=self._choose_outdir).pack(anchor="w", padx=12, pady=(0, 8))

        ctk.CTkCheckBox(frm_hw, text="Kalibrierung anwenden", variable=self.var_calibration).pack(anchor="w", padx=12, pady=3)
        ctk.CTkCheckBox(frm_hw, text="Simulation statt VISA/DSO", variable=self.var_simulation).pack(anchor="w", padx=12, pady=(0, 8))

        self._add_labeled_entry(frm_hw, "RSHUNT", self.var_rshunt, width=120)
        self._add_labeled_entry(frm_hw, "KDV", self.var_kdv, width=120)
        self._add_labeled_entry(frm_hw, "KV", self.var_kv, width=120)

        frm_trial = ctk.CTkFrame(parent)
        frm_trial.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(frm_trial, text="Trial / Prüfling", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(10, 6))
        self._add_labeled_entry(frm_trial, "Testbench", self.var_testbench, width=120)
        self._add_labeled_entry(frm_trial, "Trial Number", self.var_trial_number, width=180)
        self._add_labeled_entry(frm_trial, "Trial Sequence", self.var_trial_sequence, width=180)
        self._add_labeled_entry(frm_trial, "Remark", self.var_trial_remark, width=260)
        self._add_labeled_spinbox(frm_trial, "Zelle", self.var_cell, 1, 6)
        self._add_labeled_entry(frm_trial, "Runtime d:hh:mm:ss", self.var_runtime, width=150)
        self._add_labeled_spinbox(frm_trial, "TS Counter", self.var_ts_counter, 0, 999999)
        self._add_labeled_spinbox(frm_trial, "Cycle Counter", self.var_cycle_counter, 0, 999999999)

        frm_oc = ctk.CTkFrame(parent)
        frm_oc.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(frm_oc, text="Operating Conditions", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(10, 6))
        self._add_labeled_entry(frm_oc, "Oiltemp q [°C]", self.var_oiltemp_q, width=120)
        self._add_labeled_entry(frm_oc, "Oiltemp c [°C]", self.var_oiltemp_c, width=120)
        self._add_labeled_entry(frm_oc, "Pressure [bar]", self.var_pressure, width=120)
        self._add_labeled_entry(frm_oc, "Speed [rpm]", self.var_speed, width=120)

        frm_volt = ctk.CTkFrame(parent)
        frm_volt.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(frm_volt, text="eCON-Spannungen (1…10 V)", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(10, 6))
        
        grid = ctk.CTkFrame(frm_volt)

        grid.pack(fill="x", padx=12, pady=(0, 8))
        for i, v in enumerate(self.voltage_vars, start=1):
            cb = ctk.CTkCheckBox(grid, text=f"{i} V", variable=v)
            cb.grid(row=(i-1)//5, column=(i-1)%5, sticky="w", padx=8, pady=4)

        btns = ctk.CTkFrame(parent, fg_color="transparent")
        btns.pack(fill="x", padx=12, pady=(8, 12))
        ctk.CTkButton(btns, text="DSO testen", command=self.on_test_dso).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btns, text="Kalibrierung anzeigen", command=self.on_show_calibration).pack(side="left", padx=(0, 6))
        self.btn_start = ctk.CTkButton(btns, text="eCON Sweep starten", command=self.on_start, fg_color="green", hover_color="darkgreen")
        self.btn_start.pack(side="left", padx=(18, 6))
        self.btn_stop = ctk.CTkButton(btns, text="Stop", command=self.on_stop, state="disabled", fg_color="red", hover_color="darkred")
        self.btn_stop.pack(side="left")

    def _build_log_panel(self, parent):
        title = ctk.CTkLabel(parent, text="Log / Status", font=ctk.CTkFont(size=18, weight="bold"))
        title.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))

        text_frame = ctk.CTkFrame(parent)
        text_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)

        self.txt_log = tk.Text(text_frame, wrap="word", height=30, bg="#1f1f1f", fg="white", insertbackground="white")
        self.txt_log.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(text_frame, orient="vertical", command=self.txt_log.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.txt_log.configure(yscrollcommand=sb.set)

        help_text = (
            "Ablauf der Standalone-Messung:\n"
            "1) Spannungen auswählen\n"
            "2) Trial-/OC-Daten eintragen\n"
            "3) Optional DSO testen\n"
            "4) Sweep starten\n\n"
            "Sweep & Logging entsprechen dem Altprogramm für die eCON-Messung:\n"
            "- Frequenzbereich 10 kHz ... 100 kHz\n"
            "- Impedanz aus Bode-Gain berechnet\n"
            "- optionale Kalibrierung\n"
            "- CSV mit allen Punkten + CSV mit ausgewählten Frequenzen"
        )
        lbl = ctk.CTkLabel(parent, text=help_text, justify="left", anchor="w")
        lbl.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 12))

    def _add_labeled_entry(self, parent, label, variable, width=160):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=3)
        ctk.CTkLabel(row, text=label, width=140, anchor="w").pack(side="left")
        ctk.CTkEntry(row, textvariable=variable, width=width).pack(side="left", padx=(8, 0))

    def _add_labeled_spinbox(self, parent, label, variable, frm, to):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=3)
        ctk.CTkLabel(row, text=label, width=140, anchor="w").pack(side="left")
        sp = ttk.Spinbox(row, textvariable=variable, from_=frm, to=to, width=16)
        sp.pack(side="left", padx=(8, 0))
        return sp

    def _choose_outdir(self):
        selected = filedialog.askdirectory(initialdir=self.var_out_dir.get() or os.getcwd())
        if selected:
            self.var_out_dir.set(selected)

    def log(self, text: str):
        def _append():
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            self.txt_log.insert(tk.END, f"[{timestamp}] {text}\n")
            self.txt_log.see(tk.END)
        self.after(0, _append)

    def collect_config(self) -> MeasurementConfig:
        global RSHUNT, KDV, KV
        try:
            RSHUNT = float(self.var_rshunt.get().replace(',', '.'))
            KDV = float(self.var_kdv.get().replace(',', '.'))
            KV = float(self.var_kv.get().replace(',', '.'))
        except Exception as e:
            raise ValueError("RSHUNT/KDV/KV müssen numerisch sein") from e

        voltages = [i for i, var in enumerate(self.voltage_vars, start=1) if var.get()]
        cfg = MeasurementConfig(
            testbench=self.var_testbench.get().strip(),
            connection_device=self.var_connection.get().strip(),
            out_dir=self.var_out_dir.get().strip(),
            trial_number=self.var_trial_number.get().strip(),
            trial_sequence=self.var_trial_sequence.get().strip(),
            trial_remark=self.var_trial_remark.get().strip(),
            cell=int(self.var_cell.get()),
            measurement_runtime=self.var_runtime.get().strip(),
            ts_counter=int(self.var_ts_counter.get()),
            cycle_counter=int(self.var_cycle_counter.get()),
            oiltemp_q=float(str(self.var_oiltemp_q.get()).replace(',', '.')),
            oiltemp_c=float(str(self.var_oiltemp_c.get()).replace(',', '.')),
            pressure=float(str(self.var_pressure.get()).replace(',', '.')),
            speed=float(str(self.var_speed.get()).replace(',', '.')),
            voltages=voltages,
            use_calibration=bool(self.var_calibration.get()),
            simulation=bool(self.var_simulation.get()),
        )
        parse_runtime_to_seconds(cfg.measurement_runtime)
        return cfg

    def on_show_calibration(self):
        try:
            cfg = self.collect_config()
            R_meas, R_cal, txt = load_calibration_data(cfg.testbench)
            lines = [txt, "", "i | R_cal | R_meas"]
            for i in range(len(R_meas)-1):
                lines.append(f"{i:02d} | {R_cal[i]:9.3f} | {R_meas[i]:9.3f}")
            messagebox.showinfo("Kalibrierung", "\n".join(lines[:40]))
        except Exception as e:
            messagebox.showerror("Fehler", str(e))

    def on_test_dso(self):
        def worker():
            try:
                cfg = self.collect_config()
                if cfg.simulation:
                    self.log("DSO-Test übersprungen: Simulationsmodus aktiv")
                    return
                visa = VisaDevice(cfg.connection_device)
                self.log(f"Teste DSO: {cfg.connection_device}")
                visa.connect()
                idn = visa.query('*IDN?').strip()
                self.log(f"*IDN? -> {idn}")
                enabled = visa.query('BPLot:ENABle?').strip()
                self.log(f"BPLot:ENABle? -> {enabled}")
                visa.prepare_bode()
                frq, gain, phase, err = visa.run_bode(5.0)
                self.log(f"Testmessung fertig, Fehlerflag={err}, Punkte={len(frq)}")
                if frq:
                    self.log(f"Beispiel: {frq[0]:.1f} Hz | Gain={gain[0]:.3f} dB | Phase={phase[0]:.3f} °")
                visa.close()
            except Exception as e:
                self.log("DSO-Test FEHLER")
                self.log(str(e))
                self.log(traceback.format_exc())
                self.after(0, lambda: messagebox.showerror("DSO-Test", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def on_start(self):
        if self.measurement_thread and self.measurement_thread.is_alive():
            messagebox.showwarning("Messung läuft", "Es läuft bereits eine Messung.")
            return
        try:
            cfg = self.collect_config()
        except Exception as e:
            messagebox.showerror("Ungültige Eingaben", str(e))
            return

        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")

        def worker():
            try:
                self.runner.run(cfg)
            except Exception as e:
                self.log("MESSUNG FEHLER")
                self.log(str(e))
                self.log(traceback.format_exc())
                self.after(0, lambda: messagebox.showerror("Messung", str(e)))
            finally:
                self.after(0, lambda: self.btn_start.configure(state="normal"))
                self.after(0, lambda: self.btn_stop.configure(state="disabled"))

        self.measurement_thread = threading.Thread(target=worker, daemon=True)
        self.measurement_thread.start()

    def on_stop(self):
        self.runner.request_stop()
        self.log("Stop angefordert …")


if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = ctk.CTk()
    app.title(APP_TITLE)
    app.geometry("1280x860")
    frame = EconSweepFrame(app)
    frame.pack(fill="both", expand=True)
    app.mainloop()
