import datetime
import uuid
from enum import StrEnum
from pathlib import Path
from typing import MutableSequence, Sequence

from ebooklib import epub
from markdown_it import MarkdownIt

from ebooklib_patch import SWEpubCoverHtml
from renderers import render_poem_for_ebook, render_story_for_ebook

_md = MarkdownIt("commonmark", {"typographer": True})
_md.enable(["replacements", "smartquotes"])


class PieceType(StrEnum):
    Original = "Original"
    Poem = "Poem"
    Reprint = "Reprint"


magazine_subjects = [
    "magazine",
    "science fiction",
    "fantasy",
    "science fiction magazine",
    "Science Fiction - Short Stories",
    "Science Fiction - Poetry",
    "Science Fiction &amp; Fantasy",
    "short fiction",
    "short stories",
    "poetry",
]


def add_metadata(
    book: epub.EpubBook,
    title: str,
    editors: list[str],
    author_names: list[str],
    description: str,
    issue_num: int | None = None,
) -> None:
    """Add metadata to an ebook.

    :param book: Book to add metadata to.
    :param title: Ebook title.
    :param editors: List of editors.
    :param author_names: List of author names.
    :param description: Description of the ebook.
    :param issue_num: Optional number of the issue (if the ebook is a single magazine issue).
    """

    book.set_identifier(str(uuid.uuid4()))
    book.set_title(title)
    book.set_language("en")
    book.add_metadata("DC", "publisher", "Small Wonders LLC")
    for editor in editors:
        book.add_metadata("DC", "creator", editor)
    for author in author_names:
        book.add_metadata("DC", "contributor", author)
    book.add_metadata("DC", "date", datetime.date.today().isoformat())
    book.add_metadata("DC", "description", description)
    for subject in magazine_subjects:
        book.add_metadata("DC", "subject", subject)
    book.add_metadata(
        None, "meta", "", {"name": "calibre:series", "content": "Small Wonders"}
    )
    if issue_num is not None:
        book.add_metadata(
            None,
            "meta",
            "",
            {"name": "calibre:series_index", "content": str(issue_num)},
        )


def add_stylesheet(book: epub.EpubBook, stylesheet_path: Path) -> epub.EpubItem:
    """Create and add epub stylesheet to an ebook.

    :param book: Book to add stylesheet to.
    :param stylesheet_path: Path to the stylesheet.
    :return: Stylesheet item.
    """
    css = epub.EpubItem(
        uid="base_stylesheet",
        file_name="styles/stylesheet.css",
        media_type="text/css",
        content=stylesheet_path.read_bytes(),
    )
    book.add_item(css)
    return css


def add_cover(
    book: epub.EpubBook,
    cover_path: Path,
    title: str = "Cover",
) -> SWEpubCoverHtml:
    """Create and add cover to an ebook.

    Adds both the cover image and an HTML page containing that cover.

    :param book: Book to add cover to.
    :param cover_path: Path to the cover image file.
    :param title: Title to give the page containing the cover in the ebook.
    :return: Created cover page.
    """

    content = cover_path.read_bytes()

    book.set_cover(cover_path.name, content, create_page=False)
    c1 = SWEpubCoverHtml(
        title=title, file_name="cover.xhtml", image_name=cover_path.name
    )
    c1.set_content(cover_path)
    book.add_item(c1)

    return c1


def create_front_matter(
    paths: Sequence[Path],
    titles: Sequence[str],
    ebook_chs: MutableSequence[epub.EpubItem],
):
    """Create ebook front matter.

    Front matter is created and added in-place to ebook_chs.

    :param paths: List of paths to the front matter content (as markdown files).
    :param titles: List of titles for each front matter.
    :param ebook_chs: List of previously-added items.
    """
    for path, title in zip(paths, titles):
        ch = epub.EpubHtml(
            title=title, file_name=f"body{len(ebook_chs):02}.xhtml", lang="en"
        )
        ch.set_content(
            '<div class="frontmatter">'
            + _md.render(path.read_text(encoding="utf-8"))
            + "</div>"
        )
        ebook_chs.append(ch)


def create_piece_content(
    piece_path: Path,
    piece_type: PieceType,
    author_name: str,
    copyright_year: int,
    piece_preamble: str | None = None,
) -> str:
    """Create the HTML for a piece (original flash fiction, poem, or reprint flash fiction).

    :param piece_path: Path to the piece in Markdown format,
    :param piece_type: Type of piece.
    :param author_name: Author's name.
    :param copyright_year: Year in which the story was copyrighted. (Ignored for reprint flash.)
    :param piece_preamble: Optional HTML preamble to the story to go inside the piece div and above the title.
    :return: The HTML content.
    """
    content = '<div class="piece">\n'

    if piece_preamble:
        content += piece_preamble

    if piece_type == PieceType.Poem:
        content += render_poem_for_ebook(piece_path)
    else:
        content += render_story_for_ebook(piece_path)

    if piece_type != PieceType.Reprint:
        # Add the end div and copyright statement
        content += f'</div>\n\n<div class="endmatter">\n<p>Copyright © {copyright_year} by {author_name}</p>\n</div>\n\n'
    else:
        # Add the end div before the already-given copyright statement
        ndx = content.find("<p>Copyright ©")
        if ndx == -1:
            print(f"Warning: Couldn't find copyright statement in {piece_path}")
        else:
            content = (
                content[:ndx]
                + '</div>\n\n<div class="endmatter">\n'
                + content[ndx:]
                + "</div>\n\n"
            )

    return content


def add_piece(
    title: str,
    piece_content: str,
    author_name: str,
    author_avi_ebook_path: str,
    bio_path: Path,
    ebook_chs: MutableSequence[epub.EpubItem],
) -> None:
    """Add a piece's HTML to an ebook's list of chapters.

    :param title: Title of the piece.
    :param piece_content: HTML for the content.
    :param author_name: Author's name.
    :param author_avi_ebook_path: Path to the avatar in the ebook.
    :param bio_path: Path to the author's bio.
    :param ebook_chs: List of previously-added items.
    """
    content = (
        piece_content
        + f'<p class="author-pic"><img class="author" '
        + f'src="{author_avi_ebook_path}" alt="{author_name}"/></p>\n\n'
        + _md.render(bio_path.read_text(encoding="utf-8"))
    )
    ch = epub.EpubHtml(
        title=title, file_name=f"body{len(ebook_chs):02}.xhtml", lang="en"
    )
    ch.set_content(content)
    ebook_chs.append(ch)
