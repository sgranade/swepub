import re
from pathlib import Path

import click
from ebooklib import epub
from num2words import num2words

import console
from best_of_year_info import BestOfYearInfo, get_best_of_year_info
from ebook_info import (
    add_cover,
    add_metadata,
    add_piece,
    add_stylesheet,
    create_front_matter,
    create_piece_content,
)
from ebooklib_patch import write_epub


def _author_name_to_author_img_src(name: str) -> str:
    """Get the ebook src path to the author avatar given the author's name."""
    return re.sub(r"[\s.]", "_", name).lower() + ".jpg"


def create_content(
    info: BestOfYearInfo,
    ebook_chs: list[epub.EpubItem],
) -> None:
    """Create ebook content.

    Content is created and added in-place to ebook_chs.

    :param info: Information about the issue.
    :param ebook_chs: List of previously-added items.
    """
    for (
        piece_path,
        piece_type,
        title,
        bio_path,
        author,
        _,
        copy_year,
        intro,
    ) in info.piece_info():
        content = create_piece_content(
            piece_path,
            piece_type,
            author,
            copy_year,
            f'<div class="editorIntro">{intro}</div>\n\n',
        )

        add_piece(
            title,
            content,
            author,
            _author_name_to_author_img_src(author),
            bio_path,
            ebook_chs,
        )


def add_images(
    book: epub.EpubBook, avatar_paths: list[Path], author_names: list[str]
) -> None:
    """Add image files to the ebook.

    :param book: Book to add metadata to.
    :param avatar_paths: Paths to the authors' avatars.
    :param author_names: Authors' names.
    """
    for path, src in zip(
        avatar_paths, (_author_name_to_author_img_src(name) for name in author_names)
    ):
        book.add_item(
            epub.EpubImage(
                uid=src.split(".")[0],
                file_name=src,
                media_type="image/jpeg",
                content=path.read_bytes(),
            )
        )


@click.command()
@click.option(
    "--year",
    prompt="What year of the magazine is this for (ex: One)?",
    help="Magazine year for this issue (ex: One)",
    type=str,
)
@click.option(
    "--content-path",
    help="Path to the content files",
    type=click.Path(file_okay=False, path_type=Path),
)
def create_best_of_year(year: str, content_path: Path | None) -> None:
    root_path = Path(__file__).parent
    if not content_path:
        content_path = root_path / "best_of_year"
    stylesheet_path = root_path / "stylesheet.css"
    if re.match(r"\d+$", year):
        year = num2words(year)
    year = year.capitalize()
    front_matter = ["about.md", "keyhole.md"]
    front_matter_titles = [
        "Title Page & Copyright",
        "Thru the Keyhole",
    ]
    front_matter_paths = [content_path / fn for fn in front_matter]

    console.heading(f"Creating Best of Year {year} ebook")

    try:
        info, errors, warnings = get_best_of_year_info(content_path)
    except RuntimeError as err:
        console.error(str(err))
        return
    if errors:
        for error in errors:
            console.error(error)
    if warnings:
        for warning in warnings:
            console.warn(warning)
    if errors:
        return

    book = epub.EpubBook()

    add_metadata(
        book,
        f"Small Wonders Magazine: Best of Year {year}",
        info.editors,
        info.author_names,
        info.description,
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

    add_images(book, info.avatar_paths, info.author_names)

    full_contents = [cover] + ebook_chs

    book.spine = list(full_contents)
    book.toc = list(full_contents)

    write_epub(f"Small Wonders Magazine Best of Year {year}.epub", book)


if __name__ == "__main__":
    create_best_of_year()
