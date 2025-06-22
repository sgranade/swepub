import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import numpy as np
import pandas as pd

from ebook_info import PieceType
from issue_info import get_editors, get_title_and_author


@dataclass
class BestOfYearInfo:
    """Information about the Best of Year collection."""

    cover_path: Path
    description: str
    editors: list[str]

    editorial_path: Path
    piece_paths: list[Path]
    piece_types: list[PieceType]
    titles: list[str]
    bio_paths: list[Path]
    author_names: list[str]
    avatar_paths: list[Path]
    copy_years: list[int]
    intros: list[str]

    def piece_info(
        self,
    ) -> Iterator[tuple[Path, PieceType, str, Path, str, Path, int, str]]:
        """Get iterable over aggregated piece info.

        Aggregated piece info:
          - Path to the piece (Markdown)
          - Type
          - Title
          - Path to the author's bio (Markdown)
          - Author name
          - Path to the author's avatar (jpeg)
          - Copyright year
          - Editor's intro

        :yield: Iterator that produces tuples of (piece path, piece type, title, bio path, author name, avatar path, copyright year, intro).
        """
        return zip(
            self.piece_paths,
            self.piece_types,
            self.titles,
            self.bio_paths,
            self.author_names,
            self.avatar_paths,
            self.copy_years,
            self.intros,
            strict=True,
        )


def _simplify_title(title: str) -> str:
    """Simplify a title string for comparison purposes."""
    return re.sub("[,.'’\"]", "", title.lower())


def find_possible_piece_paths(root: Path) -> list[Path]:
    """Get paths to possible stories and poems in a root path.

    Stories and poems are assumed to be in Markdown files (`.md`) in the
    path that don't end in `-author.md`

    :param root: Path that contains all of the story and poem files.
    :return: List of paths to possible pieces.
    """
    paths = root.glob("*.md")
    # Get rid of author files
    return [fp for fp in root.glob("*.md") if not fp.stem.endswith("-author")]


PieceInfo = tuple[Path, str, str, int]
"""The path, title, author, and copyright year for a piece."""


def read_pieces_info(
    possible_piece_paths: Iterable[Path],
) -> dict[str, PieceInfo]:
    """Read information about pieces from their files.

    Note that any files in the list of paths that don't have a title
    (the first `#` in the Markdown file) or an author (the first `##`
    in the file).

    :param possible_piece_paths: List of paths to Markdown files.
    :return: Dictionary of simplified titles to PieceInfo.
    """
    possible_pieces: dict[str, PieceInfo] = {}

    for fp in possible_piece_paths:
        title, author, _ = get_title_and_author(fp)
        if title and author:
            possible_pieces[_simplify_title(title)] = fp, title, author, 0

    return possible_pieces


def read_pub_order_csv(order_path: Path) -> pd.DataFrame:
    """Read the CSV file listing the best-of pieces in publication order.

    :param order_path: Path to the CSV file.
    :raises RuntimeError: If the CSV is missing needed columns.
    :return: Dataframe with the information.
    """
    errors = []

    pub_order_df = pd.read_csv(order_path)
    for column in ["Title", "Type", "Copy Year", "Intro"]:
        if column not in pub_order_df.columns:
            errors.append(column)
    if errors:
        raise RuntimeError(
            f"CSV {order_path.name} with pieces' order is missing expected columns: {", ".join(errors)}"
        )

    return pub_order_df


def order_pieces(
    pieces_info: dict[str, PieceInfo],
    pub_order_df: pd.DataFrame,
    errors: list[str],
    warnings: list[str],
) -> list[PieceInfo]:
    """Sort the pieces into publication order.

    :param pieces_info: Information about pieces. Key: simplified title.
    :param pub_order_df: Publication order information.
    :param errors: List to which any errors will be added.
    :param warnings: List to which any warnings will be added.
    :return: Pieces' information in publication order.
    """
    title_series = pub_order_df.Title.map(_simplify_title)
    pieces: list[PieceInfo] = []
    missing_titles: list[str] = []
    pieces_info = dict(pieces_info)

    for ndx, title in enumerate(title_series):
        try:
            p = pieces_info.pop(title)
        except KeyError:
            missing_titles.append(pub_order_df.iloc[ndx].Title)
            continue
        copy_year = pub_order_df.iloc[ndx].loc["Copy Year"]
        if pd.isna(copy_year):
            if PieceType(pub_order_df.iloc[ndx].Type) != PieceType.Reprint:
                errors.append(
                    f"Piece {title} is missing its copyright year in the CSV with the pieces' order"
                )
                continue
            copy_year = 0
        pieces.append(p[:3] + (int(copy_year),))

    if missing_titles:
        errors.append(f"Missing pieces: {", ".join(missing_titles)}")
    if pieces_info:
        unmatched_files = [
            f"{fp.name} ({title})" for fp, title, _, _ in pieces_info.values()
        ]
        warnings.append(
            f"Files whose titles didn't match: {", ".join(unmatched_files)}"
        )

    return pieces


def get_bio_and_avi_paths(
    piece_paths: Iterable[Path], errors: list[str]
) -> tuple[list[Path], list[Path]]:
    """Get the paths to the author bios and avatars.

    The bios should be in `<title>-author.md` files and the avatars
    in `<title>.jpg` files. Any that don't exist result in an error
    message being added to the error list.

    :param pieces: List of paths to the pieces in publication order.
    :param errors: List to which any errors will be added.
    :return: Tuple with list of bio and avatar paths, in that order.
    """
    bio_paths = [fp.with_stem(fp.stem + "-author") for fp in piece_paths]
    avi_paths = [fp.with_suffix(".jpg") for fp in piece_paths]

    # Make sure each piece has a bio and an avi
    missing_bios = [fp for fp in bio_paths if not fp.exists()]
    missing_avis = [fp for fp in avi_paths if not fp.exists()]
    if missing_bios:
        errors.append(f"Missing bios: {", ".join([fp.name for fp in missing_bios])}")
    if missing_avis:
        errors.append(
            f"Missing author avatars: {", ".join([fp.name for fp in missing_avis])}"
        )

    return bio_paths, avi_paths


def get_best_of_year_info(
    content_path: Path,
) -> tuple[BestOfYearInfo, list[str], list[str]]:
    """Get all the needed information about an issue.

    :param content_path: Path to where all the content files live.
    :raises RuntimeError: If the option CSV is missing needed columns.
    :return: Tuple contaning best-of-year information, a list of any errors, and a list of any warnings.
    """
    errors = []
    warnings = []

    possible_piece_paths = find_possible_piece_paths(content_path)
    pieces_info = read_pieces_info(possible_piece_paths)
    pub_order_df = read_pub_order_csv(content_path / "order.csv")
    pieces = order_pieces(pieces_info, pub_order_df, errors, warnings)
    piece_paths, titles, author_names, copy_years = zip(*pieces)
    bio_paths, avi_paths = get_bio_and_avi_paths(piece_paths, errors)
    intros = list(pub_order_df.Intro)

    cover_path = content_path / "cover.jpg"
    description = (content_path / "description.html").read_text(encoding="utf-8")
    editors = get_editors(content_path / "editors.txt")
    editorial_path = content_path / "editorial.md"

    return (
        BestOfYearInfo(
            cover_path,
            description,
            editors,
            editorial_path,
            list(piece_paths),
            list(pub_order_df.Type.map(PieceType)),
            list(titles),
            bio_paths,
            list(author_names),
            avi_paths,
            list(copy_years),
            intros,
        ),
        errors,
        warnings,
    )
