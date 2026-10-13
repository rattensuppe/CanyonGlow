"""Windows entry point; the normal launch uses the unchanged application."""
import json
import sys
import tempfile
import traceback
from pathlib import Path

import canyonglow


def close_test_app(app) -> None:
    for timer in app.tk.splitlist(app.tk.call("after", "info")):
        # The owning widget deletes its Python callback command during destroy.
        app.tk.call("after", "cancel", timer)
    app.destroy()


def self_test(report_path: str) -> int:
    app = None
    settings_directory = None
    callback_errors = []
    try:
        # Exercise the packaged GUI without contacting the user's controller.
        canyonglow.NucRgbSerial.list_serial_ports = staticmethod(lambda: [])
        canyonglow.NucRgbSerial.guess_port = staticmethod(lambda: "COM3")
        canyonglow.CanyonGlow.auto_read_status_on_startup = lambda self: None
        settings_directory = tempfile.TemporaryDirectory(prefix="ui-settings-test-",
                                                        dir=Path(report_path).resolve().parent)
        settings_path = Path(settings_directory.name) / "settings.json"
        app = canyonglow.CanyonGlow(settings_path=settings_path)
        app.withdraw()
        app.report_callback_exception = lambda exc, value, tb: callback_errors.append(
            "".join(traceback.format_exception(exc, value, tb)))
        assert app.lang_var.get() == "English"
        assert app._dark
        assert not settings_path.exists()
        assert app.title() == f"{canyonglow.APP_NAME} {canyonglow.APP_VERSION}"
        assert app._t("title") == "CanyonGlow"
        assert app._t("subtitle") == "RGB Control for NUC 11 & 12 Extreme"
        assert len(app._tooltips) == 31
        assert all(tooltip.text for tooltip in app._tooltips)
        zone = app.zone_rows["Skull"]
        tooltip = zone._sync_switch._tooltip
        tooltip._create_window()
        assert not tooltip._window.winfo_viewable()
        assert tooltip._label.cget("text") == canyonglow.STRINGS["en"]["tooltip_zone_sync"]
        assert tooltip._window.grab_current() is None
        # Signed positions must remain valid for monitors to the left of the main screen.
        tooltip._window.geometry("+-20+30")
        tooltip.refresh()
        app._set_controller_notice("controller_missing", "#E05555")
        assert "No controller" in app.conn_status_lbl.cget("text")
        app._controller_port = "TEST"
        app._set_controller_mode(True)
        app._log(canyonglow.LocalizedMessage("controller_found_status", port="TEST"))
        app.lang_var.set("English")
        app._apply_lang()
        assert app.title() == f"{canyonglow.APP_NAME} {canyonglow.APP_VERSION}"
        assert app._t("subtitle") == "RGB Control for NUC 11 & 12 Extreme"
        assert app.status_var.get() == "Controller found on TEST"
        assert "Controller found" in app.conn_status_lbl.cget("text")
        app.lang_var.set("Deutsch")
        app._apply_lang()
        assert app.title() == f"{canyonglow.APP_NAME} {canyonglow.APP_VERSION}"
        assert app._t("subtitle") == "RGB-Steuerung für NUC 11 & 12 Extreme"
        assert app.status_var.get() == "Controller gefunden auf TEST"
        assert tooltip._label.cget("text") == canyonglow.STRINGS["de"]["tooltip_zone_sync"]
        assert zone._sync_switch.bind_class(tooltip._tag, "<Enter>")
        assert tooltip._tag in zone._sync_switch.bindtags()
        assert "ausschalten" in app._global_toggle._tooltip.text
        app.all_enabled_var.set(False)
        assert "einschalten" in app._global_toggle._tooltip.text
        app.all_enabled_var.set(True)
        tooltip._schedule()
        assert tooltip._timer is not None and tooltip._window is None
        tooltip.hide()
        assert tooltip._timer is None
        # Existing button hover bindings must survive language/state refreshes.
        assert zone._sync_switch.bind("<Enter>")
        assert zone._sync_switch.bind_class(tooltip._tag, "<Enter>")
        assert zone._sync_switch.bind_class(tooltip._tag, "<Leave>")
        bundle_root = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
        example_path = bundle_root / "example_default_green_profile.json"
        expected_profile = json.loads(example_path.read_text(encoding="utf-8"))
        original_open_dialog = canyonglow.filedialog.askopenfilename
        try:
            canyonglow.filedialog.askopenfilename = lambda **kwargs: str(example_path)
            app.load_profile()
        finally:
            canyonglow.filedialog.askopenfilename = original_open_dialog
        assert canyonglow.asdict(app.current_profile()) == expected_profile
        original_save_dialog = canyonglow.filedialog.asksaveasfilename
        original_open_dialog = canyonglow.filedialog.askopenfilename
        try:
            captured = {}
            def cancel_dialog(**kwargs):
                captured.clear()
                captured.update(kwargs)
                return ""
            canyonglow.filedialog.asksaveasfilename = cancel_dialog
            canyonglow.filedialog.askopenfilename = cancel_dialog
            for language in ("English", "Deutsch"):
                app.lang_var.set(language)
                app._apply_lang()
                for method, key in ((app.save_log, "save_log_btn"),
                                    (app.save_profile, "dialog_save_profile"),
                                    (app.load_profile, "dialog_load_profile")):
                    method()
                    assert captured["title"] == app._t(key)
                    assert captured["filetypes"][-1][0] == app._t("dialog_all_files")
        finally:
            canyonglow.filedialog.asksaveasfilename = original_save_dialog
            canyonglow.filedialog.askopenfilename = original_open_dialog
        app._clear_log()
        app.dry_run_var.set(True)
        app._send_commands(canyonglow.LocalizedMessage("log_power_on"), "BTN:1")
        assert "BTN:1" in app.log.get("1.0", "end")
        assert "Dry Run aktiv: nicht gesendet" in app.log.get("1.0", "end")
        app._toggle_theme()
        tooltip._create_window()
        assert tooltip._label.cget("bg") == canyonglow.LIGHT_PAL["SURFACE"]
        app._toggle_theme()
        assert tooltip._label.cget("bg") == canyonglow.DARK_PAL["SURFACE"]
        tooltip.hide()
        app._set_controller_mode(False)
        for language, expected in (("English", "No controller"), ("Deutsch", "Kein Controller")):
            app.lang_var.set(language)
            app._apply_lang()
            assert expected in app.conn_status_lbl.cget("text")
        # Destroying a hovered widget must cancel pending help and remove its bindings.
        temporary = canyonglow.tk.Button(app)
        temporary_tip = canyonglow.Tooltip(temporary, lambda: "Temporary help")
        temporary_tip._schedule()
        temporary.destroy()
        assert temporary_tip._timer is None
        assert not app.bind_class(temporary_tip._tag, "<Enter>")
        app.update_idletasks()
        # Simulate four restarts using a test file; never modify the user's preferences.
        for language in ("Deutsch", "English"):
            for theme in ("light", "dark"):
                app.lang_var.set(language)
                app._apply_lang()
                if app._dark != (theme == "dark"):
                    app._toggle_theme()
                assert json.loads(settings_path.read_text()) == {
                    "language": "de" if language == "Deutsch" else "en", "theme": theme}
                close_test_app(app)
                app = canyonglow.CanyonGlow(settings_path=settings_path)
                app.withdraw()
                app.report_callback_exception = lambda exc, value, tb: callback_errors.append(
                    "".join(traceback.format_exception(exc, value, tb)))
                assert app.lang_var.get() == language
                assert app._dark == (theme == "dark")
                palette = canyonglow.DARK_PAL if app._dark else canyonglow.LIGHT_PAL
                assert app.cget("bg") == palette["BG"]
                assert app.log.cget("bg") == palette["LOG_BG"]
                assert app.theme_btn.cget("text") == app._t("theme_to_light" if app._dark else "theme_to_dark")
                assert app.zone_rows["Skull"]._sync_switch._tooltip.text == app._t("tooltip_zone_sync")
        # Invalid preferences fall back independently; malformed files still allow startup.
        for content, expected in (
            ('{"language": "fr", "theme": "light"}', {"language": "en", "theme": "light"}),
            ('{"language": "de", "theme": []}', {"language": "de", "theme": "dark"}),
            ('[]', {"language": "en", "theme": "dark"}),
            ('{', {"language": "en", "theme": "dark"}),
        ):
            settings_path.write_text(content)
            assert canyonglow.read_ui_settings(settings_path) == expected
        close_test_app(app)
        app = canyonglow.CanyonGlow(settings_path=settings_path)
        app.withdraw()
        assert app.lang_var.get() == "English" and app._dark
        assert settings_path.read_text() == "{"
        # A write error must leave the selected interface usable and report the failure.
        close_test_app(app)
        blocker = Path(settings_directory.name) / "blocked-directory"
        blocker.write_text("not a directory")
        app = canyonglow.CanyonGlow(settings_path=blocker / "settings.json")
        app.withdraw()
        app.report_callback_exception = lambda exc, value, tb: callback_errors.append(
            "".join(traceback.format_exception(exc, value, tb)))
        app.lang_var.set("Deutsch")
        app._apply_lang()
        app._toggle_theme()
        assert app.lang_var.get() == "Deutsch" and not app._dark
        assert "nicht gespeichert" in app.log.get("1.0", "end")
        assert not list(Path(settings_directory.name).glob(".settings-*.tmp"))
        report = {
            "ok": True,
            "app_name": canyonglow.APP_NAME,
            "app_version": canyonglow.APP_VERSION,
            "frozen": bool(getattr(sys, "frozen", False)),
            "tk_version": canyonglow.tk.TkVersion,
            "checks": ["English startup", "name/version/subtitle", "DE/EN switching",
                       "bilingual tooltips and timer cleanup", "translated file dialogs",
                       "existing JSON profiles", "logging", "dry run", "light/dark mode",
                       "language/theme persistence across four restarts",
                       "invalid settings fallback", "non-blocking settings write failure"],
            "hardware_accessed": False,
        }
    except Exception:
        report = {"ok": False, "error": traceback.format_exc()}
    finally:
        if app is not None:
            close_test_app(app)
        if settings_directory is not None:
            settings_directory.cleanup()
    if callback_errors:
        report = {"ok": False, "error": "\n".join(callback_errors)}
    Path(report_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test-report":
        raise SystemExit(self_test(sys.argv[2]))
    canyonglow.main()
