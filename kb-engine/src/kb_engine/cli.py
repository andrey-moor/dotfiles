import click


@click.group()
def main() -> None:
    """kb-engine — local embedding + hybrid search for an Obsidian KB."""


if __name__ == "__main__":
    main()
