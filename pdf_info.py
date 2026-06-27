import datetime
from pathlib import Path

import weasyprint
from markdown_it import MarkdownIt

from ebook_info import PieceType
from issue_info import IssueInfo
from renderers import render_poem_for_epub, render_story_for_epub, render_title_for_epub

_md = MarkdownIt("commonmark", {"typographer": True})
_md.enable(["replacements", "smartquotes"])

_FRONT_MATTER_FILES = ["0a-about.md", "0b-cover-artist.md", "0c-keyhole.md"]


def create_head() -> str:
    """Render the opening <html><head> of the PDF document."""
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8"/>\n'
        '<link rel="stylesheet" href="pdf_stylesheet.css"/>\n'
        "</head>\n"
        "<body>\n"
    )


def create_cover_section(cover_path: Path) -> str:
    """Render a full-page cover section.

    :param cover_path: Path to the cover image, relative to the document base URL.
    """
    src = cover_path.as_posix()
    return f'<section id="cover">\n<img src="{src}" alt="Cover"/>\n</section>\n'


def create_toc_entry(n: int, title: str, author: str) -> str:
    """Render a single ToC entry linking to piece-{n}.

    :param n: 1-based piece number.
    :param title: Piece title.
    :param author: Author name.
    """
    return f'<p class="toc-entry"><a href="#piece-{n}">{render_title_for_epub(title)} \u2014 {author}</a></p>\n'


def create_toc_section(titles: list[str], author_names: list[str]) -> str:
    """Render the table of contents section.

    Page numbers are filled in at PDF-render time via the CSS target-counter() rule.

    :param titles: List of piece titles.
    :param author_names: List of author names, in the same order as titles.
    """
    entries = "".join(
        create_toc_entry(n + 1, title, author)
        for n, (title, author) in enumerate(zip(titles, author_names))
    )
    return '<section id="toc">\n<div class="toc">\n' + entries + "</div>\n</section>\n"


def create_front_matter_section(n: int, path: Path) -> str:
    """Render a front-matter section (About, Cover Artist, Editorial).

    :param n: 1-based front-matter index (used for the section id).
    :param path: Path to the front-matter Markdown file.
    """
    html = _md.render(path.read_text(encoding="utf-8"))
    return (
        f'<section id="front-{n}">\n'
        '<div class="frontmatter">\n' + html + "</div>\n</section>\n"
    )


def create_piece_section(
    n: int,
    piece_path: Path,
    piece_type: PieceType,
    author_name: str,
    copyright_year: int,
    author_avi_path: Path,
    bio_path: Path,
) -> str:
    """Render a piece section containing the piece, endmatter, avatar, and bio.

    :param n: 1-based piece number (used for the section id).
    :param piece_path: Path to the piece Markdown file.
    :param piece_type: Whether the piece is an original story, poem, or reprint.
    :param author_name: Author's name.
    :param copyright_year: Copyright year (used for originals; ignored for reprints, which carry
        their own copyright line in the source file).
    :param author_avi_path: Path to the author avatar image, relative to the document base URL.
    :param bio_path: Path to the author bio Markdown file.
    """
    if piece_type == PieceType.Poem:
        piece_html = render_poem_for_epub(piece_path)
    else:
        piece_html = render_story_for_epub(piece_path)

    content = '<div class="piece">\n' + piece_html

    if piece_type != PieceType.Reprint:
        # Add the end div and copyright statement
        content += (
            f'</div>\n\n<div class="endmatter">\n'
            f"<p>Copyright \u00a9 {copyright_year} by {author_name}</p>\n"
            f"</div>\n\n"
        )
    else:
        # Add the end div before the already-given copyright statement
        ndx = content.find("<p>Copyright \u00a9")
        if ndx == -1:
            print(f"Warning: Couldn't find copyright statement in {piece_path}")
            content += "</div>\n\n"
        else:
            content = (
                content[:ndx]
                + '</div>\n\n<div class="endmatter">\n'
                + content[ndx:]
                + "</div>\n\n"
            )

    avi_src = author_avi_path.as_posix()
    bio_html = _md.render(bio_path.read_text(encoding="utf-8"))
    content += (
        f'<p class="author-pic">'
        f'<img class="author" src="{avi_src}" alt="{author_name}"/>'
        f"</p>\n\n" + bio_html
    )

    return f'<section id="piece-{n}">\n' + content + "</section>\n"


def write_pdf(info: IssueInfo, output_path: Path) -> None:
    """Assemble a complete HTML document from the issue info and render it to PDF.

    :param info: Information about the issue.
    :param output_path: Path where the output PDF will be written.
    """
    root_path = Path(__file__).parent
    content_path = root_path / "content"
    current_year = datetime.datetime.now().year

    parts: list[str] = [create_head()]

    cover_rel = info.cover_path.relative_to(root_path)
    parts.append(create_cover_section(cover_rel))

    parts.append(create_toc_section(info.titles, info.author_names))

    for n, fm_file in enumerate(_FRONT_MATTER_FILES):
        parts.append(create_front_matter_section(n + 1, content_path / fm_file))

    for n, (piece_path, _, _, bio_path, author, avatar_path) in enumerate(
        info.piece_info()
    ):
        piece_type = (
            PieceType.Poem
            if "poem" in str(piece_path)
            else (
                PieceType.Reprint
                if "reprint" in str(piece_path)
                else PieceType.Original
            )
        )
        avatar_rel = avatar_path.relative_to(root_path)
        parts.append(
            create_piece_section(
                n + 1,
                piece_path,
                piece_type,
                author,
                current_year,
                avatar_rel,
                bio_path,
            )
        )

    parts.append("</body>\n</html>\n")

    html = "".join(parts)
    # Make base_url end with "/" so relative paths (fonts/, content/) resolve from the repo root
    base_url = root_path.as_uri() + "/"
    weasyprint.HTML(string=html, base_url=base_url).write_pdf(output_path)
