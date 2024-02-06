import datetime
import re
import uuid
from collections.abc import MutableSequence, Sequence
from pathlib import Path

from ebooklib import epub
from markdown_it import MarkdownIt

from ebooklib_patch import SWEpubCoverHtml, write_epub
from issue_info import get_issue_info

md = MarkdownIt("commonmark", {"typographer": True})
md.enable(["replacements", "smartquotes"])


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


def add_cover(
    book: epub.EpubBook,
    cover_path: Path,
    title: str = "Cover",
) -> SWEpubCoverHtml:
    """Create and add cover to the ebook.

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


def add_metadata(
    book: epub.EpubBook,
    issue_num: int,
    editors: Sequence[str],
    authors: Sequence[str],
    desc: str,
) -> None:
    """Add metadata to the ebook.

    :param book: Book to add metadata to.
    :param issue_num: Current issue number.
    :param editors: List of editors' names.
    :param authors: List of authors' names.
    :param desc: Description for the ebook.
    """
    book.set_identifier(str(uuid.uuid4()))
    book.set_title(f"Small Wonders Issue {issue_num}")
    book.set_language("en")
    book.add_metadata("DC", "publisher", "Small Wonders LLC")
    for editor in editors:
        book.add_metadata("DC", "creator", editor)
    for author in authors:
        book.add_metadata("DC", "contributor", author)
    book.add_metadata("DC", "date", datetime.date.today().isoformat())
    book.add_metadata("DC", "description", desc)
    for subject in magazine_subjects:
        book.add_metadata("DC", "subject", subject)
    book.add_metadata(
        None, "meta", "", {"name": "calibre:series", "content": "Small Wonders"}
    )
    book.add_metadata(
        None, "meta", "", {"name": "calibre:series_index", "content": str(issue_num)}
    )


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
            + md.render(path.read_text(encoding="utf-8"))
            + "</div>"
        )
        ebook_chs.append(ch)


def _poem_line_to_html(line: str) -> str:
    """Wrap a poem's line in HTML.

    :param line: Line from the poem.
    :return: HTML-ized poem line
    """
    classes = "poem"
    if not line.strip():
        # Non-breaking space needed to force ereaders to honor blank lines
        md_line = "&nbsp;"
    else:
        if line.startswith("\t"):
            cnt = len(re.match("\t+", line).group(0))
            if cnt > 4:
                raise RuntimeError(f"Too many tabs {cnt} in line {line}")
            classes += f" tab{cnt}"
            line = line[cnt:]
        md_line = md.renderInline(line)

    return f'<div class="{classes}">{md_line}</div>\n'


def generate_poem(path: Path) -> str:
    """Generate the HTML for a poem.

    :param path: Path to the poem's markdown file.
    :return: HTML for the poem.
    """
    # Since poems need specialized formatting, we handle them on a line-by-line basis
    html = ""
    lines = path.read_text(encoding="utf-8").splitlines()
    in_content = False
    for line in lines:
        if not in_content:
            if not line.strip():
                continue
            m = re.match("#+", line)
            if m is None:
                in_content = True
            else:
                hashes = m.group(0)
                cnt = len(hashes)
                if cnt > 6:
                    raise RuntimeError(f"Too many hash marks ({cnt})) in line {line}")
                html += f"<h{cnt}>{md.renderInline(line[cnt:])}</h{cnt}>\n\n"
                continue

        # If we have a horizontal rule, honor that. Otherwise, parse the line separately
        md_line = md.render(line)
        if md_line.startswith("<hr />"):
            html += md_line
        else:
            html += _poem_line_to_html(line)

    return html


def generate_story(path: Path) -> str:
    """Generate the HTML for a story.

    :param path: Path to the story's markdown file.
    :return: HTML for the story.
    """
    raw_html = md.render(path.read_text(encoding="utf-8"))
    # Change <hr><p> into <p class="noindent"> the funky regex way
    # since lxml's HTML parser requires fragments have a single parent
    # (i.e. lxml wants to wrap the output of md.render() in a single div tag)
    raw_html = re.sub("<hr( /)?>\n*<p>", '<p class="noindent">', raw_html)

    return raw_html


def _piece_path_to_author_img_filename(path: Path) -> str:
    """Get the filename of the author image for the path to a piece."""
    m = re.search("(\d+)", path.stem)
    if not m:
        raise RuntimeError(f"Expected the piece path {path} to start with a number")
    return f"{m.group(0)}-author.jpg"


def create_content(
    piece_paths: Sequence[Path],
    bio_paths: Sequence[Path],
    titles: Sequence[str],
    authors: Sequence[str],
    ebook_chs: MutableSequence[epub.EpubItem],
) -> None:
    """Create ebook content.

    Content is created and added in-place to ebook_chs.

    :param piece_paths: List of paths to the content (as markdown files).
    :param bio_paths: List of paths to the authors' bios (as markdown files).
    :param titles: List of content titles.
    :param authors: List of content authors.
    :param ebook_chs: List of previously-added items.
    """
    current_year = datetime.datetime.now().year
    for ndx, (piece_path, bio_path, title, author) in enumerate(
        zip(piece_paths, bio_paths, titles, authors)
    ):
        content = '<div class="piece">\n'

        if "poem" in str(piece_path):
            content += generate_poem(piece_path)
        else:
            content += generate_story(piece_path)

        if "reprint" not in str(piece_path):
            # Add the end div and copyright statement
            content += f'</div>\n\n<div class="endmatter">\n<p>Copyright © {current_year} by {author}</p>\n</div>\n\n'
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

        # Add author bio and link to headshot
        content += (
            f'<p class="author-pic"><img class="author" '
            + f'src="{_piece_path_to_author_img_filename(piece_path)}" alt="{author}"/></p>\n\n'
        )
        content += md.render(bio_path.read_text(encoding="utf-8"))

        ch = epub.EpubHtml(
            title=title, file_name=f"body{len(ebook_chs):02}.xhtml", lang="en"
        )
        ch.set_content(content)
        ebook_chs.append(ch)


def add_images(
    book: epub.EpubBook,
    images_path: Path,
    piece_paths: Sequence[Path],
) -> None:
    """Add image files to the ebook.

    :param book: Book to add metadata to.
    :param images_path: Path to where the image files live.
    :param piece_paths: Paths to the magazine pieces.
    """
    for piece_path in piece_paths:
        image_path = images_path / _piece_path_to_author_img_filename(piece_path)
        book.add_item(
            epub.EpubImage(
                uid=image_path.stem,
                file_name=image_path.name,
                media_type="image/jpeg",
                content=image_path.read_bytes(),
            )
        )


def build_ebook():
    """Build Small Wonders ebook."""
    root_path = Path(__file__).parent
    content_path = root_path / "content"

    front_matter = ["0a-about.md", "0b-cover-artist.md", "0c-keyhole.md"]
    front_matter_titles = [
        "Title Page & Copyright",
        "About the Cover Artist",
        "Thru the Keyhole",
    ]
    front_matter_paths = [content_path / fn for fn in front_matter]

    stylesheet_path = root_path / "stylesheet.css"

    info = get_issue_info(content_path)

    book = epub.EpubBook()

    add_metadata(
        book, info.issue_num, info.editors, info.author_names, info.description
    )

    # Set stylesheet
    css = epub.EpubItem(
        uid="base_stylesheet",
        file_name="styles/stylesheet.css",
        media_type="text/css",
        content=stylesheet_path.read_text(encoding="utf-8"),
    )
    book.add_item(css)

    cover = add_cover(book, info.cover_path, title="Cover")

    ebook_chs = []  # Keep track of what we're adding to the ebook

    # Add NCX and nav
    book.add_item(epub.EpubNcx())
    nav = epub.EpubNav(title="Table of Contents")
    ebook_chs.append(nav)

    create_front_matter(front_matter_paths, front_matter_titles, ebook_chs)
    create_content(
        info.piece_paths, info.bio_paths, info.titles, info.author_names, ebook_chs
    )

    # Add CSS to each ebook chapter and add the chapter to the book
    for ch in ebook_chs:
        ch.add_item(css)
        book.add_item(ch)

    add_images(book, content_path, info.piece_paths)

    full_contents = [cover] + ebook_chs

    book.spine = tuple(full_contents)
    book.toc = tuple(full_contents)

    write_epub(f"Small Wonders Magazine Issue {info.issue_num}.epub", book)


if __name__ == "__main__":
    build_ebook()
