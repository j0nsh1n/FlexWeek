"""The Windows installers' fixed facts. Windows itself runs them in the release workflow.

0.9.0 and 0.9.1 shipped a shortcut that pointed at the build machine's folder. These
checks keep shortcut paths as installer constants resolved on the user's PC, keep the
ids that upgrades depend on, and keep the file names in the scripts, the workflow and
the download docs in step.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ISS = (ROOT / "packaging/windows/flexweek.iss").read_text(encoding="utf-8")
WXS = ET.parse(ROOT / "packaging/windows/flexweek.wxs").getroot()
WORKFLOW = (ROOT / ".github/workflows/release-windows.yml").read_text(encoding="utf-8")
NS = {"wix": "http://wixtoolset.org/schemas/v4/wxs"}
SETUP_EXE = "FlexWeek-Windows-x64-Setup.exe"
MSI = "FlexWeek-Windows-x64.msi"


def iss_section(name: str) -> list[str]:
    body = re.search(rf"^\[{name}\]\n(.*?)(?=^\[|\Z)", ISS, re.S | re.M)
    assert body, f"flexweek.iss has no [{name}] section"
    return [line for line in body.group(1).splitlines() if line.strip() and not line.startswith(";")]


def iss_setup() -> dict[str, str]:
    return dict(line.split("=", 1) for line in iss_section("Setup"))


def test_setup_exe_installs_for_the_current_account_and_keeps_its_app_id() -> None:
    setup = iss_setup()
    assert setup["AppId"] == "{{06CA8084-53C1-43D1-9EF7-971998846AB0}"
    assert setup["PrivilegesRequired"] == "lowest"
    assert setup["DefaultDirName"] == r"{autopf}\FlexWeek"
    assert setup["OutputBaseFilename"] + ".exe" == SETUP_EXE
    assert setup["ArchitecturesInstallIn64BitMode"] == "x64compatible"


def test_setup_exe_shortcuts_open_the_installed_app_from_its_folder() -> None:
    icons = iss_section("Icons")
    assert [line.split(";")[0] for line in icons] == [
        r'Name: "{autoprograms}\FlexWeek"', r'Name: "{autodesktop}\FlexWeek"'
    ]
    for line in icons:
        assert r'Filename: "{app}\FlexWeek.exe"' in line
        assert 'WorkingDir: "{app}"' in line
    # Nothing in the script may name a folder on the build machine.
    assert not re.search(r"(?<![\w{])[A-Za-z]:\\", ISS)
    assert "zip-stage" not in ISS


def test_msi_installs_for_every_account_and_keeps_its_upgrade_code() -> None:
    package = WXS.find("wix:Package", NS)
    assert package is not None
    assert package.get("Scope") == "perMachine"
    assert package.get("UpgradeCode") == "8BF59E0D-5BB2-4D33-9510-C48E3E4B4F46"
    assert package.get("Version") == "$(var.Version)"
    assert package.find("wix:MajorUpgrade", NS) is not None
    program_files = package.find("wix:StandardDirectory[@Id='ProgramFiles64Folder']", NS)
    assert program_files is not None
    install = program_files.find("wix:Directory[@Id='INSTALLFOLDER']", NS)
    assert install is not None and install.get("Name") == "FlexWeek"
    files = install.find("wix:Files", NS)
    assert files is not None and files.get("Include") == r"!(bindpath.app)\**"


def test_msi_shortcut_opens_the_installed_app_from_its_folder() -> None:
    shortcuts = WXS.findall(".//wix:Shortcut", NS)
    assert len(shortcuts) == 1
    assert shortcuts[0].get("Target") == "[INSTALLFOLDER]FlexWeek.exe"
    assert shortcuts[0].get("WorkingDirectory") == "INSTALLFOLDER"
    menu = WXS.find("wix:Package/wix:StandardDirectory[@Id='ProgramMenuFolder']", NS)
    assert menu is not None and menu.find(".//wix:Shortcut", NS) is not None


def test_workflow_builds_tests_and_uploads_both_installers_and_no_zip() -> None:
    assert "packaging\\windows\\flexweek.iss" in WORKFLOW
    assert f"-o dist\\{MSI}" in WORKFLOW
    upload = WORKFLOW.split('gh release upload "$env:TAG"', 1)[1].split("--clobber", 1)[0]
    assert re.findall(r"dist\\(\S+)", upload) == [SETUP_EXE, f"{SETUP_EXE}.sha256", MSI, f"{MSI}.sha256"]
    # The install test runs the app through each shortcut and the workflow makes no shortcut itself.
    assert "Install, open and uninstall each installer" in WORKFLOW
    assert "$link.TargetPath" in WORKFLOW
    assert ".Save()" not in WORKFLOW
    assert ".zip" not in WORKFLOW
