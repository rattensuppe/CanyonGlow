#!/usr/bin/env python3
"""
CanyonGlow v1.0 — RGB Control for NUC 11 & 12 Extreme.

Four-zone RGB control with profiles, light/dark mode and DE/EN language switching.
"""

from __future__ import annotations

import colorsys
import json
import os
import platform
import queue
import threading
import tempfile
import time
import tkinter as tk
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, fields as dc_fields
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Dict, Iterable, List, Optional

try:
    import serial
    from serial.tools import list_ports
except ImportError as exc:
    serial = None
    list_ports = None
    SERIAL_IMPORT_ERROR = exc
else:
    SERIAL_IMPORT_ERROR = None


APP_NAME = "CanyonGlow"
APP_VERSION = "v1.0"
TIME_START = 2.0   # hardware-mandated: controller processes only one request at a time
TIME_CMD   = 0.10
DEFAULT_TIMEOUT = 3

DEFAULT_PORT_WINDOWS = "COM3"
DEFAULT_PORT_LINUX   = "/dev/ttyACM0"


def ui_settings_path() -> Path:
    if platform.system() == "Windows":
        base = Path(os.environ["LOCALAPPDATA"]) if os.environ.get("LOCALAPPDATA") else Path.home() / "AppData" / "Local"
    else:
        base = Path(os.environ["XDG_CONFIG_HOME"]) if os.environ.get("XDG_CONFIG_HOME") else Path.home() / ".config"
    return base / APP_NAME / "settings.json"


def read_ui_settings(path: Path) -> dict:
    settings = {"language": "en", "theme": "dark"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return settings
    if isinstance(data, dict):
        if data.get("language") in ("en", "de"):
            settings["language"] = data["language"]
        if data.get("theme") in ("dark", "light"):
            settings["theme"] = data["theme"]
    return settings


def write_ui_settings(path: Path, *, language: str, theme: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".settings-",
                                         suffix=".tmp", dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            json.dump({"language": language, "theme": theme}, output, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


ZONES = {
    "Skull":        {"prefix": "A", "color_index": 1},
    "Bottom Left":  {"prefix": "B", "color_index": 2},
    "Bottom Right": {"prefix": "C", "color_index": 3},
    "Bottom Front": {"prefix": "D", "color_index": 4},
}

PATTERNS = {
    "Off": 0, "Solid": 1, "Pulse": 2, "Breathing": 3,
    "Strobe": 4, "PT1": 5, "PT2": 6, "PT3": 7, "Rainbow": 8,
}
EFFECT_OPTIONS      = ["Solid", "Pulse", "Breathing", "Strobe", "PT1", "PT2", "PT3", "Rainbow"]
PATTERN_ALIASES     = {
    "PulseTrain1": "PT1", "PulseTrain2": "PT2", "PulseTrain3": "PT3",
    "Strobing": "Strobe", "Rainbow1": "Rainbow",
}
ANIMATED_PATTERNS   = {"Pulse", "Breathing", "Strobe", "PT1", "PT2", "PT3", "Rainbow"}
PULSETRAIN_PATTERNS = {"PT1", "PT2", "PT3"}

COLORS = {
    "Red": 0, "Orange": 32, "Yellow": 70, "Green": 96,
    "Cyan": 128, "Blue": 160, "Purple": 192, "Pink": 224,
}
STANDARD_HUE_MARKERS       = tuple(COLORS.items())
STANDARD_HUE_EXACT         = {v: k for k, v in STANDARD_HUE_MARKERS}
STANDARD_HUE_SNAP_TOLERANCE = 3
STANDARD_HUE_NEAR_TOLERANCE = 4
COLOR_BY_ID  = {v: k for k, v in COLORS.items()}
PATTERN_BY_ID = {v: k for k, v in PATTERNS.items()}

# ── Theme palette ─────────────────────────────────────────────────────────────
C_BG            = "#0f131a"
C_SURFACE       = "#151b24"
C_ROW           = "#111720"
C_BORDER        = "#263244"
C_BORDER_ROW    = "#253045"
C_TEXT          = "#e6edf3"
C_WHITE         = "#ffffff"
C_MUTED         = "#8fa3bd"
C_DIM           = "#657080"
C_SUBTLE        = "#9aa7b8"
C_TEAL          = "#2dd4bf"
C_TEAL_HOVER    = "#5eead4"
C_TEAL_ON       = "#061816"
C_BLUE          = "#58a6ff"
C_BLUE_HOVER    = "#79c0ff"
C_BLUE_ON       = "#07111f"
C_BLUE_DARK     = "#2f6fa8"
C_BLUE_DARK_HOV = "#3d83c2"
C_BTN           = "#242a36"
C_BTN_HOVER     = "#303849"
C_BTN_DIS       = "#171c25"
C_BTN_DIS_FG    = "#677080"
C_SWITCH_DIS    = "#1b222e"
C_DANGER_BG     = "#3a2327"
C_DANGER_FG     = "#ffb4b4"
C_DANGER_HOV    = "#4a2c32"
C_SUCCESS_BG    = "#1f3a2b"
C_SUCCESS_FG    = "#b7f7c7"
C_SUCCESS_HOV   = "#285038"
C_PILL          = "#263244"
C_HUE_EXACT_BG  = "#163a31"
C_HUE_EXACT_BTN = "#1f5a4b"
C_HUE_EXACT_FG  = "#d6fff8"
C_HUE_NEAR_BG   = "#2a2d1b"
C_HUE_NEAR_BTN  = "#4b4522"
C_HUE_NEAR_FG   = "#fff4b8"
C_LOG_BG        = "#0b0f16"
C_LOG_FG        = "#d8dee9"
C_MINI_FG       = "#9fb1c8"
C_ZONE_APPLY_FG = "#eaf4ff"
# ─────────────────────────────────────────────────────────────────────────────

DARK_PAL: dict = {
    "BG": C_BG, "SURFACE": C_SURFACE, "ROW": C_ROW,
    "BORDER": C_BORDER, "BORDER_ROW": C_BORDER_ROW,
    "TEXT": C_TEXT, "WHITE": C_WHITE, "MUTED": C_MUTED,
    "DIM": C_DIM, "SUBTLE": C_SUBTLE, "MINI_FG": C_MINI_FG,
    "TEAL": C_TEAL, "TEAL_HOVER": C_TEAL_HOVER, "TEAL_ON": C_TEAL_ON,
    "BLUE": C_BLUE, "BLUE_HOVER": C_BLUE_HOVER, "BLUE_ON": C_BLUE_ON,
    "BLUE_DARK": C_BLUE_DARK, "BLUE_DARK_HOV": C_BLUE_DARK_HOV,
    "BTN": C_BTN, "BTN_HOVER": C_BTN_HOVER, "BTN_DIS": C_BTN_DIS, "BTN_DIS_FG": C_BTN_DIS_FG,
    "SWITCH_DIS": C_SWITCH_DIS,
    "DANGER_BG": C_DANGER_BG, "DANGER_FG": C_DANGER_FG, "DANGER_HOV": C_DANGER_HOV,
    "SUCCESS_BG": C_SUCCESS_BG, "SUCCESS_FG": C_SUCCESS_FG, "SUCCESS_HOV": C_SUCCESS_HOV,
    "PILL": C_PILL,
    "HUE_EXACT_BG": C_HUE_EXACT_BG, "HUE_EXACT_BTN": C_HUE_EXACT_BTN, "HUE_EXACT_FG": C_HUE_EXACT_FG,
    "HUE_NEAR_BG": C_HUE_NEAR_BG, "HUE_NEAR_BTN": C_HUE_NEAR_BTN, "HUE_NEAR_FG": C_HUE_NEAR_FG,
    "LOG_BG": C_LOG_BG, "LOG_FG": C_LOG_FG, "ZONE_APPLY_FG": C_ZONE_APPLY_FG,
}

LIGHT_PAL: dict = {
    "BG": "#f0f4f8", "SURFACE": "#ffffff", "ROW": "#f4f7fa",
    "BORDER": "#c0cfe0", "BORDER_ROW": "#bccad8",
    "TEXT": "#1a2332", "WHITE": "#ffffff", "MUTED": "#5a7090",
    "DIM": "#8fa8be", "SUBTLE": "#4a6480", "MINI_FG": "#5a7090",
    "TEAL": "#0d9488", "TEAL_HOVER": "#0f766e", "TEAL_ON": "#ffffff",
    "BLUE": "#2563eb", "BLUE_HOVER": "#1d4ed8", "BLUE_ON": "#ffffff",
    "BLUE_DARK": "#1e40af", "BLUE_DARK_HOV": "#1e3a8a",
    "BTN": "#e2e8f0", "BTN_HOVER": "#cbd5e1", "BTN_DIS": "#f1f5f9", "BTN_DIS_FG": "#94a3b8",
    "SWITCH_DIS": "#e8eef4",
    "DANGER_BG": "#fef2f2", "DANGER_FG": "#dc2626", "DANGER_HOV": "#fee2e2",
    "SUCCESS_BG": "#f0fdf4", "SUCCESS_FG": "#16a34a", "SUCCESS_HOV": "#dcfce7",
    "PILL": "#dde5ef",
    "HUE_EXACT_BG": "#d1fae5", "HUE_EXACT_BTN": "#a7f3d0", "HUE_EXACT_FG": "#065f46",
    "HUE_NEAR_BG": "#fef3c7", "HUE_NEAR_BTN": "#fde68a", "HUE_NEAR_FG": "#78350f",
    "LOG_BG": "#f8fafc", "LOG_FG": "#1a2332", "ZONE_APPLY_FG": "#ffffff",
}

PAL: dict = dict(DARK_PAL)  # mutable current palette — updated on theme switch

STRINGS: dict = {
    "de": {
        "title": APP_NAME,
        "subtitle": "RGB-Steuerung für NUC 11 & 12 Extreme",
        "port_label": "Port",
        "refresh": "Ports laden",
        "test_id": "Gerät prüfen",
        "controller_found": "✔  Controller gefunden  ·  {port}",
        "controller_found_status": "Controller gefunden auf {port}",
        "controller_searching": "● Suche Controller …",
        "controller_missing": "✘  Kein Controller  ·  Profil-Modus",
        "tooltip_refresh": "Liste der seriellen Ports aktualisieren.",
        "tooltip_test_id": "Controller-ID am gewählten Port abfragen; Ergebnis im Log.",
        "tooltip_read_status": "Geräteeinstellungen in die Oberfläche einlesen.",
        "tooltip_reset": "Gerät sofort zurücksetzen und Status neu einlesen.",
        "tooltip_power_off": "Gesamte Beleuchtung sofort ausschalten.",
        "tooltip_power_on": "Gesamte Beleuchtung sofort einschalten.",
        "tooltip_save": "Aktuelle Einstellungen als JSON-Profil speichern.",
        "tooltip_load": "Profil in die Oberfläche laden; zum Übernehmen senden.",
        "tooltip_theme_light": "Zur hellen Oberfläche wechseln.",
        "tooltip_theme_dark": "Zur dunklen Oberfläche wechseln.",
        "tooltip_language": "Sprache der Oberfläche und Programmmeldungen wechseln.",
        "tooltip_brightness_all": "Helligkeit aller Zonen ändern; zum Übernehmen senden.",
        "tooltip_copy_to_all": "Einstellungen dieser Zone auf alle kopieren; danach senden.",
        "tooltip_apply_all": "Alle Zoneneinstellungen und die gemeinsame Palette senden.",
        "tooltip_apply_palette": "Gemeinsame Palette und gewählte PulseTrain-Zone senden.",
        "tooltip_save_log": "Angezeigtes Log als Textdatei speichern.",
        "tooltip_clear": "Angezeigtes Log leeren.",
        "tooltip_zone_power": "Diese Zone ein- oder ausschalten; danach senden.",
        "tooltip_zone_sync": "Farbänderungen zwischen SYNC-Zonen abgleichen; danach senden.",
        "tooltip_zone_send": "Nur die Einstellungen dieser Zone senden.",
        "tooltip_zone_effect": "Effekt für diese Zone wählen; danach senden.",
        "dialog_save_profile": "Profil speichern",
        "dialog_load_profile": "Profil laden",
        "dialog_all_files": "Alle Dateien",
        "read_status": "Status abrufen",
        "reset": "Werksreset",
        "all_zones_on":  "ALLE ZONEN AN",
        "all_zones_off": "ALLE ZONEN AUS",
        "brightness_all": "Globale Helligkeit",
        "profile_label": "Profil",
        "save": "Speichern",
        "load": "Laden",
        "theme_to_light": "☀ Hell",
        "theme_to_dark": "☾ Dunkel",
        "zones_title": "Zonen",
        "zones_hint": "Änderungen werden erst mit „senden“ übertragen. · Shift + Farbbalken: freie Farbwahl ohne Einrasten.",
        "copy_to_all": "Auf alle Zonen kopieren",
        "apply_all": "Alle Zonen senden",
        "selected_zone": "Ausgewählte Zone",
        "brightness": "Helligkeit",
        "tempo": "Tempo",
        "tempo_hint_default": "Nur aktiv bei animierten Effekten.",
        "pt_title": "PulseTrain Palette",
        "pt_hint": "Wähle PT1, PT2 oder PT3 als Effekt.",
        "pt_names": ["C5 Farbe 1", "C6 Farbe 2", "C7 Farbe 3"],
        "apply_palette": "Palette senden",
        "tab_basic": "Steuerung",
        "tab_log":   "Log",
        "log_title": "Log",
        "save_log_btn": "Log speichern",
        "clear": "Leeren",
        "ein": "EIN", "aus": "AUS", "link": "SYNC",
        "apply_zone": "senden",
        "zone_off_dot": "Zone aus.",
        "tempo_active": "Wirksam bei Pulse, Blink, Rainbow.",
        "tempo_inactive": "Tempo bei diesem Effekt inaktiv.",
        "pt_this_zone": "Gemeinsame Palette für alle PTx-Zonen.",
        "pt_inactive": "Wähle PT1, PT2 oder PT3 als Effekt.",
        "note_pt": "nutzt PulseTrain-Palette",
        "note_rainbow": "Rainbow · Farben automatisch",
        "note_off": "Zone aus",
        "note_link_ready": "Sync · kein Partner",
        "note_link": "Sync: ",
        "note_color_c": "Farbe C",
        "log_ready": "Bereit",
        "log_running": "{label}: läuft",
        "log_worker_result": "{label}: {result}",
        "log_error": "FEHLER: {message}",
        "log_command": "Befehl: {command}",
        "log_dry_run_send": "Dry Run aktiv: nicht gesendet",
        "log_queued": "{label}: wird seriell in die Warteschlange gestellt",
        "log_profile_apply": "Profil anwenden",
        "log_zone_apply": "{zone} anwenden",
        "log_palette_apply": "PulseTrain-Palette anwenden",
        "log_power_on": "Alle Zonen an",
        "log_power_off": "Alle Zonen aus",
        "log_zone_copied": "{zone} auf alle Zonen kopiert",
        "log_ports_found": "Ports gefunden: {count}",
        "log_no_controller_startup": "Startup: kein Prolific/PL2303-Controller gefunden.",
        "log_invalid_status_response": "Port {port}: keine gültige STA?-Antwort ({raw!r})",
        "log_startup_error": "Startup-Fehler ({port}): {error}",
        "log_status_apply_error": "Status konnte nicht in UI übernommen werden: {error}",
        "log_dry_run_reset": "Dry Run aktiv: Reset nicht gesendet",
        "log_reset_status": "Reset + Status",
        "log_dry_run_status": "Dry Run aktiv: Status nicht gelesen",
        "log_status": "Status",
        "log_dry_run_id": "Dry Run aktiv: ID-Test nicht gesendet",
        "log_controller_id": "Controller ID",
        "log_saved": "Log gespeichert: {path}",
        "log_preferences_save_failed": "Sprache und Darstellung konnten nicht gespeichert werden: {error}",
        "log_profile_saved": "Profil gespeichert: {path}",
        "log_profile_loaded": "Profil geladen: {path}",
        "log_effect_check_ok": "Interner Effekt-Check OK: Effektbefehle und STA?-Decoder",
        "log_effect_check_failed": "Interner Effekt-Check FEHLER: {details}",
        "log_effect_part_missing": "{pattern}: {part} fehlt in {command}",
        "log_decoder_expected": "STA?-Decoder: {flags} muss {pattern} ergeben",
        "log_effect_command_mismatch": "{pattern}-Befehl stimmt nicht",
        "log_off_option_invalid": "Off darf nicht in EFFECT_OPTIONS stehen",
        "log_serial_missing": "pyserial ist nicht installiert: {error}",
        "log_status_length": "Unerwartete Statuslänge {length}: {raw!r}",
        "log_port_missing": "Kein Serial-Port ausgewählt",
    },
    "en": {
        "title": APP_NAME,
        "subtitle": "RGB Control for NUC 11 & 12 Extreme",
        "port_label": "Port",
        "refresh": "Scan Ports",
        "test_id": "Check Device",
        "controller_found": "✔  Controller found  ·  {port}",
        "controller_found_status": "Controller found on {port}",
        "controller_searching": "● Searching for controller …",
        "controller_missing": "✘  No controller  ·  Profile mode",
        "tooltip_refresh": "Refresh the list of serial ports.",
        "tooltip_test_id": "Query the selected port's controller ID; see the Log.",
        "tooltip_read_status": "Read device settings into the interface.",
        "tooltip_reset": "Reset device settings immediately, then read status.",
        "tooltip_power_off": "Switch all lighting off immediately.",
        "tooltip_power_on": "Switch all lighting on immediately.",
        "tooltip_save": "Save current settings as a JSON profile.",
        "tooltip_load": "Load a profile into the interface; send to apply.",
        "tooltip_theme_light": "Switch to the light interface.",
        "tooltip_theme_dark": "Switch to the dark interface.",
        "tooltip_language": "Change the language of the interface and program messages.",
        "tooltip_brightness_all": "Change brightness for all zones; send to apply.",
        "tooltip_copy_to_all": "Copy this zone's settings to all zones; send to apply.",
        "tooltip_apply_all": "Send all zone settings and the shared palette.",
        "tooltip_apply_palette": "Send the shared palette and selected PulseTrain zone.",
        "tooltip_save_log": "Save the displayed log as a text file.",
        "tooltip_clear": "Clear the displayed log.",
        "tooltip_zone_power": "Enable or disable this zone; send to apply.",
        "tooltip_zone_sync": "Mirror colour changes between SYNC zones; send to apply.",
        "tooltip_zone_send": "Send settings for this zone only.",
        "tooltip_zone_effect": "Choose an effect for this zone; send to apply.",
        "dialog_save_profile": "Save profile",
        "dialog_load_profile": "Load profile",
        "dialog_all_files": "All files",
        "read_status": "Read Status",
        "reset": "Factory Reset",
        "all_zones_on":  "ALL ZONES ON",
        "all_zones_off": "ALL ZONES OFF",
        "brightness_all": "Global Brightness",
        "profile_label": "Profile",
        "save": "Save",
        "load": "Load",
        "theme_to_light": "☀ Light",
        "theme_to_dark": "☾ Dark",
        "zones_title": "Zones",
        "zones_hint": "Changes are only transferred when you click 'send'. · Shift + colour bar: free colour selection without snapping.",
        "copy_to_all": "Copy to All Zones",
        "apply_all": "Send All",
        "selected_zone": "Selected Zone",
        "brightness": "Brightness",
        "tempo": "Speed",
        "tempo_hint_default": "Active for animated effects only.",
        "pt_title": "PulseTrain Palette",
        "pt_hint": "Select PT1, PT2 or PT3 as effect.",
        "pt_names": ["C5 Color 1", "C6 Color 2", "C7 Color 3"],
        "apply_palette": "Send Palette",
        "tab_basic": "Control",
        "tab_log":   "Log",
        "log_title": "Log",
        "save_log_btn": "Save Log",
        "clear": "Clear",
        "ein": "ON", "aus": "OFF", "link": "SYNC",
        "apply_zone": "send",
        "zone_off_dot": "Zone off.",
        "tempo_active": "Active for Pulse, Blink, Rainbow.",
        "tempo_inactive": "Speed inactive for this effect.",
        "pt_this_zone": "Shared palette across all PTx zones.",
        "pt_inactive": "Select PT1, PT2 or PT3 as effect.",
        "note_pt": "uses PulseTrain palette",
        "note_rainbow": "Rainbow · colors automatic",
        "note_off": "Zone off",
        "note_link_ready": "Sync · no partner",
        "note_link": "Sync: ",
        "note_color_c": "Color C",
        "log_ready": "Ready",
        "log_running": "{label}: running",
        "log_worker_result": "{label}: {result}",
        "log_error": "ERROR: {message}",
        "log_command": "Command: {command}",
        "log_dry_run_send": "Dry run active: not sent",
        "log_queued": "{label}: queued for serial transmission",
        "log_profile_apply": "Apply profile",
        "log_zone_apply": "Apply {zone}",
        "log_palette_apply": "Apply PulseTrain palette",
        "log_power_on": "All zones on",
        "log_power_off": "All zones off",
        "log_zone_copied": "{zone} copied to all zones",
        "log_ports_found": "Ports found: {count}",
        "log_no_controller_startup": "Startup: no Prolific/PL2303 controller found.",
        "log_invalid_status_response": "Port {port}: no valid STA? response ({raw!r})",
        "log_startup_error": "Startup error ({port}): {error}",
        "log_status_apply_error": "Could not apply status to the UI: {error}",
        "log_dry_run_reset": "Dry run active: reset not sent",
        "log_reset_status": "Reset + status",
        "log_dry_run_status": "Dry run active: status not read",
        "log_status": "Status",
        "log_dry_run_id": "Dry run active: ID check not sent",
        "log_controller_id": "Controller ID",
        "log_saved": "Log saved: {path}",
        "log_preferences_save_failed": "Could not save language and appearance: {error}",
        "log_profile_saved": "Profile saved: {path}",
        "log_profile_loaded": "Profile loaded: {path}",
        "log_effect_check_ok": "Internal effect check OK: effect commands and STA? decoder",
        "log_effect_check_failed": "Internal effect check ERROR: {details}",
        "log_effect_part_missing": "{pattern}: {part} missing from {command}",
        "log_decoder_expected": "STA? decoder: {flags} must yield {pattern}",
        "log_effect_command_mismatch": "Incorrect {pattern} command",
        "log_off_option_invalid": "Off must not be included in EFFECT_OPTIONS",
        "log_serial_missing": "pyserial is not installed: {error}",
        "log_status_length": "Unexpected status length {length}: {raw!r}",
        "log_port_missing": "No serial port selected",
    },
}


class LocalizedMessage:
    """Keep message values intact so logs can be rendered in either language."""

    def __init__(self, key: str, **values):
        self.key = key
        self.values = values

    def render(self, lang: str) -> str:
        def render_value(value):
            if isinstance(value, LocalizedMessage):
                return value.render(lang)
            if isinstance(value, (list, tuple)):
                return " | ".join(str(render_value(item)) for item in value)
            return value

        return STRINGS[lang][self.key].format(**{
            key: render_value(value) for key, value in self.values.items()
        })

    def __str__(self) -> str:
        return self.render("de")


def exception_message(exc: Exception) -> str | LocalizedMessage:
    if len(exc.args) == 1 and isinstance(exc.args[0], LocalizedMessage):
        return exc.args[0]
    return str(exc)


@dataclass
class ZoneConfig:
    enabled:    bool = True
    pattern:    str  = "Solid"
    brightness: int  = 5
    frequency:  int  = 0
    rainbow:    bool = False
    custom_hue: int  = 96


@dataclass
class Profile:
    name:             str
    all_enabled:      bool
    zones:            Dict[str, ZoneConfig]
    pulse_train_hues: List[int] = field(default_factory=lambda: [0, 96, 160])


_ZONE_CONFIG_FIELDS = {f.name for f in dc_fields(ZoneConfig)}


# ── Helper functions ──────────────────────────────────────────────────────────

def clamp_int(value, minimum: int, maximum: int) -> int:
    try:
        ivalue = int(float(value))
    except Exception:
        ivalue = minimum
    return max(minimum, min(maximum, ivalue))


def normalize_pattern(pattern: str) -> str:
    pattern = str(pattern)
    pattern = PATTERN_ALIASES.get(pattern, pattern)
    return pattern if pattern in PATTERNS else "Solid"


def hue_to_hex(hue: int, value: float = 1.0) -> str:
    hue = clamp_int(hue, 0, 255)
    r, g, b = colorsys.hsv_to_rgb(hue / 256.0, 1.0, max(0.08, min(1.0, value)))
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def nearest_standard_hue(hue: int) -> tuple[str, int, int]:
    hue = clamp_int(hue, 0, 255)
    best_name, best_value = min(STANDARD_HUE_MARKERS, key=lambda item: abs(item[1] - hue))
    return best_name, best_value, abs(best_value - hue)


def snap_standard_hue(hue: int, tolerance: int = STANDARD_HUE_SNAP_TOLERANCE) -> int:
    _name, value, distance = nearest_standard_hue(hue)
    return value if distance <= tolerance else clamp_int(hue, 0, 255)


def standard_hue_note(hue: int) -> str:
    name, value, distance = nearest_standard_hue(hue)
    if distance == 0:
        return f"Standard: {name} · {value}"
    return ""


def nearest_color_name(hue: int) -> str:
    hue = clamp_int(hue, 0, 255)
    if hue in COLOR_BY_ID:
        return COLOR_BY_ID[hue]
    best_name, best_dist = "Custom", 999
    for name, ref in COLORS.items():
        d = min(abs(hue - ref), 256 - abs(hue - ref))
        if d < best_dist:
            best_name, best_dist = name, d
    return f"{best_name} ±{best_dist}"


def build_zone_commands(zone_name: str, cfg: ZoneConfig) -> List[str]:
    zone        = ZONES[zone_name]
    prefix      = zone["prefix"]
    color_index = zone["color_index"]

    pattern_name = normalize_pattern(cfg.pattern)
    enabled      = False if pattern_name == "Off" else bool(cfg.enabled)
    hue          = clamp_int(cfg.custom_hue, 0, 255)

    if not enabled:
        return [
            f"{prefix}P{PATTERNS['Off']}", f"{prefix}V:0",
            f"{prefix}R:0", f"{prefix}D:0", f"C{color_index}:{hue}",
        ]
    if pattern_name == "Solid":
        return [
            f"{prefix}P{PATTERNS['Solid']}", f"{prefix}V:{clamp_int(cfg.brightness, 0, 5)}",
            f"{prefix}R:0", f"{prefix}D:0", f"C{color_index}:{hue}",
        ]
    if pattern_name == "Rainbow":
        return [
            f"{prefix}P{PATTERNS['Solid']}", f"{prefix}V:{clamp_int(cfg.brightness, 0, 5)}",
            f"{prefix}R:1", f"{prefix}D:{clamp_int(cfg.frequency, 0, 5)}",
        ]
    return [
        f"{prefix}P{PATTERNS[pattern_name]}",
        f"{prefix}V:{clamp_int(cfg.brightness, 0, 5)}",
        f"{prefix}R:0",
        f"{prefix}D:{clamp_int(cfg.frequency, 0, 5) if pattern_name in ANIMATED_PATTERNS else 0}",
        f"C{color_index}:{hue}",
    ]


_PT_DEFAULTS = [0, 96, 160]


def _pad_pt_hues(hues) -> List[int]:
    result = list(hues)[:3]
    while len(result) < 3:
        result.append(_PT_DEFAULTS[len(result)])
    return result


def profile_to_commands(profile: Profile) -> str:
    commands = [f"BTN:{1 if profile.all_enabled else 0}"]
    for zone_name, cfg in profile.zones.items():
        commands.extend(build_zone_commands(zone_name, cfg))
    pt = _pad_pt_hues(profile.pulse_train_hues or _PT_DEFAULTS)
    commands.extend([
        f"C5:{clamp_int(pt[0], 0, 255)}",
        f"C6:{clamp_int(pt[1], 0, 255)}",
        f"C7:{clamp_int(pt[2], 0, 255)}",
    ])
    return ",".join(commands)


def expected_command_for(zone_name: str, pattern_name: str, hue: int = 96, brightness: int = 5, frequency: int = 2) -> str:
    return ",".join(build_zone_commands(zone_name, ZoneConfig(True, pattern_name, brightness, frequency, False, hue)))


def pattern_from_status(pattern_id: int, rainbow_flag: int | bool) -> str:
    if bool(rainbow_flag):
        return "Rainbow"
    return PATTERN_BY_ID.get(int(pattern_id), str(pattern_id))


# ── Serial backend ────────────────────────────────────────────────────────────

class NucRgbSerial:
    def __init__(self, port: str, timeout: int = DEFAULT_TIMEOUT):
        if serial is None:
            raise RuntimeError(LocalizedMessage("log_serial_missing", error=str(SERIAL_IMPORT_ERROR)))
        self.port    = port
        self.timeout = timeout

    @staticmethod
    def default_port() -> str:
        if platform.system() == "Windows":
            return DEFAULT_PORT_WINDOWS
        if platform.system() == "Linux":
            return DEFAULT_PORT_LINUX
        return ""

    @staticmethod
    def list_serial_ports() -> List[str]:
        if list_ports is None:
            return []
        ports = []
        for p in list_ports.comports():
            parts = [p.device]
            if p.description:
                parts.append(p.description)
            if p.vid is not None and p.pid is not None:
                parts.append(f"VID:PID={p.vid:04X}:{p.pid:04X}")
            ports.append(" | ".join(parts))
        return ports

    @staticmethod
    def extract_device(label_or_device: str) -> str:
        return str(label_or_device).split(" | ", 1)[0].strip()

    @staticmethod
    def guess_port() -> str:
        labels = NucRgbSerial.list_serial_ports()
        if not labels:
            return NucRgbSerial.default_port()
        priority_terms = ("prolific", "pl2303", "067b", "ttyacm", "usb serial")
        for label in labels:
            if any(term in label.lower() for term in priority_terms):
                return NucRgbSerial.extract_device(label)
        return NucRgbSerial.extract_device(labels[0])

    def _open(self):
        ser = serial.Serial(self.port, timeout=self.timeout)
        time.sleep(TIME_START)
        return ser

    def run_commands(self, commands: str) -> None:
        commands = commands.strip()
        if not commands:
            return
        with self._open() as ser:
            for cmd in commands.split(","):
                clean = cmd.strip().upper()
                if not clean:
                    continue
                ser.write(clean.encode("ascii") + b"\n")
                time.sleep(TIME_CMD)

    def query_line(self, command: str) -> str:
        with self._open() as ser:
            ser.write(command.strip().upper().encode("ascii") + b"\n")
            time.sleep(TIME_CMD)
            return ser.read_until().decode(errors="replace").strip()

    def run_raw_with_status(self, commands: str) -> str:
        before = self.get_status_raw()
        self.run_commands(commands)
        after = self.get_status_raw()
        return "Before STA?: " + before + "\nAfter  STA?: " + after

    def get_controller_id(self) -> str:
        return self.query_line("ID?")

    def get_status_raw(self) -> str:
        return self.query_line("STA?")

    @staticmethod
    def parse_status_raw(raw: str) -> Dict[str, object]:
        values = [int(x) for x in raw.split(",") if x.strip() != ""]
        if len(values) != 24:
            raise RuntimeError(LocalizedMessage("log_status_length", length=len(values), raw=raw))
        ap, bp, cp, dp, c1, c2, c3, c4, c5, c6, c7, av, bv, cv, dv, ad, bd, cd, dd, ar, br, cr, dr, btn = values
        zmap = {
            "Skull":        (ap, c1, av, ad, ar),
            "Bottom Left":  (bp, c2, bv, bd, br),
            "Bottom Right": (cp, c3, cv, cd, cr),
            "Bottom Front": (dp, c4, dv, dd, dr),
        }
        zones = {}
        for name, (pattern, hue, brightness, frequency, rainbow) in zmap.items():
            zones[name] = {
                "pattern":    pattern_from_status(pattern, rainbow),
                "pattern_id": pattern,
                "hue":        hue,
                "color":      nearest_color_name(hue),
                "brightness": brightness,
                "frequency":  frequency,
                "rainbow":    bool(rainbow),
            }
        return {
            "enabled":          bool(btn),
            "zones":            zones,
            "pulse_train_hues": [c5, c6, c7],
            "status_layout":    "AP,BP,CP,DP,C1,C2,C3,C4,C5,C6,C7,AV,BV,CV,DV,AD,BD,CD,DD,AR,BR,CR,DR,BTN",
            "raw":              raw,
        }

    def get_status(self) -> Dict[str, object]:
        return NucRgbSerial.parse_status_raw(self.get_status_raw())


# ── UI widgets ────────────────────────────────────────────────────────────────

class Tooltip:
    """Delayed, non-interactive help that follows the current language and theme."""

    def __init__(self, widget: tk.Misc, get_text: Callable[[], str]):
        self.widget = widget
        self._get_text = get_text
        self._timer = None
        self._window = None
        self._label = None
        # A separate bindtag survives the existing buttons' hover/state refreshes.
        self._tag = f"CanyonGlowTooltip{id(self)}"
        self._events = {
            "<Enter>": self._schedule,
            "<Leave>": self.hide,
            "<ButtonPress>": self.hide,
            "<KeyPress>": self.hide,
            "<Unmap>": self.hide,
            "<Destroy>": self._on_destroy,
        }
        widget.bindtags((self._tag, *widget.bindtags()))
        for event, handler in self._events.items():
            widget.bind_class(self._tag, event, handler)

    @property
    def text(self) -> str:
        return self._get_text()

    def _schedule(self, _event=None) -> None:
        self.hide()
        self._timer = self.widget.after(500, self._show)

    def _create_window(self) -> None:
        self._window = tk.Toplevel(self.widget.winfo_toplevel())
        self._window.withdraw()
        self._window.overrideredirect(True)
        self._window.transient(self.widget.winfo_toplevel())
        self._label = tk.Label(
            self._window, justify="left", wraplength=320,
            relief="solid", borderwidth=1, padx=10, pady=6,
            font=("Segoe UI", 9),
        )
        self._label.pack()
        self.refresh()

    def _show(self) -> None:
        self._timer = None
        if not self.widget.winfo_exists() or not self.widget.winfo_viewable():
            return
        self._create_window()
        self._window.deiconify()
        self._window.lift()

    def refresh(self) -> None:
        if self._window is None:
            return
        self._label.configure(text=self.text, bg=PAL["SURFACE"], fg=PAL["TEXT"])
        self._window.update_idletasks()
        width, height = self._window.winfo_reqwidth(), self._window.winfo_reqheight()
        root = self.widget.winfo_toplevel()
        left, top = root.winfo_rootx(), root.winfo_rooty()
        right, bottom = left + root.winfo_width(), top + root.winfo_height()
        x = max(left, min(self.widget.winfo_rootx(), right - width))
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        if y + height > bottom:
            y = self.widget.winfo_rooty() - height - 6
        y = max(top, y)
        self._window.geometry(f"{width}x{height}+{x}+{y}")

    def hide(self, _event=None) -> None:
        if self._timer is not None:
            try:
                self.widget.after_cancel(self._timer)
            except tk.TclError:
                pass
            self._timer = None
        if self._window is not None:
            try:
                self._window.destroy()
            except tk.TclError:
                pass
            self._window = self._label = None

    def _on_destroy(self, event) -> None:
        if event.widget is self.widget:
            self.hide()
            for sequence in self._events:
                self.widget.unbind_class(self._tag, sequence)


class PatternSelect(ttk.Frame):
    """Compact dropdown for effect selection."""

    def __init__(self, master, variable: tk.StringVar, command: Optional[Callable[[], None]] = None, width: int = 108):
        super().__init__(master, style="Row.TFrame")
        self.variable = variable
        self.command  = command
        self._enabled = True
        self.button = tk.Menubutton(
            self, text=normalize_pattern(variable.get()), width=10, relief="flat", bd=0,
            bg=PAL["BTN"], fg=PAL["TEXT"], activebackground=PAL["BTN_HOVER"], activeforeground=PAL["WHITE"],
            cursor="hand2", padx=8, pady=6, anchor="w", direction="below",
            takefocus=0, highlightthickness=0,
        )
        self.menu = tk.Menu(
            self.button, tearoff=False,
            bg=PAL["LOG_BG"], fg=PAL["TEXT"], activebackground=PAL["BLUE"], activeforeground=PAL["BLUE_ON"],
        )
        self.button.configure(menu=self.menu)
        for name in EFFECT_OPTIONS:
            self.menu.add_command(label=name, command=lambda n=name: self._select(n))
        self.button.grid(row=0, column=0, sticky="ew")
        self.columnconfigure(0, weight=1)
        self.variable.trace_add("write", lambda *_: self.refresh())
        self.refresh()

    def _select(self, name: str) -> None:
        if not self._enabled:
            return
        self.variable.set(name)
        self.refresh()
        if self.command:
            self.command()

    def refresh(self) -> None:
        self.button.configure(text=f"{normalize_pattern(self.variable.get())} ▾")

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        if enabled:
            self.button.configure(
                state=tk.NORMAL, menu=self.menu,
                bg=PAL["BTN"], fg=PAL["TEXT"],
                activebackground=PAL["BTN_HOVER"], activeforeground=PAL["WHITE"],
                cursor="hand2",
            )
        else:
            self.button.configure(
                state=tk.DISABLED, menu="",
                bg=PAL["SWITCH_DIS"], disabledforeground=PAL["DIM"],
                cursor="arrow",
            )

    def apply_theme(self) -> None:
        self.menu.configure(bg=PAL["LOG_BG"], fg=PAL["TEXT"],
                            activebackground=PAL["BLUE"], activeforeground=PAL["BLUE_ON"])
        self.set_enabled(self._enabled)


class ToggleSwitch(tk.Button):
    """Small text-based EIN/AUS toggle with colored states."""

    def __init__(
        self, master, variable: tk.BooleanVar,
        command: Optional[Callable[[], None]] = None,
        on_text: str = "EIN", off_text: str = "AUS",
        width: int = 5, padx: int = 8, pady: int = 5,
        power_colors: bool = False,
    ):
        self.variable     = variable
        self.user_command = command
        self.on_text      = on_text
        self.off_text     = off_text
        self.enabled      = True
        self.power_colors = power_colors
        super().__init__(
            master, relief="flat", bd=0, padx=padx, pady=pady, width=width,
            cursor="hand2", command=self._toggle,
            font=("Segoe UI", 9, "bold"), takefocus=0, highlightthickness=0,
        )
        self.variable.trace_add("write", lambda *_: self.refresh())
        self.refresh()

    def _toggle(self) -> None:
        if not self.enabled:
            return
        self.variable.set(not bool(self.variable.get()))
        self.refresh()
        if self.user_command:
            self.user_command()

    def refresh(self) -> None:
        state = bool(self.variable.get())
        text  = self.on_text if state else self.off_text
        if not self.enabled:
            bg, fg = PAL["SWITCH_DIS"], PAL["DIM"]
            hov    = PAL["SWITCH_DIS"]
            act_fg = PAL["DIM"]
            self.bind("<ButtonPress-1>",   lambda e: "break")
            self.bind("<ButtonRelease-1>", lambda e: "break")
        elif state:
            self.unbind("<ButtonPress-1>")
            self.unbind("<ButtonRelease-1>")
            if self.power_colors:
                bg, fg = PAL["SUCCESS_BG"], PAL["SUCCESS_FG"]
                hov, act_fg = PAL["SUCCESS_HOV"], PAL["SUCCESS_FG"]
            else:
                bg, fg = PAL["TEAL"], PAL["TEAL_ON"]
                hov, act_fg = PAL["TEAL_HOVER"], PAL["TEAL_ON"]
        else:
            self.unbind("<ButtonPress-1>")
            self.unbind("<ButtonRelease-1>")
            if self.power_colors:
                bg, fg = PAL["DANGER_BG"], PAL["DANGER_FG"]
                hov, act_fg = PAL["DANGER_HOV"], PAL["DANGER_FG"]
            else:
                bg, fg = PAL["BTN"], PAL["SUBTLE"]
                hov, act_fg = PAL["BTN_HOVER"], PAL["WHITE"]
        self.configure(text=text, bg=bg, fg=fg,
                       activebackground=hov, activeforeground=act_fg,
                       cursor="arrow" if not self.enabled else "hand2")
        en = self.enabled
        self.bind("<Enter>", lambda e, h=hov: self.configure(bg=h) if en else None)
        self.bind("<Leave>", lambda e, b=bg:  self.configure(bg=b))

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        self.configure(state=tk.NORMAL)
        self.refresh()


class HueBar(ttk.Frame):
    """Clickable hue strip 0-255.

    Gradient is rendered as 256 canvas rectangle strips — O(256) canvas ops
    instead of O(width * height) Python pixel operations.
    """

    _GRADIENT_TAG = "gradient"

    def __init__(
        self, master, variable: tk.IntVar,
        command: Optional[Callable[[], None]] = None,
        width: int = 365, height: int = 18,
        show_standard_markers: bool = True,
    ):
        super().__init__(master, style="Card.TFrame")
        self.variable        = variable
        self.command         = command
        self.requested_width = int(width)
        self.current_width   = max(16, int(width))
        self.height          = int(height)
        self._overhang       = 4   # marker extends this many px above/below the bar
        self.enabled         = True
        self._internal       = False
        self._gradient_items: List[int] = []
        self._marker_items:   List[int] = []
        self.show_standard_markers = show_standard_markers

        self.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            self, width=self.requested_width, height=self.height + 2 * self._overhang,
            highlightthickness=0, bd=0, bg=C_LOG_BG, cursor="hand2",
        )
        self.canvas.grid(row=0, column=0, sticky="ew")

        oh = self._overhang
        self.disabled_overlay = self.canvas.create_rectangle(
            0, oh, self.current_width - 1, oh + self.height - 1,
            fill=C_SURFACE, stipple="gray50", outline="",
        )
        self.canvas.itemconfigure(self.disabled_overlay, state="hidden")

        self._border_item = self.canvas.create_rectangle(
            0, oh, self.current_width - 1, oh + self.height - 1,
            outline=C_BORDER, width=1,
        )

        self._draw_standard_markers()

        total_h = self.height + 2 * oh
        self.shadow = self.canvas.create_line(0, 0, 0, total_h, fill=C_WHITE, width=5)
        self.marker = self.canvas.create_line(0, 0, 0, total_h, fill=C_LOG_BG, width=2)

        self._redraw_gradient(self.current_width)
        self.canvas.bind("<Configure>", self._on_configure)
        self.canvas.bind("<Button-1>",  self._on_pointer)
        self.canvas.bind("<B1-Motion>", self._on_pointer)
        self.variable.trace_add("write", self._on_var_change)
        self._sync()

    def _hue_to_x(self, hue: int) -> int:
        hue = clamp_int(hue, 0, 255)
        x   = round((hue / 255.0) * max(1, self.current_width - 1))
        return max(1, min(self.current_width - 2, x))

    def _draw_standard_markers(self) -> None:
        for item in self._marker_items:
            self.canvas.delete(item)
        self._marker_items.clear()
        if not self.show_standard_markers:
            return
        oh = self._overhang
        for _name, hue in STANDARD_HUE_MARKERS:
            x = self._hue_to_x(hue)
            self._marker_items.append(
                self.canvas.create_line(x, oh + 1, x, oh + 6, fill=C_LOG_BG, width=2)
            )
            self._marker_items.append(
                self.canvas.create_line(x, oh + self.height - 7, x, oh + self.height - 2, fill=C_WHITE, width=2)
            )

    def _redraw_gradient(self, width: int) -> None:
        width = max(16, int(width))
        self.current_width = width
        self.canvas.delete(self._GRADIENT_TAG)
        self._gradient_items.clear()
        oh = self._overhang
        for i in range(256):
            x1 = round(i * (width - 1) / 255)
            x2 = round((i + 1) * (width - 1) / 255)
            if x2 <= x1:
                x2 = x1 + 1
            self._gradient_items.append(
                self.canvas.create_rectangle(
                    x1, oh, x2, oh + self.height,
                    fill=hue_to_hex(i), outline="", tags=self._GRADIENT_TAG,
                )
            )
        self.canvas.tag_lower(self._GRADIENT_TAG)
        self.canvas.coords(self.disabled_overlay, 0, oh, width - 1, oh + self.height - 1)
        self.canvas.coords(self._border_item,     0, oh, width - 1, oh + self.height - 1)
        self._draw_standard_markers()
        self._sync()
        if not self.enabled:
            self.set_enabled(False)

    def _on_configure(self, event) -> None:
        width = max(16, int(event.width))
        if abs(width - self.current_width) >= 2:
            self._redraw_gradient(width)

    def _event_to_hue(self, event) -> int:
        x   = max(0, min(self.current_width - 1, int(event.x)))
        raw = clamp_int(round((x / max(1, self.current_width - 1)) * 255), 0, 255)
        if event.state & 0x0001:  # Shift held → fine control, no snap
            return raw
        return snap_standard_hue(raw)

    def _on_pointer(self, event) -> None:
        if not self.enabled:
            return
        hue = self._event_to_hue(event)
        self._internal = True
        try:
            self.variable.set(hue)
        finally:
            self._internal = False
        self._sync()
        if self.command:
            self.command()

    def _on_var_change(self, *_args) -> None:
        if not self._internal:
            self._sync()

    def _sync(self) -> None:
        hue     = clamp_int(self.variable.get(), 0, 255)
        x       = max(2, min(self.current_width - 3, self._hue_to_x(hue)))
        total_h = self.height + 2 * self._overhang
        self.canvas.coords(self.shadow, x, 0, x, total_h)
        self.canvas.coords(self.marker, x, 0, x, total_h)
        self.canvas.tag_raise(self.shadow)
        self.canvas.tag_raise(self.marker)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        self.canvas.configure(cursor=("hand2" if enabled else "arrow"))
        if enabled:
            for i, item in enumerate(self._gradient_items):
                self.canvas.itemconfigure(item, fill=hue_to_hex(i))
        else:
            for i, item in enumerate(self._gradient_items):
                r, g, b = colorsys.hsv_to_rgb(i / 256.0, 1.0, 1.0)
                y = int((0.299 * r + 0.587 * g + 0.114 * b) * 255)
                self.canvas.itemconfigure(item, fill=f"#{y:02x}{y:02x}{y:02x}")
        self.canvas.itemconfigure(self.shadow, fill=(DARK_PAL["WHITE"] if enabled else PAL["DIM"]))
        self.canvas.itemconfigure(self.marker, fill=(DARK_PAL["LOG_BG"] if enabled else PAL["BTN_HOVER"]))

    def apply_theme(self) -> None:
        self.canvas.configure(bg=PAL["LOG_BG"])
        self.canvas.itemconfigure(self.disabled_overlay, fill=PAL["SURFACE"])
        self.canvas.itemconfigure(self._border_item, outline=PAL["BORDER"])
        self._redraw_gradient(self.current_width)
        self.set_enabled(self.enabled)


class StepSelector(ttk.Frame):
    """0-5 segmented button control for brightness/tempo."""

    def __init__(self, master, variable: tk.IntVar, command: Optional[Callable[[], None]] = None):
        super().__init__(master, style="Card.TFrame")
        self.variable = variable
        self.command  = command
        self.enabled  = True
        self.buttons: List[tk.Button] = []
        for value in range(6):
            btn = tk.Button(
                self, text=str(value), relief="flat", bd=0,
                padx=8, pady=7, width=3, cursor="hand2",
                command=lambda v=value: self._select(v),
            )
            btn.grid(row=0, column=value, padx=(0 if value == 0 else 4, 0), sticky="ew")
            self.columnconfigure(value, weight=1)
            self.buttons.append(btn)
        self.variable.trace_add("write", lambda *_: self.refresh())
        self.refresh()

    def _select(self, value: int) -> None:
        if not self.enabled:
            return
        if self.variable.get() != value:
            self.variable.set(value)
        self.refresh()
        if self.command:
            self.command()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        for btn in self.buttons:
            btn.configure(
                state=(tk.NORMAL if enabled else tk.DISABLED),
                cursor=("hand2" if enabled else "arrow"),
            )
        self.refresh()

    def refresh(self) -> None:
        current = clamp_int(self.variable.get(), 0, 5)
        for value, btn in enumerate(self.buttons):
            if not self.enabled:
                btn.configure(bg=PAL["SWITCH_DIS"], fg=PAL["DIM"], activebackground=PAL["SWITCH_DIS"])
            elif value == current:
                btn.configure(bg=PAL["BLUE"], fg=PAL["BLUE_ON"],
                              activebackground=PAL["BLUE_HOVER"], activeforeground=PAL["BLUE_ON"])
            else:
                btn.configure(bg=PAL["BTN"], fg=PAL["SUBTLE"],
                              activebackground=PAL["BTN_HOVER"], activeforeground=PAL["WHITE"])


# ── Zone row widget ───────────────────────────────────────────────────────────

class ZoneRow(tk.Frame):
    """Self-contained row widget for one LED zone.

    Owns its own tk variables and all child widgets. CanyonGlow interacts
    with it via get_config / set_config / update_ui / set_selected.
    """

    def __init__(
        self,
        master,
        zone_name:          str,
        on_select:          Callable[[str], None],
        on_control_changed: Callable[[str], None],
        on_pattern_changed: Callable[[str], None],
        on_hue_changed:     Callable[[str], None],
        on_sync_toggled:    Callable[[str], None],
        on_apply:           Callable[[str], None],
        get_synced_names:   Callable[[], List[str]],
        get_pt_hues:        Callable[[], List[int]] = lambda: [0, 96, 160],
        t:                  Callable[[str], str] = lambda k: STRINGS["de"][k],
    ):
        super().__init__(
            master,
            bg=PAL["ROW"], padx=10, pady=9,
            highlightbackground=PAL["BORDER_ROW"], highlightcolor=PAL["BORDER_ROW"],
            highlightthickness=2, cursor="hand2",
        )
        self.zone_name           = zone_name
        self._send_allowed       = True
        self._global_active      = True
        self._on_select          = on_select
        self._on_control_changed = on_control_changed
        self._on_pattern_changed = on_pattern_changed
        self._on_hue_changed     = on_hue_changed
        self._on_sync_toggled    = on_sync_toggled
        self._on_apply           = on_apply
        self._get_synced_names   = get_synced_names
        self._get_pt_hues        = get_pt_hues
        self._t                  = t

        self.enabled    = tk.BooleanVar(value=True)
        self.pattern    = tk.StringVar(value="Solid")
        self.custom_hue = tk.IntVar(value=96)
        self.brightness = tk.IntVar(value=5)
        self.frequency  = tk.IntVar(value=0)
        self.rainbow    = tk.BooleanVar(value=False)
        self.sync_hue   = tk.BooleanVar(value=False)

        self.columnconfigure(0, weight=0, minsize=108)
        self.columnconfigure(1, weight=0, minsize=92)
        self.columnconfigure(2, weight=1, minsize=440)
        self.columnconfigure(3, weight=0, minsize=88)
        self.bind("<Button-1>", lambda _e: self._on_select(self.zone_name))

        self._build()
        self.brightness.trace_add("write", lambda *_: self.after(0, self.update_ui))
        self.update_ui()

    def _build(self) -> None:
        z = self.zone_name

        # ── Identity block: name, preview, EIN/AUS ──
        identity = ttk.Frame(self, style="Row.TFrame")
        identity.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        identity.bind("<Button-1>", lambda _e: self._on_select(z))
        identity.columnconfigure(0, weight=0)
        identity.columnconfigure(1, weight=0)

        self._name_lbl = ttk.Label(identity, text=z, style="CardTitle.TLabel", width=12)
        self._name_lbl.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self._name_lbl.bind("<Button-1>", lambda _e: self._on_select(z))

        self._preview = tk.Canvas(identity, width=34, height=34,
                                  bg="#000000", highlightthickness=0, cursor="hand2")
        self._preview.grid(row=1, column=0, sticky="w", padx=(0, 10))
        self._preview.bind("<Button-1>", lambda _e: self._on_select(z))

        self._active_switch = ToggleSwitch(
            identity, self.enabled,
            command=lambda: self._on_control_changed(z),
            on_text=self._t("ein"), off_text=self._t("aus"), width=3, padx=6, pady=4,
            power_colors=True,
        )
        self._active_switch.grid(row=1, column=1, sticky="w", pady=(2, 0))

        # ── Effect selector ──
        self._pattern_widget = PatternSelect(
            self, self.pattern, command=lambda: self._on_pattern_changed(z),
        )
        self._pattern_widget.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=(10, 0))
        self._pattern_widget.button.configure(width=10, padx=10, pady=8)
        self._pattern_widget.button.bind("<Button-1>", lambda _e: self._on_select(z), add="+")

        # ── Hue area ──
        hue_area = ttk.Frame(self, style="Row.TFrame")
        hue_area.grid(row=0, column=2, sticky="nsew", padx=(0, 10))
        hue_area.columnconfigure(0, weight=1)

        self._hue_bar = HueBar(
            hue_area, self.custom_hue,
            command=lambda: self._on_hue_changed(z), width=390, height=19,
        )
        self._hue_bar.grid(row=0, column=0, sticky="w", pady=(8, 0))

        self._hue_spin = ttk.Spinbox(
            hue_area, from_=0, to=255, textvariable=self.custom_hue,
            width=3, command=lambda: self._on_hue_changed(z),
        )
        self._hue_spin.grid(row=0, column=1, sticky="w", padx=(6, 0), pady=(8, 0))
        self._hue_spin.bind("<KeyRelease>",      lambda _e: self._on_hue_changed(z))
        self._hue_spin.bind("<ButtonRelease-1>",  lambda _e: self._on_hue_changed(z))

        self._sync_switch = ToggleSwitch(
            hue_area, self.sync_hue,
            command=lambda: self._on_sync_toggled(z),
            on_text=self._t("link"), off_text=self._t("link"), width=5, padx=8, pady=7,
        )
        self._sync_switch.grid(row=0, column=2, sticky="w", padx=(5, 0), pady=(8, 0))

        self._note = ttk.Label(hue_area, text="Farbe", style="MiniLabel.TLabel", width=32)
        self._note.grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self._note.bind("<Button-1>", lambda _e: self._on_select(z))

        # ── Apply button ──
        actions = ttk.Frame(self, style="Row.TFrame")
        actions.grid(row=0, column=3, sticky="nsew")
        actions.columnconfigure(0, weight=1)
        self._apply_btn = ttk.Button(
            actions, text=self._t("apply_zone"), style="ZoneApply.TButton",
            command=lambda: self._on_apply(z), width=10, takefocus=0,
        )
        self._apply_btn.grid(row=0, column=0, sticky="ew", pady=(8, 0))

    # ── Public interface ──────────────────────────────────────────────────────

    def get_config(self) -> ZoneConfig:
        pattern = normalize_pattern(str(self.pattern.get()))
        enabled = bool(self.enabled.get())
        if pattern == "Off":
            enabled = False
            pattern = "Solid"
        return ZoneConfig(
            enabled=enabled,
            pattern=pattern,
            brightness=clamp_int(self.brightness.get(), 0, 5),
            frequency=clamp_int(self.frequency.get(), 0, 5),
            rainbow=False,
            custom_hue=clamp_int(self.custom_hue.get(), 0, 255),
        )

    def set_config(self, cfg: ZoneConfig) -> None:
        pattern = normalize_pattern(cfg.pattern)
        enabled = bool(cfg.enabled)
        if pattern == "Off":
            enabled = False
            pattern = "Solid"
        self.enabled.set(enabled)
        self.pattern.set(pattern)
        self.brightness.set(clamp_int(cfg.brightness, 0, 5))
        self.frequency.set(clamp_int(cfg.frequency, 0, 5))
        self.rainbow.set(False)
        self.custom_hue.set(clamp_int(cfg.custom_hue, 0, 255))
        self.update_ui()

    def set_selected(self, selected: bool) -> None:
        color = PAL["TEAL"] if selected else PAL["BORDER_ROW"]
        self.configure(highlightbackground=color, highlightcolor=color)

    def update_ui(self) -> None:
        hue        = clamp_int(self.custom_hue.get(), 0, 255)
        brightness = clamp_int(self.brightness.get(), 0, 5)
        enabled    = bool(self.enabled.get())
        pattern    = normalize_pattern(self.pattern.get())

        if pattern == "Off":
            pattern = "Solid"
            self.pattern.set(pattern)
            self.enabled.set(False)
            enabled = False
        else:
            self.pattern.set(pattern)

        # Colour preview square
        if not self._global_active:
            val = 0.05
        elif enabled:
            val = max(0.16, brightness / 5.0)
        else:
            val = 0.10
        self._draw_preview(hue, pattern, val)

        # Hue spinbox style: standard/default
        _std_name, _std_value, _std_dist = nearest_standard_hue(hue)
        hue_active = enabled and pattern not in PULSETRAIN_PATTERNS and pattern != "Rainbow"
        if hue_active and _std_dist == 0:
            self._hue_spin.configure(style="StandardHue.TSpinbox")
        else:
            self._hue_spin.configure(style="TSpinbox")

        self._name_lbl.configure(style="CardTitle.TLabel" if enabled else "Disabled.TLabel")
        self._note.configure(
            text=self._color_note(pattern, hue, enabled),
            style="MiniLabel.TLabel" if enabled else "Disabled.TLabel",
        )
        self._set_controls_enabled(enabled and self._global_active)


    def _draw_preview(self, hue: int, pattern: str, value: float) -> None:
        cv = self._preview
        cv.delete("all")
        W, H = 34, 34
        if pattern in PULSETRAIN_PATTERNS:
            hues = self._get_pt_hues()
        elif pattern == "Rainbow":
            hues = [0, 43, 85, 128, 171, 213]
        else:
            hues = None
        if hues:
            self._fill_gradient(cv, W, H, hues, value)
        else:
            cv.create_rectangle(0, 0, W, H, fill=hue_to_hex(hue, value), outline="")

    @staticmethod
    def _fill_gradient(cv: tk.Canvas, w: int, h: int, hues: List[int], value: float) -> None:
        n = len(hues)
        for x in range(w):
            t   = x / max(1, w - 1)
            seg = t * (n - 1)
            idx = min(int(seg), n - 2)
            frac = seg - idx
            h1, h2 = hues[idx], hues[idx + 1]
            diff   = ((h2 - h1 + 128) % 256) - 128
            interp = int(h1 + frac * diff) % 256
            cv.create_line(x, 0, x, h, fill=hue_to_hex(interp, value))

    # ── Private helpers ───────────────────────────────────────────────────────

    def _color_note(self, pattern: str, hue: int, enabled: bool) -> str:
        if pattern in PULSETRAIN_PATTERNS:
            return self._t("note_pt")
        if pattern == "Rainbow":
            return self._t("note_rainbow")
        if not enabled:
            return self._t("note_off")
        std_note = standard_hue_note(hue)
        if std_note:
            return std_note
        if self.sync_hue.get():
            synced = self._get_synced_names()
            if len(synced) > 1:
                short = {"Bottom Left": "Left", "Bottom Right": "Right", "Bottom Front": "Front"}
                return self._t("note_link") + ", ".join(short.get(n, n) for n in synced)
            return self._t("note_link_ready")
        ci = ZONES[self.zone_name]["color_index"]
        return f"{self._t('note_color_c')}{ci}"

    def _set_controls_enabled(self, enabled: bool) -> None:
        pattern    = normalize_pattern(self.pattern.get())
        hue_active = bool(enabled) and pattern not in PULSETRAIN_PATTERNS and pattern != "Rainbow"
        self._pattern_widget.set_enabled(bool(enabled))
        self._hue_bar.set_enabled(hue_active)
        self._hue_spin.state(["!disabled"] if hue_active else ["disabled"])
        self._sync_switch.set_enabled(hue_active)
        self._apply_btn.state(["!disabled"] if self._send_allowed else ["disabled"])

    def apply_theme(self) -> None:
        self.configure(bg=PAL["ROW"],
                       highlightbackground=PAL["BORDER_ROW"],
                       highlightcolor=PAL["BORDER_ROW"])
        self._pattern_widget.apply_theme()
        self._active_switch.refresh()
        self._sync_switch.refresh()
        self._hue_bar.apply_theme()

    def set_send_enabled(self, enabled: bool) -> None:
        self._send_allowed = enabled
        self._apply_btn.state(["!disabled"] if enabled else ["disabled"])

    def set_global_active(self, enabled: bool) -> None:
        self._global_active = enabled
        cur = "hand2" if enabled else "arrow"
        self.configure(cursor=cur)
        self._preview.configure(cursor=cur)
        self._active_switch.set_enabled(enabled)
        self._set_controls_enabled(bool(self.enabled.get()) if enabled else False)
        hue = clamp_int(self.custom_hue.get(), 0, 255)
        pattern = normalize_pattern(self.pattern.get())
        if enabled:
            brightness = clamp_int(self.brightness.get(), 0, 5)
            val = max(0.16, brightness / 5.0) if bool(self.enabled.get()) else 0.10
        else:
            val = 0.05
        self._draw_preview(hue, pattern, val)

    def apply_lang(self, t: Callable[[str], str]) -> None:
        self._t = t
        self._active_switch.on_text  = t("ein")
        self._active_switch.off_text = t("aus")
        self._active_switch.refresh()
        self._sync_switch.on_text  = t("link")
        self._sync_switch.off_text = t("link")
        self._sync_switch.refresh()
        self._apply_btn.configure(text=t("apply_zone"))
        self.update_ui()


# ── Worker thread mixin ───────────────────────────────────────────────────────

class WorkerMixin:
    def __init__(self):
        self._queue:        "queue.Queue[tuple[str, str | LocalizedMessage]]" = queue.Queue()
        self._serial_lock:  threading.RLock               = threading.RLock()
        self._busy_count:   int                           = 0
        self._busy_lock:    threading.Lock                = threading.Lock()
        self._cancel_event: threading.Event               = threading.Event()

    @contextmanager
    def _busy_ctx(self, label: str | LocalizedMessage):
        """Increment busy count and post 'busy' for the duration of the managed block."""
        with self._busy_lock:
            self._busy_count += 1
        self._queue.put(("busy", LocalizedMessage("log_running", label=label)))
        try:
            yield
        finally:
            with self._busy_lock:
                self._busy_count = max(0, self._busy_count - 1)

    def run_worker(self, label: str | LocalizedMessage, fn, *args, use_serial_lock: bool = True, **kwargs) -> None:
        def target():
            try:
                with self._busy_ctx(label):
                    if use_serial_lock:
                        with self._serial_lock:
                            result = fn(*args, **kwargs)
                    else:
                        result = fn(*args, **kwargs)
            except Exception as exc:
                self._queue.put(("error", LocalizedMessage("log_worker_result", label=label, result=exception_message(exc))))
            else:
                self._queue.put(("info", LocalizedMessage("log_worker_result", label=label, result="OK" if result is None else result)))
            finally:
                self._queue.put(("idle", LocalizedMessage("log_ready")))
        threading.Thread(target=target, daemon=True).start()

    def is_busy(self) -> bool:
        with self._busy_lock:
            return self._busy_count > 0


# ── Main application ──────────────────────────────────────────────────────────

class CanyonGlow(tk.Tk, WorkerMixin):
    def __init__(self, *, settings_path: Path | None = None):
        self._settings_path = Path(settings_path) if settings_path is not None else ui_settings_path()
        settings = read_ui_settings(self._settings_path)
        self._dark = settings["theme"] == "dark"
        PAL.update(DARK_PAL if self._dark else LIGHT_PAL)
        tk.Tk.__init__(self)
        WorkerMixin.__init__(self)

        self.title(f"{APP_NAME} {APP_VERSION}")
        icon_path = Path(__file__).resolve().parent / "picture" / "CanyonGlow.ico"
        if platform.system() == "Windows" and icon_path.is_file():
            try:
                self.iconbitmap(default=str(icon_path))
            except tk.TclError:
                pass
        self.geometry("1280x820")
        self.minsize(1120, 740)
        self.configure(bg=PAL["BG"])

        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self._setup_styles()

        self.lang_var             = tk.StringVar(value="Deutsch" if settings["language"] == "de" else "English")
        self._surface_frames:     List[tk.Frame] = []
        self._i18n:               list           = []   # (widget, str_key)
        self._tooltips:           List[Tooltip] = []

        self.port_var             = tk.StringVar(value=NucRgbSerial.guess_port())
        self.all_enabled_var      = tk.BooleanVar(value=True)
        self.dry_run_var          = tk.BooleanVar(value=False)
        self.status_var           = tk.StringVar(value=self._t("log_ready"))
        self._status_message      = LocalizedMessage("log_ready")
        self._log_entries: List[tuple[str, str | LocalizedMessage]] = []
        self.profile_name_var     = tk.StringVar(value="Default")
        self.global_brightness_var = tk.IntVar(value=5)

        self.selected_zone_var        = tk.StringVar(value="Skull")
        self.selected_brightness_var  = tk.IntVar(value=5)
        self.selected_frequency_var   = tk.IntVar(value=0)
        self._syncing_inspector       = False

        self.pt_hue_vars:      List[tk.IntVar]    = [tk.IntVar(value=0), tk.IntVar(value=96), tk.IntVar(value=160)]
        self.pt_labels:        List[ttk.Label]    = []
        self.pt_static_labels: List[ttk.Label]    = []
        self.pt_bars:          List[HueBar]       = []
        self.pt_spins:         List[ttk.Spinbox]  = []
        self.pt_buttons:       List[ttk.Button]   = []
        self.zone_rows:        Dict[str, ZoneRow] = {}
        self._send_btns:        List[ttk.Button]  = []
        self._active_btns:      List[ttk.Button]  = []
        self._global_toggle:    Optional[tk.Button] = None
        self._controller_found: bool              = False
        self._controller_port:  str               = ""
        self._controller_status_key: str          = ""

        self._build_ui()
        self._apply_theme()
        self.bind("<Unmap>", lambda event: self._hide_tooltips() if event.widget is self else None, add="+")
        self.bind("<KeyPress>", lambda _event: self._hide_tooltips(), add="+")
        self.all_enabled_var.trace_add("write", lambda *_: self._on_global_active_changed())
        self.refresh_ports(select_guess=False)
        self._validate_effect_commands()
        self._set_controller_mode(False)
        self.after(150, self._poll_queue)
        self.after(500, self.auto_read_status_on_startup)

    def _setup_styles(self) -> None:
        self.option_add("*Font", ("Segoe UI", 10))
        self.option_add("*TCombobox*Listbox.font", ("Segoe UI", 10))

        s = self.style
        s.configure(".",            background=PAL["BG"],      foreground=PAL["TEXT"], fieldbackground=PAL["SURFACE"])
        s.configure("Dark.TFrame",  background=PAL["BG"])
        s.configure("Surface.TFrame", background=PAL["SURFACE"])
        s.configure("Card.TFrame",  background=PAL["SURFACE"])
        s.configure("Row.TFrame",   background=PAL["SURFACE"])

        s.configure("TLabel",         background=PAL["BG"],      foreground=PAL["TEXT"])
        s.configure("Title.TLabel",   background=PAL["BG"],      foreground=PAL["TEXT"],  font=("Segoe UI", 18, "bold"))
        s.configure("Subtitle.TLabel", background=PAL["BG"],     foreground=PAL["MUTED"],  font=("Segoe UI", 10))
        s.configure("CardTitle.TLabel", background=PAL["SURFACE"], foreground=PAL["TEXT"], font=("Segoe UI", 12, "bold"))
        s.configure("Muted.TLabel",   background=PAL["SURFACE"], foreground=PAL["MUTED"])
        s.configure("MiniLabel.TLabel", background=PAL["SURFACE"], foreground=PAL["MINI_FG"], font=("Segoe UI", 9))
        s.configure("Disabled.TLabel", background=PAL["SURFACE"], foreground=PAL["DIM"],   font=("Segoe UI", 9))
        s.configure("Pill.TLabel",    background=PAL["PILL"],    foreground=PAL["TEXT"],  padding=(7, 2), font=("Segoe UI", 9, "bold"))
        s.configure("MutedPill.TLabel", background=PAL["SWITCH_DIS"], foreground=PAL["DIM"], padding=(7, 2), font=("Segoe UI", 9, "bold"))

        s.configure("TButton", background=PAL["BTN"], foreground=PAL["TEXT"], borderwidth=0, focusthickness=0, padding=(10, 7))
        s.map("TButton", background=[("active", PAL["BTN_HOVER"]), ("disabled", PAL["BTN_DIS"])],
                         foreground=[("disabled", PAL["BTN_DIS_FG"])])

        s.configure("Primary.TButton", background=PAL["BLUE"], foreground=PAL["BLUE_ON"],
                    borderwidth=0, padding=(12, 7), font=("Segoe UI", 10, "bold"))
        s.map("Primary.TButton", background=[("active", PAL["BLUE_HOVER"])])

        s.configure("ZoneApply.TButton", background=PAL["BLUE_DARK"], foreground=PAL["ZONE_APPLY_FG"],
                    borderwidth=0, padding=(10, 7), font=("Segoe UI", 10, "bold"))
        s.map("ZoneApply.TButton",
              background=[("active", PAL["BLUE_DARK_HOV"]), ("disabled", PAL["SWITCH_DIS"])],
              foreground=[("disabled", PAL["DIM"])])

        s.configure("Danger.TButton",  background=PAL["DANGER_BG"],  foreground=PAL["DANGER_FG"],  borderwidth=0, padding=(10, 7))
        s.map("Danger.TButton",  background=[("active", PAL["DANGER_HOV"])])
        s.configure("Success.TButton", background=PAL["SUCCESS_BG"], foreground=PAL["SUCCESS_FG"], borderwidth=0, padding=(10, 7))
        s.map("Success.TButton", background=[("active", PAL["SUCCESS_HOV"])])

        s.configure("TCheckbutton", background=PAL["SURFACE"], foreground=PAL["TEXT"])
        s.map("TCheckbutton", background=[("active", PAL["SURFACE"])])
        s.configure("TNotebook",     background=PAL["BG"], borderwidth=0)
        s.configure("TNotebook.Tab", background=PAL["SURFACE"], foreground=PAL["SUBTLE"], padding=(14, 8))
        s.map("TNotebook.Tab", background=[("selected", PAL["BTN"])], foreground=[("selected", PAL["TEXT"])])

        s.configure("TCombobox",  fieldbackground=PAL["SURFACE"], background=PAL["BTN"], foreground=PAL["TEXT"], arrowcolor=PAL["TEXT"])
        s.map("TCombobox",
              fieldbackground=[("readonly", PAL["SURFACE"]), ("disabled", PAL["SWITCH_DIS"])],
              foreground=[("readonly", PAL["TEXT"]), ("disabled", PAL["DIM"])],
              selectbackground=[("readonly", PAL["BTN"])],
              selectforeground=[("readonly", PAL["TEXT"])],
        )
        s.configure("TSpinbox",   fieldbackground=PAL["SURFACE"], background=PAL["BTN"], foreground=PAL["TEXT"], arrowcolor=PAL["TEXT"])
        s.configure("StandardHue.TSpinbox", fieldbackground=PAL["HUE_EXACT_BG"], background=PAL["HUE_EXACT_BTN"],
                    foreground=PAL["HUE_EXACT_FG"], arrowcolor=PAL["HUE_EXACT_FG"])
        s.configure("NearHue.TSpinbox",     fieldbackground=PAL["HUE_NEAR_BG"],  background=PAL["HUE_NEAR_BTN"],
                    foreground=PAL["HUE_NEAR_FG"],  arrowcolor=PAL["HUE_NEAR_FG"])
        s.configure("Horizontal.TScale", background=LIGHT_PAL["SURFACE"], troughcolor=PAL["BTN"])

    def _validate_effect_commands(self) -> None:
        expected = {
            "Off":       ("P0", "V:0", "R:0", "D:0"),
            "Solid":     ("P1", "R:0", "D:0"),
            "Pulse":     ("P2", "R:0"),
            "Breathing": ("P3", "R:0"),
            "Strobe":    ("P4", "R:0"),
            "PT1":       ("P5", "R:0"),
            "PT2":       ("P6", "R:0"),
            "PT3":       ("P7", "R:0"),
            "Rainbow":   ("P1", "R:1"),
        }
        failures = []
        for pattern, parts in expected.items():
            cmd = expected_command_for("Skull", pattern)
            for part in parts:
                if f"A{part}" not in cmd:
                    failures.append(LocalizedMessage("log_effect_part_missing", pattern=pattern, part=part, command=cmd))
        if pattern_from_status(1, 1) != "Rainbow":
            failures.append(LocalizedMessage("log_decoder_expected", flags="P1/R1", pattern="Rainbow"))
        if pattern_from_status(1, 0) != "Solid":
            failures.append(LocalizedMessage("log_decoder_expected", flags="P1/R0", pattern="Solid"))
        if "AP2,AV:5,AR:0,AD:2,C1:95" != expected_command_for("Skull", "Pulse", hue=95, brightness=5, frequency=2):
            failures.append(LocalizedMessage("log_effect_command_mismatch", pattern="Pulse"))
        if "AP4,AV:5,AR:0,AD:2,C1:95" != expected_command_for("Skull", "Strobe", hue=95, brightness=5, frequency=2):
            failures.append(LocalizedMessage("log_effect_command_mismatch", pattern="Strobe"))
        if "AP1,AV:5,AR:1,AD:2" != expected_command_for("Skull", "Rainbow", hue=95, brightness=5, frequency=2):
            failures.append(LocalizedMessage("log_effect_command_mismatch", pattern="Rainbow"))
        if "Off" in EFFECT_OPTIONS:
            failures.append(LocalizedMessage("log_off_option_invalid"))
        if failures:
            self._log(LocalizedMessage("log_effect_check_failed", details=failures))
        else:
            self._log(LocalizedMessage("log_effect_check_ok"))

    # ── UI construction ───────────────────────────────────────────────────────

    def _attach_tooltip(self, widget: tk.Misc, key: str | Callable[[], str]) -> None:
        tooltip = Tooltip(widget, lambda: self._t(key() if callable(key) else key))
        widget._tooltip = tooltip
        self._tooltips.append(tooltip)

    def _hide_tooltips(self) -> None:
        for tooltip in self._tooltips:
            tooltip.hide()

    def _refresh_tooltips(self) -> None:
        for tooltip in self._tooltips:
            tooltip.refresh()

    def _build_ui(self) -> None:
        import tkinter.font as tkFont
        _fnt   = tkFont.Font(family="Segoe UI", size=10)
        _minpx = lambda *texts: max(_fnt.measure(t) for t in texts) + 20
        self._minpx = _minpx

        root = ttk.Frame(self, padding=14, style="Dark.TFrame")
        root.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        header = ttk.Frame(root, style="Dark.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(1, weight=1)

        lbl_title    = ttk.Label(header, text=self._t("title"),    style="Title.TLabel")
        lbl_subtitle = ttk.Label(header, text=self._t("subtitle"), style="Subtitle.TLabel")
        lbl_title.grid(row=0, column=0, sticky="w")
        lbl_subtitle.grid(row=1, column=0, sticky="w", pady=(2, 0))
        self._i18n += [(lbl_title, "title"), (lbl_subtitle, "subtitle")]

        conn = ttk.Frame(header, style="Dark.TFrame")
        conn.grid(row=0, column=1, rowspan=2, sticky="e")
        lbl_port = ttk.Label(conn, text=self._t("port_label"), style="Subtitle.TLabel")
        lbl_port.grid(row=0, column=0, padx=(0, 8))
        self._i18n.append((lbl_port, "port_label"))
        self.port_combo = ttk.Combobox(conn, textvariable=self.port_var, width=38)
        self.port_combo.grid(row=0, column=1, padx=(0, 8))
        btn_ref = ttk.Button(conn, text=self._t("refresh"), command=self.refresh_ports)
        btn_ref.grid(row=0, column=2, sticky="ew", padx=(0, 6))
        conn.columnconfigure(2, minsize=_minpx("Ports laden", "Scan Ports"))
        self._i18n.append((btn_ref, "refresh"))
        self._attach_tooltip(btn_ref, "tooltip_refresh")
        btn_tid = ttk.Button(conn, text=self._t("test_id"), command=self.test_id)
        btn_tid.grid(row=0, column=3, sticky="ew")
        conn.columnconfigure(3, minsize=_minpx("Gerät prüfen", "Check Device"))
        self._i18n.append((btn_tid, "test_id"))
        self._attach_tooltip(btn_tid, "tooltip_test_id")

        self.conn_status_lbl = tk.Label(
            conn, text="", fg=PAL["MUTED"], bg=PAL["BG"],
            font=("Segoe UI", 10, "bold"), anchor="e",
        )
        self.conn_status_lbl.grid(row=1, column=0, columnspan=4, sticky="e", pady=(6, 0))

        toolbar = ttk.Frame(root, style="Surface.TFrame", padding=10)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        toolbar.columnconfigure(11, weight=1)

        for col, (key, kw) in enumerate([
            ("read_status", {"command": self.read_status}),
            ("reset",       {"command": self.reset_default}),
        ]):
            b = ttk.Button(toolbar, text=self._t(key), **kw)
            b.grid(row=0, column=col, sticky="ew", padx=(0, 8))
            self._i18n.append((b, key))
            self._send_btns.append(b)
            self._attach_tooltip(b, f"tooltip_{key}")
        toolbar.columnconfigure(0, minsize=_minpx("Status abrufen", "Read Status"))
        toolbar.columnconfigure(1, minsize=_minpx("Werksreset",     "Factory Reset"))

        _pwr_fnt = tkFont.Font(family="Segoe UI", size=9, weight="bold")
        _pwr_min = max(_pwr_fnt.measure(t) for t in (
            "ALLE ZONEN AUS", "ALLE ZONEN AN", "ALL ZONES OFF", "ALL ZONES ON",
        )) + 32
        _toggle_frame = tk.Frame(toolbar, width=_pwr_min, bd=0, highlightthickness=0)
        _toggle_frame.grid(row=0, column=2, sticky="nsew", padx=(0, 18))
        _toggle_frame.pack_propagate(False)
        toolbar.columnconfigure(2, minsize=_pwr_min)

        self._global_toggle = tk.Button(
            _toggle_frame, relief="flat", bd=0, padx=12, pady=5,
            font=("Segoe UI", 9, "bold"), takefocus=0, highlightthickness=0,
            command=self._toggle_global_power,
        )
        self._global_toggle.pack(fill="both", expand=True)
        self._attach_tooltip(self._global_toggle, lambda: "tooltip_power_off" if self.all_enabled_var.get() else "tooltip_power_on")

        lbl_br = ttk.Label(toolbar, text=self._t("brightness_all"), style="Muted.TLabel")
        lbl_br.grid(row=0, column=4, sticky="e")
        self._i18n.append((lbl_br, "brightness_all"))
        self.global_brightness_label = ttk.Label(toolbar, text=str(self.global_brightness_var.get()),
                                                 style="Pill.TLabel", width=2, anchor="center")
        self.global_brightness_label.grid(row=0, column=6, sticky="w", padx=(0, 18))
        self._global_brightness_scale = ttk.Scale(toolbar, from_=0, to=5, orient="horizontal")
        self._global_brightness_scale.grid(row=0, column=5, sticky="ew", padx=(8, 4))
        self._global_brightness_scale.set(self.global_brightness_var.get())
        self._global_brightness_scale.configure(command=self.on_global_brightness)
        self._attach_tooltip(self._global_brightness_scale, "tooltip_brightness_all")

        lbl_prof = ttk.Label(toolbar, text=self._t("profile_label"), style="Muted.TLabel", width=7)
        lbl_prof.grid(row=0, column=7, sticky="e", padx=(0, 8))
        self._i18n.append((lbl_prof, "profile_label"))
        ttk.Entry(toolbar, textvariable=self.profile_name_var, width=18).grid(row=0, column=8, sticky="ew", padx=(0, 8))
        btn_save = ttk.Button(toolbar, text=self._t("save"), command=self.save_profile)
        btn_save.grid(row=0, column=9, sticky="ew", padx=(0, 6))
        self._i18n.append((btn_save, "save"))
        self._attach_tooltip(btn_save, "tooltip_save")
        toolbar.columnconfigure(9,  minsize=_minpx("Speichern", "Save"))
        btn_load = ttk.Button(toolbar, text=self._t("load"), command=self.load_profile)
        btn_load.grid(row=0, column=10, sticky="ew", padx=(0, 6))
        self._i18n.append((btn_load, "load"))
        self._attach_tooltip(btn_load, "tooltip_load")
        toolbar.columnconfigure(10, minsize=_minpx("Laden", "Load"))

        # Theme toggle + language selector
        self.theme_btn = ttk.Button(
            toolbar, text=self._t("theme_to_light" if self._dark else "theme_to_dark"),
            command=self._toggle_theme,
        )
        self.theme_btn.grid(row=0, column=12, sticky="ew", padx=(8, 4))
        self._attach_tooltip(self.theme_btn, lambda: "tooltip_theme_light" if self._dark else "tooltip_theme_dark")
        toolbar.columnconfigure(12, minsize=_minpx("☾ Dunkel", "☾ Dark", "☀ Hell", "☀ Light"))

        lang_combo = ttk.Combobox(toolbar, textvariable=self.lang_var,
                                  values=["English", "Deutsch"], state="readonly", width=9)
        lang_combo.grid(row=0, column=13, padx=(0, 0))
        lang_combo.bind("<<ComboboxSelected>>", lambda _: self._apply_lang())
        self._attach_tooltip(lang_combo, "tooltip_language")

        self.nb = ttk.Notebook(root)
        self.nb.grid(row=2, column=0, sticky="nsew")
        basic = ttk.Frame(self.nb, padding=10, style="Dark.TFrame")
        self.nb.add(basic, text=self._t("tab_basic"))
        self._build_basic(basic)

        log_tab = ttk.Frame(self.nb, padding=10, style="Dark.TFrame")
        self.nb.add(log_tab, text=self._t("tab_log"))
        self._build_log_tab(log_tab)

        status_bar = ttk.Frame(root, style="Dark.TFrame")
        status_bar.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        status_bar.columnconfigure(0, weight=1)
        ttk.Label(status_bar, textvariable=self.status_var, style="Subtitle.TLabel").grid(row=0, column=0, sticky="w")

    def _build_basic(self, page: ttk.Frame) -> None:
        page.columnconfigure(0, weight=1)
        page.columnconfigure(1, weight=0)
        page.rowconfigure(0, weight=1)

        left = tk.Frame(page, bg=PAL["SURFACE"], padx=12, pady=12,
                        highlightbackground=PAL["BORDER"], highlightcolor=PAL["BORDER"], highlightthickness=1)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=1)
        self._surface_frames.append(left)

        lbl_zones = ttk.Label(left, text=self._t("zones_title"), style="CardTitle.TLabel")
        lbl_zones.grid(row=0, column=0, sticky="w")
        self._i18n.append((lbl_zones, "zones_title"))
        lbl_hint = ttk.Label(left, text=self._t("zones_hint"), style="Muted.TLabel")
        lbl_hint.grid(row=1, column=0, sticky="w", pady=(2, 10))
        self._i18n.append((lbl_hint, "zones_hint"))

        rows_frame = ttk.Frame(left, style="Card.TFrame")
        rows_frame.grid(row=2, column=0, sticky="nsew")
        rows_frame.columnconfigure(0, weight=1)

        for i, zone_name in enumerate(ZONES):
            row = ZoneRow(
                rows_frame, zone_name,
                on_select=self.select_zone,
                on_control_changed=self.on_zone_control_changed,
                on_pattern_changed=self.on_zone_pattern_changed,
                on_hue_changed=self.on_zone_hue_changed,
                on_sync_toggled=self.on_sync_toggled,
                on_apply=self.apply_zone_from_row,
                get_synced_names=self.synced_zone_names,
                get_pt_hues=self.current_pulse_train_hues,
                t=self._t,
            )
            row.grid(row=i, column=0, sticky="ew", pady=(0 if i == 0 else 8, 0))
            self.zone_rows[zone_name] = row
            self._attach_tooltip(row._active_switch, "tooltip_zone_power")
            self._attach_tooltip(row._sync_switch, "tooltip_zone_sync")
            self._attach_tooltip(row._apply_btn, "tooltip_zone_send")
            self._attach_tooltip(row._pattern_widget.button, "tooltip_zone_effect")

        left_actions = ttk.Frame(left, style="Card.TFrame")
        left_actions.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        left_actions.columnconfigure(1, weight=1)
        btn_copy = ttk.Button(left_actions, text=self._t("copy_to_all"), command=self.copy_selected_zone_to_all)
        btn_copy.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        left_actions.columnconfigure(0, minsize=self._minpx("Auf alle Zonen kopieren", "Copy to All Zones"))
        self._i18n.append((btn_copy, "copy_to_all"))
        self._active_btns.append(btn_copy)
        self._attach_tooltip(btn_copy, "tooltip_copy_to_all")
        btn_apply_all = ttk.Button(left_actions, text=self._t("apply_all"), style="Primary.TButton",
                                   command=self.apply_profile)
        btn_apply_all.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        self._i18n.append((btn_apply_all, "apply_all"))
        self._send_btns.append(btn_apply_all)
        self._attach_tooltip(btn_apply_all, "tooltip_apply_all")

        right = ttk.Frame(page, style="Dark.TFrame")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)

        inspector = tk.Frame(right, bg=PAL["SURFACE"], padx=12, pady=12,
                             highlightbackground=PAL["BORDER"], highlightcolor=PAL["BORDER"], highlightthickness=1)
        inspector.grid(row=0, column=0, sticky="ew")
        self._surface_frames.append(inspector)
        self._build_inspector_panel(inspector)

        pt = tk.Frame(right, bg=PAL["SURFACE"], padx=12, pady=12,
                      highlightbackground=PAL["BORDER"], highlightcolor=PAL["BORDER"], highlightthickness=1)
        pt.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self._surface_frames.append(pt)
        self._build_pulse_train_panel(pt)

        self.select_zone("Skull")

    def _build_inspector_panel(self, panel: tk.Frame) -> None:
        panel.columnconfigure(0, weight=1)
        lbl_sel = ttk.Label(panel, text=self._t("selected_zone"), style="CardTitle.TLabel")
        lbl_sel.grid(row=0, column=0, sticky="w")
        self._i18n.append((lbl_sel, "selected_zone"))
        self.inspector_title = ttk.Label(panel, text="Skull", style="Muted.TLabel")
        self.inspector_title.grid(row=1, column=0, sticky="w", pady=(2, 10))
        lbl_br = ttk.Label(panel, text=self._t("brightness"), style="MiniLabel.TLabel")
        lbl_br.grid(row=2, column=0, sticky="w", pady=(6, 4))
        self._i18n.append((lbl_br, "brightness"))
        self.brightness_steps = StepSelector(panel, self.selected_brightness_var, command=self.on_inspector_changed)
        self.brightness_steps.grid(row=3, column=0, sticky="ew")
        lbl_tempo = ttk.Label(panel, text=self._t("tempo"), style="MiniLabel.TLabel")
        lbl_tempo.grid(row=4, column=0, sticky="w", pady=(14, 4))
        self._i18n.append((lbl_tempo, "tempo"))
        self.frequency_steps = StepSelector(panel, self.selected_frequency_var, command=self.on_inspector_changed)
        self.frequency_steps.grid(row=5, column=0, sticky="ew")
        self.frequency_hint = ttk.Label(panel, text=self._t("tempo_hint_default"), style="Muted.TLabel")
        self.frequency_hint.grid(row=6, column=0, sticky="w", pady=(6, 0))

    def _build_pulse_train_panel(self, panel: tk.Frame) -> None:
        panel.columnconfigure(0, weight=1)
        self.pt_title = ttk.Label(panel, text=self._t("pt_title"), style="CardTitle.TLabel")
        self.pt_title.grid(row=0, column=0, sticky="w")
        self._i18n.append((self.pt_title, "pt_title"))
        self.pt_hint = ttk.Label(panel, text=self._t("pt_hint"),
                                 style="Muted.TLabel", wraplength=280, justify="left")
        self.pt_hint.grid(row=1, column=0, sticky="w", pady=(2, 10))
        self._i18n.append((self.pt_hint, "pt_hint"))
        defaults = [0, 96, 160]
        for i, name in enumerate(self._t("pt_names")):
            block = ttk.Frame(panel, style="Card.TFrame")
            block.grid(row=i + 2, column=0, sticky="ew", pady=(0 if i == 0 else 6, 0))
            block.columnconfigure(1, weight=1)
            name_label = ttk.Label(block, text=name, style="MiniLabel.TLabel", width=10)
            name_label.grid(row=0, column=0, sticky="w", padx=(0, 8))
            self.pt_static_labels.append(name_label)
            bar = HueBar(block, self.pt_hue_vars[i], command=lambda idx=i: self.update_pt_ui(idx),
                         width=220, height=18)
            bar.grid(row=0, column=1, sticky="ew")
            self.pt_bars.append(bar)
            spin = ttk.Spinbox(block, from_=0, to=255, textvariable=self.pt_hue_vars[i], width=3,
                               command=lambda idx=i: self.update_pt_ui(idx))
            spin.grid(row=0, column=2, sticky="e", padx=(8, 0))
            spin.bind("<KeyRelease>", lambda _e, idx=i: self.update_pt_ui(idx))
            self.pt_spins.append(spin)
            label = ttk.Label(block, text=f"{defaults[i]}", style="Muted.TLabel", width=5)
            self.pt_labels.append(label)
        btns = ttk.Frame(panel, style="Card.TFrame")
        btns.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        btns.columnconfigure(0, weight=1)
        b1 = ttk.Button(btns, text=self._t("apply_palette"), style="Primary.TButton",
                        command=self.apply_pulse_train_colors)
        b1.grid(row=0, column=0, sticky="ew")
        self._i18n.append((b1, "apply_palette"))
        self.pt_buttons.append(b1)
        self._send_btns.append(b1)
        self._attach_tooltip(b1, "tooltip_apply_palette")

    def _build_log_tab(self, page: ttk.Frame) -> None:
        page.columnconfigure(0, weight=1)
        page.rowconfigure(0, weight=1)
        logcard = tk.Frame(page, bg=PAL["SURFACE"], padx=12, pady=10,
                           highlightbackground=PAL["BORDER"], highlightthickness=1)
        logcard.grid(row=0, column=0, sticky="nsew")
        logcard.columnconfigure(0, weight=1)
        logcard.rowconfigure(1, weight=1)
        self._surface_frames.append(logcard)
        self.log = tk.Text(logcard, wrap="word", undo=False,
                           bg=PAL["LOG_BG"], fg=PAL["LOG_FG"], insertbackground=PAL["WHITE"],
                           relief="flat", padx=8, pady=6)
        self.log.grid(row=1, column=0, sticky="nsew")
        sb = ttk.Scrollbar(logcard, orient="vertical", command=self.log.yview)
        sb.grid(row=1, column=1, sticky="ns")
        self.log.configure(yscrollcommand=sb.set)
        logbtns = ttk.Frame(logcard, style="Card.TFrame")
        logbtns.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        save_log_btn = ttk.Button(logbtns, text=self._t("save_log_btn"), command=self.save_log)
        save_log_btn.pack(side=tk.LEFT)
        self._i18n.append((save_log_btn, "save_log_btn"))
        self._attach_tooltip(save_log_btn, "tooltip_save_log")
        clear_btn = ttk.Button(logbtns, text=self._t("clear"),
                               command=self._clear_log)
        clear_btn.pack(side=tk.LEFT, padx=(8, 0))
        self._i18n.append((clear_btn, "clear"))
        self._attach_tooltip(clear_btn, "tooltip_clear")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _backend(self) -> NucRgbSerial:
        port = NucRgbSerial.extract_device(self.port_var.get())
        if not port:
            raise RuntimeError(LocalizedMessage("log_port_missing"))
        return NucRgbSerial(port)

    def _render_message(self, msg: str | LocalizedMessage) -> str:
        lang = "de" if self.lang_var.get() == "Deutsch" else "en"
        return msg.render(lang) if isinstance(msg, LocalizedMessage) else str(msg)

    def _set_status(self, msg: str | LocalizedMessage) -> None:
        self._status_message = msg
        self.status_var.set(self._render_message(msg).split("\n", 1)[0])

    def _log(self, msg: str | LocalizedMessage) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self._log_entries.append((timestamp, msg))
        self.log.insert(tk.END, f"[{timestamp}] {self._render_message(msg)}\n")
        self.log.see(tk.END)
        self._set_status(msg)

    def _clear_log(self) -> None:
        self._log_entries.clear()
        self.log.delete("1.0", tk.END)

    def _refresh_log_language(self) -> None:
        scroll_position = self.log.yview()[0]
        self.log.delete("1.0", tk.END)
        self.log.insert(tk.END, "".join(
            f"[{timestamp}] {self._render_message(msg)}\n"
            for timestamp, msg in self._log_entries
        ))
        self.log.yview_moveto(scroll_position)
        self._set_status(self._status_message)

    def _poll_queue(self) -> None:
        try:
            while True:
                level, msg = self._queue.get_nowait()
                if level == "error":
                    self._log(LocalizedMessage("log_error", message=msg))
                elif level == "busy":
                    self._set_status(msg)
                elif level == "idle":
                    if not self.is_busy():
                        self._set_status(msg)
                else:
                    self._log(msg)
        except queue.Empty:
            pass
        self.after(150, self._poll_queue)

    # ── Theme & language ──────────────────────────────────────────────────────

    def _save_ui_settings(self) -> None:
        try:
            write_ui_settings(self._settings_path,
                              language="de" if self.lang_var.get() == "Deutsch" else "en",
                              theme="dark" if self._dark else "light")
        except OSError as exc:
            self._log(LocalizedMessage("log_preferences_save_failed", error=exception_message(exc)))

    def _t(self, key: str):
        lang = "de" if self.lang_var.get() == "Deutsch" else "en"
        return STRINGS[lang][key]

    def _set_controller_mode(self, found: bool) -> None:
        self._controller_found = found
        self._on_global_active_changed()

    def _set_controller_notice(self, key: str, color: str) -> None:
        self._controller_status_key = key
        self.conn_status_lbl.configure(text=self._t(key), fg=color)

    def _refresh_global_toggle(self) -> None:
        btn = self._global_toggle
        if not btn:
            return
        on = bool(self.all_enabled_var.get())
        if not self._controller_found:
            bg, hov = PAL["SWITCH_DIS"], PAL["SWITCH_DIS"]
            btn.configure(
                text=self._t("all_zones_off" if on else "all_zones_on"),
                bg=bg, fg=PAL["DIM"],
                activebackground=hov, activeforeground=PAL["DIM"],
                cursor="arrow",
            )
            btn.bind("<ButtonPress-1>",   lambda e: "break")
            btn.bind("<ButtonRelease-1>", lambda e: "break")
            btn.bind("<Enter>", lambda e: None)
            btn.bind("<Leave>", lambda e, b=bg: btn.configure(bg=b))
        elif on:
            bg, hov = PAL["DANGER_BG"], PAL["DANGER_HOV"]
            btn.unbind("<ButtonPress-1>")
            btn.unbind("<ButtonRelease-1>")
            btn.configure(
                text=self._t("all_zones_off"),
                bg=bg, fg=PAL["DANGER_FG"],
                activebackground=hov, activeforeground=PAL["DANGER_FG"],
                cursor="hand2",
            )
            btn.bind("<Enter>", lambda e, h=hov: btn.configure(bg=h))
            btn.bind("<Leave>", lambda e, b=bg:  btn.configure(bg=b))
        else:
            bg, hov = PAL["SUCCESS_BG"], PAL["SUCCESS_HOV"]
            btn.unbind("<ButtonPress-1>")
            btn.unbind("<ButtonRelease-1>")
            btn.configure(
                text=self._t("all_zones_on"),
                bg=bg, fg=PAL["SUCCESS_FG"],
                activebackground=hov, activeforeground=PAL["SUCCESS_FG"],
                cursor="hand2",
            )
            btn.bind("<Enter>", lambda e, h=hov: btn.configure(bg=h))
            btn.bind("<Leave>", lambda e, b=bg:  btn.configure(bg=b))

    def _on_global_active_changed(self) -> None:
        global_on = bool(self.all_enabled_var.get())
        send_ok = self._controller_found and global_on
        send_state = ["!disabled"] if send_ok else ["disabled"]
        for btn in self._send_btns:
            btn.state(send_state)
        active_state = ["!disabled"] if global_on else ["disabled"]
        for btn in self._active_btns:
            btn.state(active_state)
        if hasattr(self, "_global_brightness_scale"):
            self._global_brightness_scale.state(active_state)
        for row in self.zone_rows.values():
            row.set_global_active(global_on)
            row.set_send_enabled(send_ok)
        self._refresh_global_toggle()
        self.refresh_selected_styles()
        self.refresh_inspector_state()
        self._refresh_tooltips()

    def _toggle_theme(self) -> None:
        self._dark = not self._dark
        PAL.update(DARK_PAL if self._dark else LIGHT_PAL)
        self.theme_btn.configure(text=self._t("theme_to_light" if self._dark else "theme_to_dark"))
        self._apply_theme()
        self._save_ui_settings()

    def _apply_theme(self) -> None:
        self._setup_styles()
        self.configure(bg=PAL["BG"])
        self.conn_status_lbl.configure(bg=PAL["BG"])
        for f in self._surface_frames:
            f.configure(bg=PAL["SURFACE"],
                        highlightbackground=PAL["BORDER"])
        self.log.configure(bg=PAL["LOG_BG"], fg=PAL["LOG_FG"], insertbackground=PAL["WHITE"])
        for row in self.zone_rows.values():
            row.apply_theme()
        for bar in self.pt_bars:
            bar.apply_theme()
        self.brightness_steps.refresh()
        self.frequency_steps.refresh()
        self._refresh_global_toggle()
        self.refresh_inspector_state()
        self._refresh_tooltips()

    def _apply_lang(self, _event=None) -> None:
        self.title(f"{self._t('title')} {APP_VERSION}")
        self.theme_btn.configure(text=self._t("theme_to_light" if self._dark else "theme_to_dark"))
        for widget, key in self._i18n:
            widget.configure(text=self._t(key))
        for i, name in enumerate(self._t("pt_names")):
            if i < len(self.pt_static_labels):
                self.pt_static_labels[i].configure(text=name)
        self.nb.tab(0, text=self._t("tab_basic"))
        self.nb.tab(1, text=self._t("tab_log"))
        for row in self.zone_rows.values():
            row.apply_lang(self._t)
        if self._controller_found:
            port = self._controller_port
            self.conn_status_lbl.configure(text=self._t("controller_found").format(port=port))
        elif self._controller_status_key:
            self.conn_status_lbl.configure(text=self._t(self._controller_status_key))
        self._refresh_log_language()
        self.refresh_inspector_state()
        self._on_global_active_changed()
        self._save_ui_settings()

    # ── Zone & profile state ──────────────────────────────────────────────────

    def current_zone_config(self, zone_name: str) -> ZoneConfig:
        return self.zone_rows[zone_name].get_config()

    def current_profile(self) -> Profile:
        return Profile(
            name=self.profile_name_var.get().strip() or "Default",
            all_enabled=bool(self.all_enabled_var.get()),
            zones={name: self.current_zone_config(name) for name in ZONES},
            pulse_train_hues=self.current_pulse_train_hues(),
        )

    def set_zone_config(self, zone_name: str, cfg: ZoneConfig) -> None:
        self.zone_rows[zone_name].set_config(cfg)

    def set_profile(self, profile: Profile) -> None:
        self.profile_name_var.set(profile.name)
        self.all_enabled_var.set(profile.all_enabled)
        for z in ZONES:
            self.zone_rows[z].set_config(profile.zones.get(z, ZoneConfig()))
        self.set_pulse_train_hues(getattr(profile, "pulse_train_hues", [0, 96, 160]))
        selected = self.selected_zone_var.get()
        self.select_zone(selected if selected in self.zone_rows else "Skull")

    def synced_zone_names(self) -> List[str]:
        return [name for name, row in self.zone_rows.items() if row.sync_hue.get()]

    def current_pulse_train_hues(self) -> List[int]:
        return [clamp_int(v.get(), 0, 255) for v in self.pt_hue_vars]

    def set_pulse_train_hues(self, hues: Iterable[int]) -> None:
        for i, hue in enumerate(_pad_pt_hues(hues)):
            self.pt_hue_vars[i].set(clamp_int(hue, 0, 255))
            self.update_pt_ui(i)

    # ── UI refresh ────────────────────────────────────────────────────────────

    def update_zone_ui(self, zone_name: str) -> None:
        row = self.zone_rows[zone_name]
        row.update_ui()
        if self.selected_zone_var.get() == zone_name and not self._syncing_inspector:
            self._syncing_inspector = True
            try:
                self.selected_brightness_var.set(clamp_int(row.brightness.get(), 0, 5))
                self.selected_frequency_var.set(clamp_int(row.frequency.get(), 0, 5))
            finally:
                self._syncing_inspector = False
            self.refresh_inspector_state()
        self.refresh_selected_styles()

    def update_pt_ui(self, index: int) -> None:
        hue = clamp_int(self.pt_hue_vars[index].get(), 0, 255)
        self.pt_hue_vars[index].set(hue)
        if index < len(self.pt_labels):
            self.pt_labels[index].configure(text=f"{hue}")
        for name, row in self.zone_rows.items():
            if normalize_pattern(row.pattern.get()) in PULSETRAIN_PATTERNS:
                row.update_ui()

    def refresh_selected_styles(self) -> None:
        selected  = self.selected_zone_var.get()
        global_on = bool(self.all_enabled_var.get())
        for zone_name, row in self.zone_rows.items():
            row.set_selected(global_on and zone_name == selected)

    def refresh_inspector_state(self) -> None:
        zone_name = self.selected_zone_var.get()
        if zone_name not in self.zone_rows:
            return
        cfg     = self.current_zone_config(zone_name)
        pattern = normalize_pattern(cfg.pattern)

        show_hue = pattern not in PULSETRAIN_PATTERNS and pattern != "Rainbow"
        hue_part = f" · Hue {cfg.custom_hue}" if show_hue else ""
        self.inspector_title.configure(text=f"{zone_name} · {pattern}{hue_part}")
        if not cfg.enabled:
            self.frequency_hint.configure(text=self._t("zone_off_dot"))
        elif pattern in ANIMATED_PATTERNS:
            self.frequency_hint.configure(text=self._t("tempo_active"))
        else:
            self.frequency_hint.configure(text=self._t("tempo_inactive"))

        pt_effect = pattern in PULSETRAIN_PATTERNS
        self.pt_title.configure(
            style="CardTitle.TLabel" if (cfg.enabled and pt_effect) else "Muted.TLabel"
        )
        if not cfg.enabled:
            self.pt_hint.configure(text=self._t("zone_off_dot"))
        elif pt_effect:
            self.pt_hint.configure(text=self._t("pt_this_zone"))
        else:
            self.pt_hint.configure(text=self._t("pt_inactive"))
        self.refresh_right_enabled_state()

    def refresh_right_enabled_state(self) -> None:
        zone_name = self.selected_zone_var.get()
        if zone_name not in self.zone_rows:
            return
        cfg          = self.current_zone_config(zone_name)
        zone_enabled = bool(cfg.enabled) and bool(self.all_enabled_var.get())
        pattern      = normalize_pattern(cfg.pattern)

        self.brightness_steps.set_enabled(zone_enabled)
        self.frequency_steps.set_enabled(zone_enabled and pattern in ANIMATED_PATTERNS)

        pt_enabled = zone_enabled and pattern in PULSETRAIN_PATTERNS
        for bar  in self.pt_bars:
            bar.set_enabled(pt_enabled)
        for spin in self.pt_spins:
            spin.state(["!disabled"] if pt_enabled else ["disabled"])
        for lbl  in self.pt_static_labels:
            lbl.configure(style="MiniLabel.TLabel" if pt_enabled else "Disabled.TLabel")
        for lbl  in self.pt_labels:
            lbl.configure(style="Muted.TLabel" if pt_enabled else "Disabled.TLabel")
        for btn  in self.pt_buttons:
            btn.state(["!disabled"] if (pt_enabled and self._controller_found) else ["disabled"])

    def select_zone(self, zone_name: str) -> None:
        if zone_name not in self.zone_rows:
            return
        if not bool(self.all_enabled_var.get()):
            return
        self.selected_zone_var.set(zone_name)
        cfg = self.current_zone_config(zone_name)
        self._syncing_inspector = True
        try:
            self.selected_brightness_var.set(cfg.brightness)
            self.selected_frequency_var.set(cfg.frequency)
        finally:
            self._syncing_inspector = False
        self.refresh_selected_styles()
        self.refresh_inspector_state()
        self.after(25, self.refresh_selected_styles)

    # ── Event handlers ────────────────────────────────────────────────────────

    def on_zone_control_changed(self, zone_name: str) -> None:
        self.select_zone(zone_name)
        self.update_zone_ui(zone_name)

    def on_zone_pattern_changed(self, zone_name: str) -> None:
        self.select_zone(zone_name)
        self.update_zone_ui(zone_name)
        self.focus_set()
        self.after(25, self.refresh_selected_styles)

    def on_sync_toggled(self, zone_name: str) -> None:
        self.select_zone(zone_name)
        if self.zone_rows[zone_name].sync_hue.get():
            selected = self.selected_zone_var.get()
            if selected in self.zone_rows and selected != zone_name:
                hue = clamp_int(self.zone_rows[selected].custom_hue.get(), 0, 255)
                self.zone_rows[zone_name].custom_hue.set(hue)
        for z in self.zone_rows:
            self.update_zone_ui(z)

    def on_zone_hue_changed(self, zone_name: str) -> None:
        self.select_zone(zone_name)
        hue = clamp_int(self.zone_rows[zone_name].custom_hue.get(), 0, 255)
        if self.zone_rows[zone_name].sync_hue.get():
            for other_name, row in self.zone_rows.items():
                if other_name != zone_name and row.sync_hue.get():
                    row.custom_hue.set(hue)
                    self.update_zone_ui(other_name)
        self.update_zone_ui(zone_name)

    def on_inspector_changed(self) -> None:
        if self._syncing_inspector:
            return
        zone_name = self.selected_zone_var.get()
        if zone_name not in self.zone_rows:
            return
        row = self.zone_rows[zone_name]
        if not row.enabled.get():
            self.refresh_inspector_state()
            return
        row.brightness.set(clamp_int(self.selected_brightness_var.get(), 0, 5))
        row.frequency.set(clamp_int(self.selected_frequency_var.get(), 0, 5))
        self.update_zone_ui(zone_name)

    def on_global_brightness(self, value) -> None:
        val = clamp_int(round(float(value)), 0, 5)
        self.global_brightness_var.set(val)
        self.global_brightness_label.configure(text=str(val))
        for z, row in self.zone_rows.items():
            row.brightness.set(val)
            self.update_zone_ui(z)

    # ── Command dispatch ──────────────────────────────────────────────────────

    def _send_commands(self, label: str | LocalizedMessage, commands) -> None:
        cmd_str = commands if isinstance(commands, str) else ",".join(commands)
        self._log(LocalizedMessage("log_command", command=cmd_str))
        if self.dry_run_var.get():
            self._log(LocalizedMessage("log_dry_run_send"))
            return
        if self.is_busy():
            self._log(LocalizedMessage("log_queued", label=label))
        self.run_worker(label, self._backend().run_commands, cmd_str)

    def apply_profile(self) -> None:
        self._send_commands(LocalizedMessage("log_profile_apply"), profile_to_commands(self.current_profile()))

    def apply_zone(self, zone_name: str) -> None:
        self._send_commands(LocalizedMessage("log_zone_apply", zone=zone_name),
                            build_zone_commands(zone_name, self.zone_rows[zone_name].get_config()))

    def apply_zone_from_row(self, zone_name: str) -> None:
        self.select_zone(zone_name)
        self.apply_zone(zone_name)
        self.focus_set()
        self.after(25, self.refresh_selected_styles)

    def apply_selected_zone(self) -> None:
        self.apply_zone(self.selected_zone_var.get())

    def copy_selected_zone_to_all(self) -> None:
        self.copy_zone_to_all(self.selected_zone_var.get())

    def copy_zone_to_all(self, source_zone: str) -> None:
        cfg = self.zone_rows[source_zone].get_config()
        for z, row in self.zone_rows.items():
            row.set_config(cfg)
        self._log(LocalizedMessage("log_zone_copied", zone=source_zone))

    def pulse_train_color_commands(self) -> List[str]:
        h = self.current_pulse_train_hues()
        return [f"C5:{h[0]}", f"C6:{h[1]}", f"C7:{h[2]}"]

    def apply_pulse_train_colors(self) -> None:
        cmds: List[str] = []
        zone_name = self.selected_zone_var.get()
        row = self.zone_rows.get(zone_name)
        if row and normalize_pattern(row.pattern.get()) in PULSETRAIN_PATTERNS:
            cmds.extend(build_zone_commands(zone_name, row.get_config()))
        cmds.extend(self.pulse_train_color_commands())
        self._send_commands(LocalizedMessage("log_palette_apply"), cmds)

    # ── Hardware actions ──────────────────────────────────────────────────────

    def refresh_ports(self, select_guess: bool = True) -> None:
        ports = NucRgbSerial.list_serial_ports()
        self.port_combo["values"] = ports
        if select_guess or not self.port_var.get():
            self.port_var.set(NucRgbSerial.guess_port())
        self._log(LocalizedMessage("log_ports_found", count=len(ports)))

    def auto_read_status_on_startup(self) -> None:
        if self.dry_run_var.get():
            return
        self._set_controller_notice("controller_searching", PAL["MUTED"])

        def worker():
            # Phase 1: find Prolific/PL2303 chip in port list — no serial open needed
            target_port = None
            if list_ports is not None:
                for p in list_ports.comports():
                    desc = (p.description or "").lower()
                    vid_match  = (p.vid == 0x067B)
                    desc_match = "prolific" in desc or "pl2303" in desc
                    if vid_match or desc_match:
                        target_port = p.device
                        break

            if not target_port:
                def no_hw():
                    self._log(LocalizedMessage("log_no_controller_startup"))
                    self._set_controller_notice("controller_missing", "#E05555")
                self.after(0, no_hw)
                return

            # Phase 2: open port, send STA? and verify response
            try:
                with serial.Serial(target_port, timeout=2) as ser:
                    time.sleep(TIME_START)
                    ser.reset_input_buffer()
                    ser.write(b"STA?\n")
                    time.sleep(TIME_CMD)
                    sta_raw = ser.read_until(b"\n").decode(errors="replace").strip()

                status = None
                try:
                    status = NucRgbSerial.parse_status_raw(sta_raw)
                except Exception:
                    pass

                if not status:
                    def no_resp():
                        self._log(LocalizedMessage("log_invalid_status_response", port=target_port, raw=sta_raw))
                        self._set_controller_notice("controller_missing", "#E05555")
                    self.after(0, no_resp)
                    return

                p, s = target_port, status

                def on_ok():
                    self._controller_port = p
                    self._log(LocalizedMessage("controller_found_status", port=p))
                    self.port_var.set(p)
                    self.conn_status_lbl.configure(
                        text=self._t("controller_found").format(port=p), fg="#4CAF50"
                    )
                    self._set_controller_mode(True)
                    self.apply_status_to_ui(s)
                self.after(0, on_ok)

            except Exception as exc:
                msg = exception_message(exc)
                def on_fail():
                    self._log(LocalizedMessage("log_startup_error", port=target_port, error=msg))
                    self._set_controller_notice("controller_missing", "#E05555")
                self.after(0, on_fail)

        threading.Thread(target=worker, daemon=True).start()

    def apply_status_to_ui(self, status: Dict[str, object]) -> None:
        try:
            self.all_enabled_var.set(bool(status.get("enabled", True)))
            for zone_name, raw in status.get("zones", {}).items():
                if zone_name not in self.zone_rows:
                    continue
                raw_pattern  = normalize_pattern(raw.get("pattern", "Solid"))
                zone_enabled = raw_pattern != "Off"
                ui_pattern   = "Solid" if raw_pattern == "Off" else raw_pattern
                self.zone_rows[zone_name].set_config(ZoneConfig(
                    enabled=zone_enabled, pattern=ui_pattern,
                    brightness=clamp_int(raw.get("brightness", 5), 0, 5),
                    frequency=clamp_int(raw.get("frequency", 0), 0, 5),
                    rainbow=False,
                    custom_hue=clamp_int(raw.get("hue", 96), 0, 255),
                ))
            if "pulse_train_hues" in status:
                self.set_pulse_train_hues(status["pulse_train_hues"])
        except Exception as exc:
            self._log(LocalizedMessage("log_status_apply_error", error=exception_message(exc)))

    def reset_default(self) -> None:
        if self.dry_run_var.get():
            self._log(LocalizedMessage("log_dry_run_reset"))
            return

        def reset_and_read():
            backend = self._backend()
            backend.run_commands("RST")
            time.sleep(0.3)
            status = backend.get_status()
            self.after(0, lambda: self.apply_status_to_ui(status))
            return json.dumps(status, indent=2, ensure_ascii=False)

        self.run_worker(LocalizedMessage("log_reset_status"), reset_and_read)

    def _toggle_global_power(self) -> None:
        new_on = not bool(self.all_enabled_var.get())
        self.all_enabled_var.set(new_on)
        if new_on:
            self._send_commands(LocalizedMessage("log_power_on"), "BTN:1")
        else:
            self._send_commands(LocalizedMessage("log_power_off"), "BTN:0")

    def read_status(self) -> None:
        if self.dry_run_var.get():
            self._log(LocalizedMessage("log_dry_run_status"))
            return

        def read_and_format():
            status = self._backend().get_status()
            self.after(0, lambda: self.apply_status_to_ui(status))
            return json.dumps(status, indent=2, ensure_ascii=False)

        self.run_worker(LocalizedMessage("log_status"), read_and_format)

    def test_id(self) -> None:
        if self.dry_run_var.get():
            self._log(LocalizedMessage("log_dry_run_id"))
            return
        self.run_worker(LocalizedMessage("log_controller_id"), self._backend().get_controller_id)

    # ── Profile persistence ───────────────────────────────────────────────────

    def save_log(self) -> None:
        path = filedialog.asksaveasfilename(
            title=self._t("save_log_btn"), defaultextension=".txt",
            filetypes=[("Text", "*.txt"), (self._t("dialog_all_files"), "*.*")],
            initialfile=f"{APP_NAME}_{APP_VERSION}_log.txt",
        )
        if not path:
            return
        Path(path).write_text(self.log.get("1.0", tk.END), encoding="utf-8")
        self._log(LocalizedMessage("log_saved", path=str(path)))

    def save_profile(self) -> None:
        profile = self.current_profile()
        data = {
            "name":             profile.name,
            "all_enabled":      profile.all_enabled,
            "zones":            {name: asdict(cfg) for name, cfg in profile.zones.items()},
            "pulse_train_hues": profile.pulse_train_hues,
        }
        path = filedialog.asksaveasfilename(
            title=self._t("dialog_save_profile"), defaultextension=".json",
            filetypes=[("JSON", "*.json"), (self._t("dialog_all_files"), "*.*")],
            initialfile=f"{profile.name}.json",
        )
        if not path:
            return
        Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        self._log(LocalizedMessage("log_profile_saved", path=str(path)))

    def load_profile(self) -> None:
        path = filedialog.askopenfilename(
            title=self._t("dialog_load_profile"),
            filetypes=[("JSON", "*.json"), (self._t("dialog_all_files"), "*.*")],
        )
        if not path:
            return
        data  = json.loads(Path(path).read_text(encoding="utf-8"))
        zones = {}
        for name, raw_cfg in data.get("zones", {}).items():
            raw_cfg = dict(raw_cfg)
            # Backward compat: old profiles store color name instead of custom_hue.
            if "custom_hue" not in raw_cfg and "color" in raw_cfg:
                raw_cfg["custom_hue"] = COLORS.get(raw_cfg["color"], 96)
            if "pattern" in raw_cfg:
                raw_cfg["pattern"] = normalize_pattern(raw_cfg["pattern"])
            # Filter unknown fields so future schema additions don't cause TypeError.
            raw_cfg = {k: v for k, v in raw_cfg.items() if k in _ZONE_CONFIG_FIELDS}
            zones[name] = ZoneConfig(**raw_cfg)
        profile = Profile(
            name=data.get("name", Path(path).stem),
            all_enabled=bool(data.get("all_enabled", True)),
            zones={name: zones.get(name, ZoneConfig()) for name in ZONES},
            pulse_train_hues=data.get("pulse_train_hues", [0, 96, 160]),
        )
        self.set_profile(profile)
        self._log(LocalizedMessage("log_profile_loaded", path=str(path)))


def main() -> None:
    if SERIAL_IMPORT_ERROR is not None:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "pyserial missing",
            "pyserial is not installed.\n\nInstall with:\npy -m pip install pyserial",
        )
        return
    app = CanyonGlow()
    app.mainloop()


if __name__ == "__main__":
    main()
