import datetime
import uuid
from collections.abc import MutableSequence, Sequence
from pathlib import Path

from ebooklib import epub
from markdown_it import MarkdownIt

from ebooklib_patch import SWEpubCoverHtml, write_epub
from issue_info import IssueInfo, get_issue_info
from renderers import render_poem_for_ebook, render_story_for_ebook

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
    info: IssueInfo,
) -> None:
    """Add metadata to the ebook.

    :param book: Book to add metadata to.
    :param info: Information about the issue.
    """
    book.set_identifier(str(uuid.uuid4()))
    book.set_title(f"Small Wonders Issue {info.issue_num}")
    book.set_language("en")
    book.add_metadata("DC", "publisher", "Small Wonders LLC")
    for editor in info.editors:
        book.add_metadata("DC", "creator", editor)
    for author in info.author_names:
        book.add_metadata("DC", "contributor", author)
    book.add_metadata("DC", "date", datetime.date.today().isoformat())
    book.add_metadata("DC", "description", info.description)
    for subject in magazine_subjects:
        book.add_metadata("DC", "subject", subject)
    book.add_metadata(
        None, "meta", "", {"name": "calibre:series", "content": "Small Wonders"}
    )
    book.add_metadata(
        None,
        "meta",
        "",
        {"name": "calibre:series_index", "content": str(info.issue_num)},
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


def create_content(
    info: IssueInfo,
    ebook_chs: MutableSequence[epub.EpubItem],
) -> None:
    """Create ebook content.

    Content is created and added in-place to ebook_chs.

    :param info: Information about the issue.
    :param ebook_chs: List of previously-added items.
    """
    current_year = datetime.datetime.now().year
    for ndx, (piece_path, _, title, bio_path, author, avatar_path) in enumerate(
        info.piece_info()
    ):
        content = '<div class="piece">\n'

        if "poem" in str(piece_path):
            content += render_poem_for_ebook(piece_path)
        else:
            content += render_story_for_ebook(piece_path)

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
            + f'src="{avatar_path}" alt="{author}"/></p>\n\n'
        )
        content += md.render(bio_path.read_text(encoding="utf-8"))

        ch = epub.EpubHtml(
            title=title, file_name=f"body{len(ebook_chs):02}.xhtml", lang="en"
        )
        ch.set_content(content)
        ebook_chs.append(ch)


def add_images(
    book: epub.EpubBook,
    avatar_paths: Sequence[Path],
) -> None:
    """Add image files to the ebook.

    :param book: Book to add metadata to.
    :param avatar_paths: Paths to the authors' avatars.
    """
    for avatar_path in avatar_paths:
        book.add_item(
            epub.EpubImage(
                uid=avatar_path.stem,
                file_name=avatar_path.name,
                media_type="image/jpeg",
                content=avatar_path.read_bytes(),
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

    add_metadata(book, info)

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
    create_content(info, ebook_chs)

    # Add CSS to each ebook chapter and add the chapter to the book
    for ch in ebook_chs:
        ch.add_item(css)
        book.add_item(ch)

    add_images(book, info.avatar_paths)

    full_contents = [cover] + ebook_chs

    book.spine = tuple(full_contents)
    book.toc = tuple(full_contents)

    write_epub(f"Small Wonders Magazine Issue {info.issue_num}.epub", book)


if __name__ == "__main__":
    build_ebook()
