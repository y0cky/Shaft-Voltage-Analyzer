import customtkinter as ctk

# Importiere die ausgelagerten Tabs
from src.gui.logger_tab import SyncLoggerFrame
from src.gui.viewer_tab import SyncViewerFrame
from src.gui.report_tab import SyncReportFrame  # <-- NEU importiert

# Design-Thema festlegen
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class UltimateSyncApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("RTB2004 Logger & Viewer")
        self.geometry("1400x950")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        # Tabs initialisieren
        self.tab_logger = self.tabview.add("Live Datalogger")
        self.tab_viewer = self.tabview.add("Log-Viewer")
        self.tab_report = self.tabview.add("Vergleichsbericht")  # <-- NEU hinzugefügt

        # Tab 1: Live Logger
        self.logger_module = SyncLoggerFrame(self.tab_logger)
        self.logger_module.pack(fill="both", expand=True)

        # Tab 2: Log-Viewer
        self.viewer_module = SyncViewerFrame(self.tab_viewer)
        self.viewer_module.pack(fill="both", expand=True)

        # Tab 3: Vergleichsbericht
        self.report_module = SyncReportFrame(self.tab_report)  # <-- NEU initialisiert
        self.report_module.pack(fill="both", expand=True)

    def on_closing(self):
        if hasattr(self, 'logger_module'):
            self.logger_module.stop()
        self.destroy()

if __name__ == "__main__":
    app = UltimateSyncApp()
    app.mainloop()