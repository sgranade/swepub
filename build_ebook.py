import datetime
import re
from collections.abc import MutableSequence, Sequence
from pathlib import Path

from ebooklib import epub

from ebook_info import (
    PieceType,
    add_cover,
    add_metadata,
    add_piece,
    add_stylesheet,
    create_front_matter,
    create_piece_content,
)
from ebooklib_patch import write_epub
from issue_info import IssueInfo, get_issue_info


def _avatar_path_to_author_img_src(path: Path) -> str:
    """Get the ebook path to the author avatar given the path to the avatar."""
    m = re.search(r"(\d+)", path.stem)
    if not m:
        raise RuntimeError(f"Expected the avatar path {path} to start with a number")
    return f"{m.group(0)}-author.jpg"


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
    for piece_path, _, title, bio_path, author, avatar_path in info.piece_info():
        piece_type = (
            PieceType.Poem
            if "poem" in str(piece_path)
            else (
                PieceType.Reprint
                if "reprint" in str(piece_path)
                else PieceType.Original
            )
        )

        content = create_piece_content(piece_path, piece_type, author, current_year)

        add_piece(
            title,
            content,
            author,
            _avatar_path_to_author_img_src(avatar_path),
            bio_path,
            ebook_chs,
        )


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
    """Build Small Wonders issue ebook."""
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
        book,
        f"Small Wonders Issue {info.issue_num}",
        info.editors,
        info.author_names,
        info.description,
        info.issue_num,
    )

    # Set stylesheet
    css = add_stylesheet(book, stylesheet_path)

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

    book.spine = list(full_contents)
    book.toc = list(full_contents)

    write_epub(f"Small Wonders Magazine Issue {info.issue_num}.epub", book)


if __name__ == "__main__":
    build_ebook()
