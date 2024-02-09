import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

from markdown_it import MarkdownIt


@dataclass
class IssueInfo:
    """Information about an issue and its associated files"""

    issue_num: int
    cover_path: Path
    description: str
    editors: list[str]

    piece_paths: list[Path]
    titles: list[str]
    bio_paths: list[Path]
    author_names: list[str]


def get_issue_num(about_path: Path) -> int:
    """Get the current issue number.

    The issue number is extracted from the first instance of "Issue <###>" in the file.

    :param about_path: Path to the "about the issue" file.
    :raises RuntimeError: If the issue number isn't found.
    :return: The issue number.
    """
    m = re.search("Issue +(\d+)", about_path.read_text())
    if m is None:
        raise RuntimeError(f"Couldn't find issue number in {about_path}")
    return int(m.group(1))


def get_editors(editors_path: Path) -> Sequence[str]:
    """Get the editors from the file containing the list of editors.

    :param editors_path: Path to the text file with the editors' names, one on a line.
    :return: List of the editors' names.
    """
    return [e.strip() for e in editors_path.read_text().splitlines()]


def get_titles_and_authors(
    piece_paths: Iterable[Path],
) -> Sequence[Sequence[str], Sequence[str]]:
    """Get the titles and authors from the files containing the pieces.

    The first level one heading ("# Heading") is assumed to be the title.
    The first level two heading ("## Mx. Author") is assumed to be the author. If it
    starts with "By " or "by ", that's removed.

    :param piece_paths: List of paths to the Markdown files containing the pieces.
    :raises RuntimeError: If any files lack a title or an author.
    :return: A tuple containing the list of titles and the list of authors.
    """
    md = MarkdownIt("commonmark", {"typographer": True})
    md.enable(["replacements", "smartquotes"])

    titles = []
    authors = []
    errs = []
    for fp in piece_paths:
        content = md.parse(fp.read_text(encoding="utf-8"))
        title = None
        author = None
        for cur_token, next_token in pairwise(content):
            if cur_token.markup == "#" and title is None:
                title = next_token.content
            elif cur_token.markup == "##" and author is None:
                author = re.sub(r"[Bb]y +", "", next_token.content)
            if title is not None and author is not None:
                break
        file_errs = []
        if title is None:
            file_errs.append("No title found. Are you missing a # Markdown heading?")
        if author is None:
            file_errs.append("No author found. Are you missing a ## Markdown heading?")
        if file_errs:
            err_desc = " ".join(file_errs)
            errs.append(f"{fp}: {err_desc}")
        else:
            titles.append(title)
            authors.append(author)

    if errs:
        raise RuntimeError("Issues finding titles/authors.\n  " + "\n  ".join(errs))

    return titles, authors


def get_issue_info(content_path: Path) -> IssueInfo:
    """Get all the needed information about an issue.

    :param content_path: Path to where all the content files live.
    :return: Issue information.
    """
    content_types = ("story", "poem", "reprint")
    piece_filenames = [f"{idx+1}a-{content_types[idx % 3]}.md" for idx in range(0, 9)]

    issue_num = get_issue_num(content_path / "0a-about.md")
    cover_path = content_path / "cover.jpg"
    description = (content_path / "description.html").read_text(encoding="utf-8")
    editors = get_editors(content_path / "editors.txt")

    piece_paths = [content_path / fn for fn in piece_filenames]
    bio_paths = [content_path / f"{idx+1}b-author.md" for idx in range(0, 9)]
    titles, authors = get_titles_and_authors(piece_paths)

    return IssueInfo(
        issue_num=issue_num,
        cover_path=cover_path,
        description=description,
        editors=editors,
        piece_paths=piece_paths,
        titles=titles,
        bio_paths=bio_paths,
        author_names=authors,
    )
