from pathlib import Path

import click

from kb_engine.config import Config

from kb_engine.commands.core import (
    eval_cmd,
    log_event,
    rebuild,
    search,
    status,
    sync,
)
from kb_engine.commands.ingest import (
    backfill_content_cmd,
    file_cmd,
    import_mail_cmd,
    import_things,
    inbox_check,
)
from kb_engine.commands.reports import (
    dedup_report,
    digest,
    doctor,
    related,
    synthesis_candidates_cmd,
)
from kb_engine.commands.run import pipeline
from kb_engine.commands.topics_cmds import topics

# Re-exported so tests reaching through the CLI module keep working
# (`from kb_engine import cli; cli._default_things_db(...)`).
from kb_engine.commands.ingest import _default_things_db  # noqa: F401


@click.group()
@click.option(
    "--vault",
    "vault",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Path to the Obsidian vault root.",
)
@click.option(
    "--db",
    "db",
    default=None,
    type=click.Path(dir_okay=False, path_type=Path),
    help="SQLite cache path (defaults to ~/.local/state/kb-engine/kb-engine.db).",
)
@click.pass_context
def main(ctx: click.Context, vault: Path, db: Path | None) -> None:
    """kb-engine — local embedding + hybrid search for an Obsidian KB."""
    ctx.obj = Config(vault_path=vault, db_path=db)


main.add_command(sync)
main.add_command(search)
main.add_command(log_event)
main.add_command(eval_cmd)
main.add_command(synthesis_candidates_cmd)
main.add_command(dedup_report)
main.add_command(related)
main.add_command(status)
main.add_command(doctor)
main.add_command(inbox_check)
main.add_command(rebuild)
main.add_command(topics)
main.add_command(import_mail_cmd)
main.add_command(backfill_content_cmd)
main.add_command(import_things)
main.add_command(digest)
main.add_command(pipeline)
main.add_command(file_cmd)


if __name__ == "__main__":
    main()
