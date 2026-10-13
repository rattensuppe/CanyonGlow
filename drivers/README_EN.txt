CanyonGlow v1.0 - Serial driver

If the tool finds the controller, the required driver is already installed.
Intel NUC Software Studio is not required for this tool.

Controller and driver identification:
The RGB controller uses a Prolific PL2303 USB-to-serial bridge. On the tested
NUC 11 Extreme, Device Manager lists it as "Prolific PL2303GD USB Serial COM Port"
under "Ports (COM & LPT)"; the driver provider is "Prolific". Windows adds the
assigned COM-port number to the name. The required Windows serial driver is
provided by Prolific; use Windows Update or the official installer below.

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
3. In Device Manager, look under "Ports (COM & LPT)" for the Prolific port named
   above. Use the COM-port number shown on your system; it is not a fixed number.
   Restart CanyonGlow after installing a driver to run automatic controller
   detection again. "Scan Ports" refreshes the port list; "Check Device" queries
   the controller ID and shows the result in the log, but does not itself enable
   sending.

This directory contains instructions only. No driver is bundled or installed
by the RGB tool's setup.
