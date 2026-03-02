"""Tests for praxis.watchdog — failure monitoring and threshold logic."""

import time

from praxis import watchdog

# --- _redact_secrets() ---


class TestRedactSecrets:
    def test_long_tokens_redacted(self):
        text = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9abcdefghij"
        result = watchdog._redact_secrets(text)
        assert "<REDACTED>" in result
        assert "eyJhbG" not in result

    def test_env_var_passwords_redacted(self):
        text = "PASSWORD=hunter2 SECRET=abc123 TOKEN=mytoken"
        result = watchdog._redact_secrets(text)
        assert "hunter2" not in result
        assert "abc123" not in result
        assert "mytoken" not in result

    def test_short_normal_text_unchanged(self):
        text = "Error: connection refused"
        assert watchdog._redact_secrets(text) == text


# --- _hash_output() ---


class TestHashOutput:
    def test_deterministic(self):
        h1 = watchdog._hash_output("stdout", "stderr", 1)
        h2 = watchdog._hash_output("stdout", "stderr", 1)
        assert h1 == h2

    def test_different_exit_codes_differ(self):
        h1 = watchdog._hash_output("output", "err", 1)
        h2 = watchdog._hash_output("output", "err", 2)
        assert h1 != h2

    def test_returns_12_char_hex(self):
        h = watchdog._hash_output("out", "err", 1)
        assert len(h) == 12
        int(h, 16)  # raises ValueError if not hex

    def test_only_last_20_lines_matter(self):
        prefix_a = "\n".join(f"line-a-{i}" for i in range(50))
        prefix_b = "\n".join(f"line-b-{i}" for i in range(50))
        tail = "\n".join(f"tail-{i}" for i in range(20))
        h1 = watchdog._hash_output(prefix_a + "\n" + tail, "", 1)
        h2 = watchdog._hash_output(prefix_b + "\n" + tail, "", 1)
        assert h1 == h2


# --- _load_state / _save_state ---


class TestStateRoundTrip:
    def test_missing_file_returns_default(self, tmp_path, monkeypatch):
        monkeypatch.setattr(watchdog, "STATE_FILE", tmp_path / "nonexistent.json")
        state = watchdog._load_state()
        assert state == {"history": [], "reported": {}}

    def test_save_then_load(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(watchdog, "STATE_FILE", state_file)
        state = {
            "history": [
                {
                    "timestamp": 1000.0,
                    "signature": "abc123def456",
                    "command": "make test",
                    "project": "praxis",
                    "exit_code": 1,
                }
            ],
            "reported": {"abc123def456": 1000.0},
        }
        watchdog._save_state(state)
        loaded = watchdog._load_state()
        assert loaded == state

    def test_corrupt_json_returns_default(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        state_file.write_text("{corrupt json!!!")
        monkeypatch.setattr(watchdog, "STATE_FILE", state_file)
        state = watchdog._load_state()
        assert state == {"history": [], "reported": {}}

    def test_creates_parent_dirs(self, tmp_path, monkeypatch):
        state_file = tmp_path / "deep" / "nested" / "state.json"
        monkeypatch.setattr(watchdog, "STATE_FILE", state_file)
        watchdog._save_state({"history": [], "reported": {}})
        assert state_file.exists()


# --- _handle_failure() ---


class TestHandleFailure:
    def _make_result(self, stdout="fail", stderr="err", returncode=1):
        """Create a fake CompletedProcess."""
        import subprocess

        return subprocess.CompletedProcess(
            args=["test"], returncode=returncode, stdout=stdout, stderr=stderr
        )

    def test_below_threshold_no_report(self, tmp_path, monkeypatch):
        monkeypatch.setattr(watchdog, "STATE_FILE", tmp_path / "state.json")
        reports = []
        monkeypatch.setattr(
            watchdog, "_report_to_lore", lambda *a, **kw: reports.append(1)
        )
        result = self._make_result()
        # threshold=3, only 1 failure
        watchdog._handle_failure("make test", "praxis", result, 600, 3)
        assert len(reports) == 0

    def test_at_threshold_reports(self, tmp_path, monkeypatch):
        monkeypatch.setattr(watchdog, "STATE_FILE", tmp_path / "state.json")
        reports = []
        monkeypatch.setattr(
            watchdog, "_report_to_lore", lambda *a, **kw: reports.append(1)
        )
        result = self._make_result()
        # Call 3 times with same output to hit threshold
        for _ in range(3):
            watchdog._handle_failure("make test", "praxis", result, 600, 3)
        assert len(reports) == 1

    def test_different_signatures_independent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(watchdog, "STATE_FILE", tmp_path / "state.json")
        reports = []
        monkeypatch.setattr(
            watchdog, "_report_to_lore", lambda *a, **kw: reports.append(1)
        )
        result_a = self._make_result(stdout="error A")
        result_b = self._make_result(stdout="error B")
        # Interleave two different failures, neither hits threshold=3
        watchdog._handle_failure("make test", "praxis", result_a, 600, 3)
        watchdog._handle_failure("make test", "praxis", result_b, 600, 3)
        watchdog._handle_failure("make test", "praxis", result_a, 600, 3)
        assert len(reports) == 0

    def test_same_signature_within_window_no_re_report(self, tmp_path, monkeypatch):
        monkeypatch.setattr(watchdog, "STATE_FILE", tmp_path / "state.json")
        reports = []
        monkeypatch.setattr(
            watchdog, "_report_to_lore", lambda *a, **kw: reports.append(1)
        )
        result = self._make_result()
        # Hit threshold
        for _ in range(3):
            watchdog._handle_failure("make test", "praxis", result, 600, 3)
        assert len(reports) == 1
        # Additional failures within window don't re-report
        watchdog._handle_failure("make test", "praxis", result, 600, 3)
        assert len(reports) == 1

    def test_old_history_pruned(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(watchdog, "STATE_FILE", state_file)
        reports = []
        monkeypatch.setattr(
            watchdog, "_report_to_lore", lambda *a, **kw: reports.append(1)
        )
        # Seed state with old entries outside the window
        old_time = time.time() - 1000  # well outside 600s window
        state = {
            "history": [
                {
                    "timestamp": old_time,
                    "signature": "oldsig12345a",
                    "command": "make test",
                    "project": "praxis",
                    "exit_code": 1,
                }
                for _ in range(5)
            ],
            "reported": {},
        }
        watchdog._save_state(state)
        # New failure with different sig — old entries should be pruned
        result = self._make_result(stdout="new error")
        watchdog._handle_failure("make test", "praxis", result, 600, 3)
        loaded = watchdog._load_state()
        # Old entries pruned, only the new one remains
        assert len(loaded["history"]) == 1


# --- report_status() ---


class TestReportStatus:
    def test_empty_state(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(watchdog, "STATE_FILE", tmp_path / "state.json")
        watchdog.report_status()
        out = capsys.readouterr().out
        assert "No recent failures" in out

    def test_state_with_history(self, tmp_path, monkeypatch, capsys):
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(watchdog, "STATE_FILE", state_file)
        state = {
            "history": [
                {
                    "timestamp": time.time(),
                    "signature": "abc123def456",
                    "command": "make test",
                    "project": "praxis",
                    "exit_code": 1,
                },
                {
                    "timestamp": time.time(),
                    "signature": "abc123def456",
                    "command": "make test",
                    "project": "praxis",
                    "exit_code": 1,
                },
            ],
            "reported": {"abc123def456": time.time()},
        }
        watchdog._save_state(state)
        watchdog.report_status()
        out = capsys.readouterr().out
        assert "abc123def456" in out
        assert "REPORTED" in out
        assert "Failures:  2" in out
