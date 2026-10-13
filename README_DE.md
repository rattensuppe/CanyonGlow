# CanyonGlow v1.0

**RGB-Steuerung für NUC 11 & 12 Extreme**

Grafische Oberfläche zur Steuerung der vier RGB-LED-Zonen des
Intel NUC 11 Extreme (Beast Canyon) und NUC 12 Extreme (Dragon Canyon).
Kommunikation erfolgt direkt über die serielle Schnittstelle des Embedded Controllers.

---

## Unterstützte Hardware

| Modell | Codename | Typische Kit-IDs |
|---|---|---|
| Intel NUC 11 Extreme | Beast Canyon | NUC11BTMi7, NUC11BTMi9 |
| Intel NUC 12 Extreme | Dragon Canyon | NUC12DCMi7, NUC12DCMi9 |

Die Unterstützung ist auf diese beiden Modellreihen beschränkt. Andere
NUC-Modelle (z. B. NUC Mini, NUC Pro oder NUC 13+) werden nicht unterstützt.

---

## RGB-Zonen

Das Gerät hat vier unabhängig steuerbare Zonen:

| Zone | Position |
|---|---|
| **Skull** | Schädel-Logo vorne |
| **Bottom Left** | Unterseite links |
| **Bottom Right** | Unterseite rechts |
| **Bottom Front** | Unterseite vorne |

---

## Features

### Effekte
Jede Zone unterstützt folgende Effekte unabhängig voneinander:

- **Solid** — statische Farbe
- **Pulse** — sanftes Auf- und Abschwellen
- **Breathing** — gleichmäßiges Ein- und Ausblenden
- **Strobe** — Blitzlicht ⚠️
- **Rainbow** — automatischer Farbdurchlauf
- **PT1 / PT2 / PT3** — PulseTrain: dreifarbige Sequenzpalette, die alle PTx-Zonen
  gemeinsam nutzen. Farben werden im Panel „PulseTrain Palette“ eingestellt.
  **Palette senden** überträgt die gemeinsame Palette und die Einstellungen der
  ausgewählten PTx-Zone an den Controller.

> ⚠️ **Pulse und Strobe** senden unterschiedliche Befehle an den Controller (`P2` vs. `P4`),
> können auf dem Gerät aber visuell ähnlich wirken. Die Effekte werden im Controller erzeugt.

### Farbe & Helligkeit

- Farbbalken mit 256 Hue-Werten (HSV-Modell)
- Einrasten auf Standard-Farben (Rot, Orange, Gelb, Grün, Cyan, Blau, Lila, Pink)
- **Shift + Ziehen** auf dem Farbbalken deaktiviert das Einrasten für freie Farbwahl
- Direkte Zahleneingabe im Spinbox-Feld (0–255)
- Helligkeit in 6 Stufen (0–5), global und je Zone
- Helligkeit und Tempo werden rechts für die ausgewählte Zone eingestellt.
  Tempo (0–5) ist nur bei animierten Effekten aktiv. Bei Rainbow erfolgt die
  Farbwahl automatisch; bei PulseTrain wird die gemeinsame Palette verwendet.

### Zonen-Sync

- **SYNC** gleicht Änderungen des Hue-Werts zwischen den verknüpften Zonen in der
  Oberfläche ab. Effekte, Helligkeit und Tempo werden dadurch nicht verknüpft.
- Die geänderten Werte werden erst beim Senden übernommen. **Alle Zonen senden**
  überträgt sie gemeinsam; **senden** in einer Zeile überträgt nur diese Zone.
- **Auf alle Zonen kopieren** kopiert die Einstellungen der ausgewählten Zone in
  alle anderen Zeilen, ebenfalls ohne sofortige Übertragung.

### Globale Steuerung

- **ALLE ZONEN AN / ALLE ZONEN AUS** — zeigt die nächste Aktion an und schaltet
  beim Klick die globale Beleuchtung direkt ein oder aus. Im ausgeschalteten
  Zustand sind die Zonensteuerung und die globale Helligkeit gesperrt; Profile,
  Log, Sprach- und Theme-Auswahl bleiben verfügbar.
- **Globale Helligkeit** — Helligkeitsschieberegler wirkt auf alle Zonen beim Senden
- **Alle Zonen senden** — überträgt alle Zonen und die gemeinsame Palette mit einem Klick

### Profile

- Speichern und Laden von Konfigurationen als `.json`-Datei
- Profilname frei wählbar
- Beispielprofil: `example_default_green_profile.json`
- Laden verändert zunächst nur die Oberfläche. Die geladenen Zoneneinstellungen
  mit **Alle Zonen senden** übernehmen, sobald der Controller erkannt und die globale
  Beleuchtung eingeschaltet ist. SYNC-Verknüpfungen werden nicht gespeichert.

### Oberfläche

- **Dark Mode / Light Mode** umschaltbar
- **Deutsch / Englisch** umschaltbar
- Beim ersten Start gelten Englisch und Dark Mode. Die zuletzt gewählte Sprache
  und der Hell-/Dunkelmodus werden automatisch gespeichert und beim nächsten Start
  wiederhergestellt. Kurze Tooltips folgen der ausgewählten Sprache.
- Log mit gesendeten Befehlen, Statusmeldungen und abgefragten Controller-Antworten
- Log speichern und leeren; übersetzbare Programmmeldungen folgen der ausgewählten
  Sprache, auch bei bereits vorhandenen Einträgen. Rohdaten bleiben unverändert.

---

## Installation und Start (Windows)

Die fertigen Pakete sind für **Windows 10/11 (x64)** vorgesehen. Python und
Python-Pakete sind darin enthalten und müssen nicht separat installiert werden.
Intel NUC Software Studio wird nicht benötigt.

Bei einer neuen Installation ist im Setup Englisch vorausgewählt; Deutsch bleibt
auswählbar. Bei Updates übernimmt das Setup die bisher verwendete Installationssprache.

- **Setup:** `CanyonGlow-v1.0-Setup-x64.exe` starten. Installation erfolgt im
  Benutzerkonto mit Startmenü-Eintrag und optionaler Desktop-Verknüpfung.
- **Portable:** `CanyonGlow-v1.0-Portable-x64.zip` vollständig entpacken und
  `CanyonGlow.exe` im Ordner `CanyonGlow` starten. Den gesamten Ordner einschließlich
  `_internal` zusammenhalten; die EXE allein reicht nicht aus.

Der serielle Gerätetreiber muss vorhanden sein. Hinweise zu Windows Update und
zum offiziellen Prolific-Download stehen in [drivers/README_DE.txt](drivers/README_DE.txt).

Beim Start sucht das Tool nach dem Prolific/PL2303-Controller und liest dessen
Status. Nach erfolgreicher Erkennung werden die Zoneneinstellungen aus dem Gerät
übernommen. Senden ist verfügbar, wenn die globale Beleuchtung eingeschaltet ist.
Ohne erkannten Controller
können Profile vorbereitet, gespeichert und geladen werden; Senden ist gesperrt.

Mit **Ports laden** wird die Portliste aktualisiert. Ein Port kann oben rechts
ausgewählt oder manuell eingetragen werden. **Gerät prüfen** fragt die Controller-ID
ab und protokolliert das Ergebnis; es ersetzt die automatische Statuserkennung
beim Start nicht. Nach einer Treiberinstallation oder bei behobenen
Verbindungsproblemen das Tool neu starten.

Farbe, Effekt, Helligkeit, Tempo und die EIN/AUS-Schalter einzelner Zonen verändern
zunächst nur die Oberfläche. Zur Übertragung **senden**, **Alle Zonen senden** oder
**Palette senden** verwenden. Die globale EIN/AUS-Taste und **Werksreset** wirken
direkt auf den Controller.

---

## Aktualisieren und Deinstallieren

Für ein Update das neue Setup ausführen. Der vorhandene Installationsordner
wird weiterverwendet; bisherige Programmverknüpfungen werden bei der
Umbenennung durch CanyonGlow-Verknüpfungen ersetzt. Startmenü- und
Desktop-Verknüpfungen verwenden den Dokumente-Ordner als Arbeitsverzeichnis.

Die Setup-Installation lässt sich über die Windows-Einstellungen unter Apps
deinstallieren. Zusätzlich angelegte Profil-Dateien werden nicht gelöscht.
Die Portable-Version benötigt keine Installation oder Deinstallation.

Die Pakete sind derzeit unsigniert.

Sprache und Darstellung werden pro Windows-Benutzer in
`%LOCALAPPDATA%\CanyonGlow\settings.json` gespeichert. Setup- und Portable-Version
verwenden dieselbe Datei. Diese Einstellungen bleiben auch bei Updates erhalten.

---

## Profil-Format

Profile werden als UTF-8-kodiertes JSON gespeichert:

```json
{
  "name": "Mein Profil",
  "all_enabled": true,
  "pulse_train_hues": [0, 96, 160],
  "zones": {
    "Skull": {
      "enabled": true,
      "pattern": "Solid",
      "brightness": 5,
      "frequency": 0,
      "custom_hue": 96
    }
  }
}
```

Effekte in der Oberfläche: `Solid`, `Pulse`, `Breathing`, `Strobe`, `PT1`, `PT2`, `PT3`, `Rainbow`  
Hue-Bereich: `0–255` · Helligkeit: `0–5` · Tempo: `0–5`

Das Beispiel zeigt nur eine Zone. Beim Speichern werden alle vier Zonen geschrieben;
beim Laden fehlende Zonen erhalten Standardwerte. Ausschalten wird über `enabled`
gespeichert. Die bestehenden JSON-Profile bleiben nutzbar.

---

## Serielle Kommunikation

Der Controller kommuniziert über einen virtuellen COM-Port (USB).
Die tatsächliche Portnummer wird vom Betriebssystem vergeben und kann von `COM3`
abweichen. `COM3` ist nur ein Fallback-Wert, falls keine Ports erkannt werden.

Nach jedem Öffnen des Ports wartet die Software **2 Sekunden** vor dem ersten
Befehl. Zwischen einzelnen Befehlen liegen **0,1 Sekunden**. Ein Sendevorgang kann
deshalb etwas dauern; weitere Sendevorgänge werden nacheinander abgearbeitet.

---

## Projekt- und Lizenzhinweise

Unabhängiges Werkzeug. Keine offizielle Unterstützung durch Intel oder ASUS.
CanyonGlow und das eigene CanyonGlow-Icon stehen unter der [MIT-Lizenz](LICENSE),
Copyright (c) 2026 rattensuppe. Nutzung, Änderung und Weitergabe sind erlaubt;
Copyright- und Lizenzhinweise müssen erhalten bleiben.
Die Lizenztexte der mitgelieferten Laufzeitkomponenten liegen im Ordner `licenses`.
Hinweise zu übernommenen Bestandteilen und deren Lizenzen stehen in
[THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt).

---

## Danksagung

Inspiriert durch das Projekt **nuc_rgb** von Alvin Zhu:
[nuc_rgb auf GitHub](https://github.com/AlvinZhu/nuc_rgb) —
als Grundlage für das Verständnis des seriellen Controller-Protokolls.

---

## Hinweis zur Entstehung

Die ursprüngliche Fassung entstand mit Unterstützung von
[Claude Code](https://claude.ai/code) (Anthropic). Spätere Überarbeitungen erfolgten
mit Unterstützung von Codex (OpenAI).
