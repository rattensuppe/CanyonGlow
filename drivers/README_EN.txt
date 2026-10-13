CanyonGlow v1.0 - Serial driver

If the tool finds the controller, the required driver is already installed.
Intel NUC Software Studio is not required for this tool.

If no controller is found:
1. Open Windows Update and check for updates. Prolific provides the serial driver
   through Windows Update. If available, also check "Optional updates" for
   Prolific driver updates.
2. If Windows Update does not install a suitable driver, use the official
   Prolific download:
   https://www.prolific.com.tw/en/portfolio-item/pl2303gd/
   Under "Drivers & Software", download the "Windows Driver Installer Setup
   Program" for your Windows version. Extract the ZIP and run the installer
   inside; restart Windows if needed.
3. In Device Manager, look under "Ports (COM & LPT)" for a Prolific port, e.g.
   "Prolific PL2303GD USB Serial COM Port (COM3)". The COM number may differ.
   Restart CanyonGlow after installing a driver to run automatic controller
   detection again. "Scan Ports" refreshes the port list; "Check Device" queries
   the controller ID and shows the result in the log, but does not itself enable
   sending.

This directory contains instructions only. No driver is bundled or installed
by the RGB tool's setup.
