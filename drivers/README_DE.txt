CanyonGlow v1.0 - Serieller Treiber

Wenn das Tool den Controller findet, ist der benötigte Treiber bereits vorhanden.
Intel NUC Software Studio wird für dieses Tool nicht benötigt.

Falls kein Controller gefunden wird:
1. Windows Update öffnen und nach Updates suchen. Prolific stellt den passenden
   seriellen Treiber über Windows Update bereit. Falls angeboten, auch unter
   "Optionale Updates" nach Prolific-Treiberupdates sehen.
2. Falls Windows Update keinen passenden Treiber installiert, den offiziellen
   Prolific-Download verwenden:
   https://www.prolific.com.tw/en/portfolio-item/pl2303gd/
   Unter "Drivers & Software" den "Windows Driver Installer Setup Program"
   für die verwendete Windows-Version herunterladen. ZIP entpacken und den
   enthaltenen Installer starten; gegebenenfalls Windows neu starten.
3. Im Geräte-Manager unter "Anschlüsse (COM & LPT)" nach einem Prolific-Port
   suchen, z. B. "Prolific PL2303GD USB Serial COM Port (COM3)". Die COM-Nummer
   kann abweichen. CanyonGlow nach einer Treiberinstallation neu starten, damit
   die automatische Controller-Erkennung erneut läuft. "Ports laden" aktualisiert
   die Portliste; "Gerät prüfen" fragt die Controller-ID ab und zeigt das Ergebnis
   im Log, schaltet die Sendefunktionen aber nicht selbst frei.

Dieses Verzeichnis enthält nur die Anleitung. Ein Treiber wird weder mitgeliefert
noch durch das Setup des RGB-Tools installiert.
