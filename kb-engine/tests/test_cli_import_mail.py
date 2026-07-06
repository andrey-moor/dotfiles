from click.testing import CliRunner

import kb_engine.cli as cli
import kb_engine.importing.mail_notes as mail_notes
from kb_engine.importing.mail import MailMessage


def test_import_mail_wires_fetch_to_writer(tmp_path, monkeypatch):
    monkeypatch.setenv("FASTMAIL_API_TOKEN", "tok")
    # connect/fetch_labeled now resolve inside the shared run_import_mail helper.
    monkeypatch.setattr(mail_notes, "connect", lambda token: ("acct", None))
    monkeypatch.setattr(mail_notes, "fetch_labeled", lambda call, acct, label, limit: [
        MailMessage("m@x", "Hi", "a@b.com", None, "2026-07-01T00:00:00Z", "body", None)])
    result = CliRunner().invoke(cli.main, ["--vault", str(tmp_path), "import-mail", "--json"])
    assert result.exit_code == 0, result.output
    assert '"written": 1' in result.output
    assert (tmp_path / "Knowledge" / "inbox").exists()


def test_import_mail_requires_token(tmp_path, monkeypatch):
    monkeypatch.delenv("FASTMAIL_API_TOKEN", raising=False)
    result = CliRunner().invoke(cli.main, ["--vault", str(tmp_path), "import-mail"])
    assert result.exit_code != 0 and "FASTMAIL_API_TOKEN" in result.output
