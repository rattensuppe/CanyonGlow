CanyonGlow v1.0 - Serieller Treiber

Wenn das Tool den Controller findet, ist der benötigte Treiber bereits vorhanden.
Intel NUC Software Studio wird für dieses Tool nicht benötigt.

Controller und Treiber erkennen:
Der RGB-Controller verwendet eine Prolific-PL2303-USB-zu-Seriell-Brücke. Beim
getesteten NUC 11 Extreme steht im Geräte-Manager unter "Anschlüsse (COM & LPT)"
der Name "Prolific PL2303GD USB Serial COM Port"; der Treiberanbieter ist
"Prolific". Windows ergänzt den Namen um die zugewiesene COM-Portnummer.
Den benötigten seriellen Windows-Treiber stellt Prolific bereit; Windows Update
oder den offiziellen Installer weiter unten verwenden.

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
3. Im Geräte-Manager unter "Anschlüsse (COM & LPT)" nach dem oben genannten
   Prolific-Port suchen. Die auf deinem System angezeigte COM-Portnummer verwenden;
   es ist keine feste Nummer vorgegeben. CanyonGlow nach einer Treiberinstallation neu starten, damit
   die automatische Controller-Erkennung erneut läuft. "Ports laden" aktualisiert
   die Portliste; "Gerät prüfen" fragt die Controller-ID ab und zeigt das Ergebnis
   im Log, schaltet die Sendefunktionen aber nicht selbst frei.

Dieses Verzeichnis enthält nur die Anleitung. Ein Treiber wird weder mitgeliefert
noch durch das Setup des RGB-Tools installiert.
