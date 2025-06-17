import click


def heading(s: str) -> None:
    """Print a heading to the console."""
    click.secho(s, bold=True, fg="green")


def subheading(s: str) -> None:
    """Print a subheading to the console."""
    click.secho(s, fg="green")


def subsubheading(s: str) -> None:
    """Print a sub-subheading to the console."""
    click.secho(s, fg="blue")


def error(s: str) -> None:
    """Print an error to the console."""
    click.secho(s, bold=True, fg="red")


def warn(s: str) -> None:
    """Print a warning to the console."""
    click.secho(s, bold=True, fg="yellow")


def info(s: str) -> None:
    """Print info to the console."""
    click.secho(s, dim=True)
