import datetime
import re
import uuid
from collections import OrderedDict
from collections.abc import Iterable, MutableSequence, Sequence
from itertools import pairwise
from pathlib import Path

from ebooklib import epub
from markdown_it import MarkdownIt
from PIL import Image

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


# Adapted from the ebooklib class so I could tweak it -- the existing class lower-cases all
# xml attributes, which wrecks the viewBox attribute
class EpubCoverHtml(epub.EpubHtml):
    def __init__(
        self, uid="cover", file_name="cover.xhtml", image_name="", title="Cover"
    ):
        super(EpubCoverHtml, self).__init__(uid=uid, file_name=file_name, title=title)

        self.image_name = image_name
        self.is_linear = False

    def is_chapter(self):
        return False

    def set_content(self, cover_path):
        self.content = self.get_cover_html_content(cover_path)

    def get_content(self):
        return self.content

    def get_cover_html_content(self, cover_path: Path) -> bytes:
        with Image.open(cover_path) as img:
            cover_width, cover_height = img.size

        return (
            """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">
 <head>
  <style>
    body { margin: 0em; padding: 0em; }
    img { max-width: 100%; max-height: 100%; }
  </style>
 </head>
 <body>
   <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
   height="100%" width="100%" viewBox="0 0 """
            + f"{cover_width} {cover_height}"
            + '''" preserveAspectRatio="xMidYMid meet" version="1.1">
     <image href="'''
            + self.image_name
            + """" alt="Cover art"/></svg>
 </body>
</html>"""
        ).encode()

    def __str__(self):
        return "<EpubCoverHtml:%s:%s>" % (self.id, self.file_name)


# Adapted from the ebooklib function so I can tweak it
def set_cover(book, file_name: str, cover_path: Path, create_page=True, title="Cover"):
    """
    Set cover and create cover document if needed.

    :Args:
      - book: epub object to add the cover to
      - file_name: file name of the cover page (in the epub file)
      - cover_path: Path to the image file
      - create_page: Should cover page be defined. Defined as bool value (optional). Default value is True.
      - title: Title for the cover page (if defined).
    """

    cover_path = Path(cover_path)
    content = cover_path.read_bytes()

    c0 = epub.EpubCover(file_name=file_name)
    c0.content = content
    book.add_item(c0)

    if create_page:
        c1 = EpubCoverHtml(title=title, file_name="cover.xhtml", image_name=file_name)
        c1.set_content(cover_path)
        book.add_item(c1)

    book.add_metadata(
        None, "meta", "", OrderedDict([("name", "cover"), ("content", "cover-img")])
    )


def get_titles_and_authors(
    piece_paths: Iterable[Path],
) -> Sequence[Sequence[str], Sequence[str]]:
    """Get the titles and authors from the files containing the pieces."""
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


def get_editors(editors_path: Path) -> Sequence[str]:
    """Get the editors from the file containing the list of editors."""
    return editors_path.read_text().splitlines()


def get_issue_num(about_path: Path) -> int:
    """Get the current issue number."""
    m = re.search("Issue +(\d+)", about_path.read_text())
    if m is None:
        raise RuntimeError(f"Couldn't find issue number in {about_path}")
    return int(m.group(1))


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


def generate_poem(path: Path) -> str:
    """Generate the HTML for a poem.

    :param path: Path to the poem's markdown file.
    :return: HTML for the poem.
    """
    html = ""
    lines = path.read_text(encoding="utf-8").splitlines()
    in_content = False
    for line in lines:
        if not in_content and not line.strip():
            continue
        if in_content or not line.startswith("#"):
            in_content = True
            # Extra non-breaking space needed to force ereaders to honor blank lines
            html += f'<div class="poem">{line}&nbsp;</div>\n'
        elif line.startswith("##"):
            html += f"<h2>{line[2:]}</h2>\n\n"
        elif line.startswith("#"):
            html += f"<h1>{line[1:]}</h1>\n\n"

    return html


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
            content += md.render(piece_path.read_text(encoding="utf-8"))

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
                    + '</div>\n<div class="endmatter">\n'
                    + content[ndx:]
                    + "</div>\n\n"
                )

        # Add author bio and link to headshot
        content += (
            f'<p class="author-pic"><img class="author" '
            + f'src="{piece_path.name}" alt="{author}"/></p>\n\n'
        )
        content += md.render(bio_path.read_text(encoding="utf-8"))

        ch = epub.EpubHtml(
            title=title, file_name=f"body{len(ebook_chs):02}.xhtml", lang="en"
        )
        ch.set_content(content)
        ebook_chs.append(ch)


def add_images(
    book: epub.EpubBook, image_paths: Sequence[Path], piece_paths: Sequence[Path]
) -> None:
    """Add image files to the ebook.

    :param book: Book to add metadata to.
    :param image_paths: Paths to the image files.
    :param piece_paths: Paths to the magazine pieces.
    """
    for image_path, piece_path in zip(image_paths, piece_paths):
        book.add_item(
            epub.EpubImage(
                uid=image_path.stem,
                file_name=piece_path.name,
                media_type="image/jpeg",
                content=image_path.read_bytes(),
            )
        )


def build_ebook():
    """Build Small Wonders ebook."""
    root_path = Path(__file__).parent
    content_path = root_path / "content"
    images_path = root_path / "images"

    front_matter = ["0a-about.md", "0b-cover-artist.md", "0c-keyhole.md"]
    front_matter_titles = [
        "Title Page & Copyright",
        "About the Cover Artist",
        "Thru the Keyhole",
    ]

    # Generate filenames for all pieces
    content_types = ("story", "poem", "reprint")
    pieces = [f"{idx+1}a-{content_types[idx % 3]}.md" for idx in range(0, 9)]
    author_bios = [f"{idx+1}b-author.md" for idx in range(0, 9)]

    front_matter_paths = [content_path / fn for fn in front_matter]
    piece_paths = [content_path / fn for fn in pieces]
    author_bio_paths = [content_path / fn for fn in author_bios]
    author_image_paths = [
        images_path / f"{path.stem[0]}-author.jpg" for path in piece_paths
    ]
    cover_path = images_path / "cover.jpg"
    editors_path = content_path / "editors.txt"
    description_path = content_path / "description.html"

    stylesheet_path = root_path / "stylesheet.css"

    titles, authors = get_titles_and_authors(piece_paths)
    editors = get_editors(editors_path)
    issue_num = get_issue_num(front_matter_paths[0])

    book = epub.EpubBook()

    add_metadata(
        book, issue_num, editors, authors, description_path.read_text(encoding="utf-8")
    )

    # Set stylesheet
    css = epub.EpubItem(
        uid="base_stylesheet",
        file_name="styles/stylesheet.css",
        media_type="text/css",
        content=stylesheet_path.read_text(encoding="utf-8"),
    )
    book.add_item(css)

    set_cover(book, "cover.jpg", cover_path, title=f"Small Wonders Issue {issue_num}")

    ebook_chs = []  # Keep track of what we're adding to the ebook

    # Add NCX and nav
    book.add_item(epub.EpubNcx())
    nav = epub.EpubNav()
    ebook_chs.append(nav)

    create_front_matter(front_matter_paths, front_matter_titles, ebook_chs)
    create_content(piece_paths, author_bio_paths, titles, authors, ebook_chs)

    # Add CSS to each ebook chapter and add the chapter to the book
    for ch in ebook_chs:
        ch.add_item(css)
        book.add_item(ch)

    add_images(book, author_image_paths, piece_paths)

    book.spine = tuple(ebook_chs)
    book.toc = tuple(ebook_chs)

    epub.write_epub(f"Small Wonders Magazine Issue {issue_num}.epub", book)


if __name__ == "__main__":
    build_ebook()
