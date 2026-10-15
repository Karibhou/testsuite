"""Behavioral boundaries of the guest command/result adapter; no live GNOME calls."""

import json
import os
from pathlib import Path
import shutil
import subprocess
from unittest.mock import Mock

import pytest

from tests.shared.extension_session import ExtensionSession, installed_path, parse_shell_json


def test_shell_json_preserves_unicode_rendered_labels_and_false_state():
    output = "(true, '{\"title\":\"THỊ TRƯỜNG TÀI CHÍNH\",\"visible\":false,\"rows\":[\"BTC-USD\",\"^GSPC\"]}')"
    assert parse_shell_json(output) == {
        "title": "THỊ TRƯỜNG TÀI CHÍNH", "visible": False, "rows": ["BTC-USD", "^GSPC"],
    }


@pytest.mark.parametrize("output", [
    "(false, 'true')", "(true, 'undefined')", "(true, 1)", "true", "(true, '{broken')",
])
def test_rejected_or_malformed_eval_cannot_pass_a_rendering_assertion(output):
    with pytest.raises(AssertionError):
        parse_shell_json(output)


def test_installed_path_uses_the_cli_candidate_path_not_a_system_default():
    assert installed_path("Example\n  State: ACTIVE\n  Path: /var/home/guest/.local/share/gnome-shell/extensions/example@host\n") == Path(
        "/var/home/guest/.local/share/gnome-shell/extensions/example@host"
    )


@pytest.mark.parametrize("info", ["State: ACTIVE", "Path: relative/extension"])
def test_missing_candidate_location_is_a_failure(info):
    with pytest.raises(AssertionError, match="absolute Path"):
        installed_path(info)


def test_failed_settings_restoration_remains_a_cleanup_failure():
    session = ExtensionSession({"uuid": "example@host", "schema": "org.gnome.shell.extensions.example"})
    session._saved_settings = {"visible": "true"}
    session.command = Mock(side_effect=AssertionError("schema unavailable"))
    with pytest.raises(AssertionError, match="cleanup failed.*",):
        session.cleanup()
    assert session._saved_settings == {"visible": "true"}


def test_enabled_state_matching_does_not_accept_a_different_uuid():
    session = ExtensionSession({"uuid": "example@host", "schema": "org.gnome.shell.extensions.example"})
    session.command = Mock(return_value=subprocess.CompletedProcess([], 0, "prefix-example@host\nexample@host-suffix\n", ""))
    assert session.is_enabled() is False


@pytest.mark.parametrize("active_state", ["ACTIVE", "ENABLED"])
def test_enabled_flag_waits_for_actual_activation(monkeypatch, active_state):
    session = ExtensionSession({"uuid": "example@host", "schema": "org.gnome.shell.extensions.example"})
    session.command = Mock(side_effect=[
        subprocess.CompletedProcess([], 0, "", ""),
        subprocess.CompletedProcess([], 0, "example@host\n", ""),
        subprocess.CompletedProcess([], 0, "State: ACTIVATING\n", ""),
        subprocess.CompletedProcess([], 0, f"State: {active_state}\n", ""),
    ])
    monkeypatch.setattr("tests.shared.extension_session.time.sleep", lambda seconds: None)
    assert session.enable() == active_state


@pytest.mark.parametrize("state", ["ERROR", "OUT OF DATE"])
def test_terminal_activation_errors_fail_immediately(state):
    session = ExtensionSession({"uuid": "example@host", "schema": "org.gnome.shell.extensions.example"})
    session.command = Mock(side_effect=[
        subprocess.CompletedProcess([], 0, "", ""),
        subprocess.CompletedProcess([], 0, "example@host\n", ""),
        subprocess.CompletedProcess([], 0, f"State: {state}\n", ""),
    ])
    with pytest.raises(AssertionError, match="cannot activate"):
        session.enable()


@pytest.mark.parametrize(("expression", "expected"), [
    ("true", True),
    ("false", False),
    ('"true"', "true"),
    ('[true, false, 45, "THỊ TRƯỜNG TÀI CHÍNH"]', [True, False, 45, "THỊ TRƯỜNG TÀI CHÍNH"]),
    ('({visible: false, rows: ["BTC-USD", "^GSPC"]})', {"visible": False, "rows": ["BTC-USD", "^GSPC"]}),
])
def test_shell_eval_returns_typed_rendered_state(tmp_path, monkeypatch, expression, expected):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Eval serialization boundary test needs a JavaScript runtime (node)")
    # Execute real JS with Shell's EvalAsync serialization contract, without
    # connecting to or mutating the maintainer's GNOME session.
    bridge = tmp_path / "gdbus"
    bridge.write_text(
        f"#!{node}\n"
        "global.context = {unsafe_mode: true};\n"
        "const payload = JSON.stringify(eval(process.argv.at(-1)));\n"
        "process.stdout.write('(true, ' + JSON.stringify(payload ?? '') + ')');\n",
        encoding="utf-8",
    )
    bridge.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    session = ExtensionSession({"uuid": "example@host", "schema": "org.gnome.shell.extensions.example"})

    actual = session.shell_json(expression)

    assert type(actual) is type(expected)
    assert actual == expected


@pytest.mark.parametrize("probe", [False, "true", 1, None])
def test_installed_candidate_rejects_a_non_boolean_shell_prerequisite(tmp_path, probe):
    profile = {"uuid": "example@host", "schema": "org.gnome.shell.extensions.example"}
    (tmp_path / "metadata.json").write_text(json.dumps({
        "uuid": profile["uuid"], "settings-schema": profile["schema"],
    }), encoding="utf-8")
    session = ExtensionSession(profile)
    session.command = Mock(side_effect=[
        subprocess.CompletedProcess([], 0, f"Path: {tmp_path}\n", ""),
        subprocess.CompletedProcess([], 0, "", ""),
    ])
    session.shell_json = Mock(return_value=probe)

    with pytest.raises(AssertionError, match="boolean true"):
        session.ensure_installed()


PROFILE = {"uuid": "example@host", "schema": "org.gnome.shell.extensions.example"}


def _done(stdout="", returncode=0, stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class _FakeClock:
    """Deterministic monotonic clock: each sleep() advances time by its argument."""

    def __init__(self):
        self.now = 0.0
        self.sleeps = 0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps += 1
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    fake = _FakeClock()
    monkeypatch.setattr("tests.shared.extension_session.time", fake)
    return fake


def test_load_collection_reads_the_checked_in_extension_profiles(tmp_path):
    from tests.shared.extension_session import COLLECTION_PATH, load_collection

    assert isinstance(load_collection(), dict)
    assert load_collection(COLLECTION_PATH) == json.loads(COLLECTION_PATH.read_text(encoding="utf-8"))
    custom = tmp_path / "collection.json"
    custom.write_text('{"extensions": ["THỊ TRƯỜNG"]}', encoding="utf-8")
    assert load_collection(custom) == {"extensions": ["THỊ TRƯỜNG"]}


def test_command_forces_c_utf8_locale_and_leaves_schema_dir_alone_before_install(monkeypatch):
    monkeypatch.setenv("GSETTINGS_SCHEMA_DIR", "/host/schemas")
    run = Mock(return_value=_done("ok"))
    monkeypatch.setattr("tests.shared.extension_session.subprocess.run", run)
    session = ExtensionSession(PROFILE)

    assert session.command(["gsettings", "list-schemas"], timeout=7).stdout == "ok"

    argv, kwargs = run.call_args.args[0], run.call_args.kwargs
    assert argv == ["gsettings", "list-schemas"]
    assert kwargs["capture_output"] is True and kwargs["text"] is True
    assert kwargs["timeout"] == 7
    assert kwargs["env"]["LC_ALL"] == "C.UTF-8"
    assert kwargs["env"]["GSETTINGS_SCHEMA_DIR"] == "/host/schemas"


def test_command_points_gsettings_at_the_installed_candidate_schemas(monkeypatch, tmp_path):
    run = Mock(return_value=_done())
    monkeypatch.setattr("tests.shared.extension_session.subprocess.run", run)
    session = ExtensionSession(PROFILE)
    session.package_path = tmp_path

    session.command(["gsettings", "get", PROFILE["schema"], "visible"])

    assert run.call_args.kwargs["env"]["GSETTINGS_SCHEMA_DIR"] == str(tmp_path / "schemas")
    assert run.call_args.kwargs["timeout"] == 30


def test_command_failure_reports_exit_code_argv_and_stderr(monkeypatch):
    monkeypatch.setattr(
        "tests.shared.extension_session.subprocess.run",
        Mock(return_value=_done(returncode=3, stderr="No such schema")),
    )
    session = ExtensionSession(PROFILE)

    with pytest.raises(AssertionError, match=r"Guest command failed \(3\).*'gsettings'.*\nNo such schema"):
        session.command(["gsettings", "get", "missing", "key"])


def test_unchecked_command_returns_the_failed_result(monkeypatch):
    failed = _done(returncode=1, stderr="not enabled")
    monkeypatch.setattr("tests.shared.extension_session.subprocess.run", Mock(return_value=failed))

    assert ExtensionSession(PROFILE).command(["false"], check=False) is failed


def test_wait_for_polls_until_the_rendered_state_matches(clock):
    session = ExtensionSession(PROFILE)
    session.shell_json = Mock(side_effect=[False, False, True])

    assert session.wait_for("panel.visible") is True
    assert session.shell_json.call_count == 3
    assert clock.sleeps == 2


def test_wait_for_compares_against_the_expected_value_not_truthiness(clock):
    session = ExtensionSession(PROFILE)
    session.shell_json = Mock(side_effect=[1, "3", 3])

    assert session.wait_for("rows.length", expected=3) == 3


def test_wait_for_timeout_reports_expression_expected_and_last_value(clock):
    session = ExtensionSession(PROFILE)
    session.shell_json = Mock(return_value="BTC-USD")

    with pytest.raises(AssertionError, match=r"not reached: label\.text; expected '\^GSPC', got 'BTC-USD'"):
        session.wait_for("label.text", expected="^GSPC", timeout=1)
    assert clock.now >= 1


def _write_metadata(path, **overrides):
    metadata = {"uuid": PROFILE["uuid"], "settings-schema": PROFILE["schema"], **overrides}
    (path / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")


@pytest.mark.parametrize("overrides", [
    {"uuid": "other@host"},
    {"settings-schema": "org.gnome.shell.extensions.other"},
])
def test_installed_candidate_with_a_different_identity_is_rejected(tmp_path, overrides):
    _write_metadata(tmp_path, **overrides)
    session = ExtensionSession(PROFILE)
    session.command = Mock(return_value=_done(f"Path: {tmp_path}\n"))
    session.shell_json = Mock(return_value=True)

    with pytest.raises(AssertionError, match="identity does not match"):
        session.ensure_installed()
    session.command.assert_called_once_with(["gnome-extensions", "info", PROFILE["uuid"]])
    session.shell_json.assert_not_called()
    assert session._original_enabled is None


@pytest.mark.parametrize(("enabled_list", "original"), [
    ("example@host\n", True),
    ("other@host\n", False),
])
def test_installed_candidate_records_the_pre_test_enabled_state(tmp_path, enabled_list, original):
    _write_metadata(tmp_path)
    session = ExtensionSession(PROFILE)
    session.command = Mock(side_effect=[_done(f"Path: {tmp_path}\n"), _done(enabled_list)])
    session.shell_json = Mock(return_value=True)

    session.ensure_installed()

    assert session.package_path == tmp_path
    assert session._original_enabled is original
    session.shell_json.assert_called_once_with("true")


def test_disable_waits_until_the_extension_leaves_the_enabled_list(clock):
    session = ExtensionSession(PROFILE)
    session.command = Mock(side_effect=[_done(), _done("example@host\n"), _done("")])

    session.disable()

    assert session.command.call_args_list[0].args[0] == ["gnome-extensions", "disable", PROFILE["uuid"]]
    assert clock.sleeps == 1


def test_disable_times_out_when_the_extension_stays_enabled(clock):
    session = ExtensionSession(PROFILE)
    session.command = Mock(return_value=_done("example@host\n"))

    with pytest.raises(AssertionError, match="example@host did not become disabled"):
        session.disable()
    assert clock.now >= 10


def test_enable_times_out_when_the_extension_is_never_listed_as_enabled(clock):
    session = ExtensionSession(PROFILE)
    session.command = Mock(return_value=_done(""))

    with pytest.raises(AssertionError, match="example@host did not become enabled"):
        session.enable()


def test_enabled_extension_that_never_activates_fails_with_its_last_info(clock):
    session = ExtensionSession(PROFILE)

    def guest(argv, **kwargs):
        if argv[:2] == ["gnome-extensions", "list"]:
            return _done("example@host\n")
        if argv[:2] == ["gnome-extensions", "info"]:
            return _done("State: INITIALIZED\n")
        return _done()

    session.command = Mock(side_effect=guest)

    with pytest.raises(AssertionError, match="enabled but not active: State: INITIALIZED"):
        session.enable()


def test_set_setting_saves_only_the_pre_test_value_once():
    session = ExtensionSession(PROFILE)
    session.command = Mock(side_effect=[_done("true\n"), _done(), _done()])

    session.set_setting("visible", "false")
    session.set_setting("visible", "true")

    assert session._saved_settings == {"visible": "true"}
    assert [c.args[0] for c in session.command.call_args_list] == [
        ["gsettings", "get", PROFILE["schema"], "visible"],
        ["gsettings", "set", PROFILE["schema"], "visible", "false"],
        ["gsettings", "set", PROFILE["schema"], "visible", "true"],
    ]


@pytest.mark.parametrize(("original", "restore"), [(True, "enable"), (False, "disable")])
def test_cleanup_restores_settings_then_the_pre_test_enabled_state(original, restore):
    session = ExtensionSession(PROFILE)
    session._saved_settings = {"visible": "true", "symbols": "['BTC-USD']"}
    session._original_enabled = original
    calls = []
    session.command = Mock(side_effect=lambda argv, **kw: calls.append(argv) or _done())
    session.enable = Mock(side_effect=lambda: calls.append("enable"))
    session.disable = Mock(side_effect=lambda: calls.append("disable"))

    session.cleanup()

    assert calls == [
        ["gsettings", "set", PROFILE["schema"], "visible", "true"],
        ["gsettings", "set", PROFILE["schema"], "symbols", "['BTC-USD']"],
        restore,
    ]
    assert session._saved_settings == {}


def test_cleanup_without_a_recorded_state_does_not_toggle_the_extension():
    session = ExtensionSession(PROFILE)
    session.command = Mock()
    session.enable = Mock()
    session.disable = Mock()

    session.cleanup()

    session.command.assert_not_called()
    session.enable.assert_not_called()
    session.disable.assert_not_called()


def test_cleanup_keeps_going_and_reports_every_failure():
    session = ExtensionSession(PROFILE)
    session._saved_settings = {"visible": "true", "symbols": "['^GSPC']"}
    session._original_enabled = False
    session.command = Mock(side_effect=[
        subprocess.TimeoutExpired(["gsettings"], 30),
        _done(),
    ])
    session.disable = Mock(side_effect=AssertionError("Extension example@host did not become disabled"))

    with pytest.raises(AssertionError) as raised:
        session.cleanup()

    message = str(raised.value)
    assert message.startswith("Extension cleanup failed:\n")
    assert "timed out after 30 seconds" in message
    assert "did not become disabled" in message
    assert session.command.call_count == 2
    session.disable.assert_called_once_with()
    assert session._saved_settings == {"visible": "true", "symbols": "['^GSPC']"}
