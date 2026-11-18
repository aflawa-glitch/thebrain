from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_portable_root_and_configuration_exist():
    assert (ROOT / "JULIAN_PORTABLE_ROOT").is_file()
    assert (ROOT / "config" / "portable.env.example").is_file()
    assert (ROOT / "launcher" / "julian-portable.sh").is_file()
    assert (ROOT / "launcher" / "julian-portable.ps1").is_file()


def test_portable_config_declares_required_quality_dependencies():
    config = (ROOT / "config" / "portable.env.example").read_text(encoding="utf-8")
    for key in ("PYTHON_PATH=", "LLAMA_SERVER_PATH=", "MODEL_PATH=", "LLM_ENABLED=true", "CONTEXT_SIZE="):
        assert key in config


def test_portable_launchers_do_not_use_legacy_fixed_mount_path():
    for rel in ("launcher/julian-portable.sh", "launcher/julian-portable.ps1"):
        source = (ROOT / rel).read_text(encoding="utf-8")
        assert "/Volumes/HGRJ5880J/" not in source
        assert "JULIAN_PORTABLE_ROOT" in source


def test_portable_launcher_fails_closed_instead_of_using_system_python():
    shell = (ROOT / "launcher" / "julian-portable.sh").read_text(encoding="utf-8")
    powershell = (ROOT / "launcher" / "julian-portable.ps1").read_text(encoding="utf-8")
    assert "No system-Python fallback was attempted" in shell
    assert "No system-Python fallback was attempted" in powershell
    assert "No process was killed" in shell
    assert "Stopped only the processes started by this launcher" in shell


def test_portable_mac_setup_helper_is_present_and_non_mutating():
    helper = (ROOT / "scripts" / "configure_portable_runtime.sh").read_text(encoding="utf-8")
    assert "No packages were installed" in helper
    assert "no environment rewritten" in helper
    assert (ROOT / "JULIAN_PORTABLE_ROOT").is_file()

def test_bash_launcher_resolves_actual_model_identifier():
    shell = (ROOT / "launcher" / "julian-portable.sh").read_text(encoding="utf-8")
    assert "LLM_MODEL" in shell
    assert "JULIAN_LLM_MODEL" in shell
    assert "/v1/models" in shell
