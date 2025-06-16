from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, create_autospec, patch

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

import best_of_year_info as uut


def test_find_possible_piece_paths_returns_all_markdown_files():
    piece_paths = [
        create_autospec(Path, name="piece-one.md"),
        create_autospec(Path, name="piece-two.md"),
    ]
    piece_paths[0].stem = "piece-one"
    piece_paths[1].stem = "piece-two"
    root_path = create_autospec(Path, name="root_path")
    root_path.glob.side_effect = lambda pattern: (
        piece_paths if pattern == "*.md" else []
    )

    result = uut.find_possible_piece_paths(root_path)

    assert result == piece_paths


def test_find_possible_piece_paths_skips_author_files():
    piece_paths = [
        create_autospec(Path, name="piece-one.md"),
        create_autospec(Path, name="piece-one-author.md"),
        create_autospec(Path, name="piece-two.md"),
        create_autospec(Path, name="piece-two-author.md"),
    ]
    piece_paths[0].stem = "piece-one"
    piece_paths[1].stem = "piece-one-author"
    piece_paths[2].stem = "piece-two"
    piece_paths[3].stem = "piece-two-author"
    root_path = create_autospec(Path, name="root_path")
    root_path.glob.side_effect = lambda pattern: (
        piece_paths if pattern == "*.md" else []
    )

    result = uut.find_possible_piece_paths(root_path)

    assert result == [piece_paths[0], piece_paths[2]]


def test_read_pieces_info_reads_title_and_author():
    p1 = Mock(name="piece_path_1")
    p1.read_text.return_value = "\n".join(["# Title", "## by  Mx. Author"])
    p2 = Mock(name="piece_path_2")
    p2.read_text.return_value = "\n".join(["# Other", "## J. Random"])
    paths = [p1, p2]

    result = uut.read_pieces_info(paths)

    assert result == {
        "title": (p1, "Title", "Mx. Author"),
        "other": (p2, "Other", "J. Random"),
    }


def test_read_pieces_info_simplifies_title_for_dict_key():
    p = Mock(name="piece_path")
    p.read_text.return_value = "\n".join(
        ['# Title\'s Other’s, a "Love" Story', "## by  Mx. Author"]
    )
    paths = [p]

    result = uut.read_pieces_info(paths)

    assert result == {
        "titles others a love story": (
            p,
            'Title\'s Other’s, a "Love" Story',
            "Mx. Author",
        ),
    }


def test_read_pub_order_csv_reads_the_dataframe():
    b = BytesIO()
    b.write(
        "\n".join(
            [
                "Title,Type,Info",
                "Plums,Poem,We liked this!",
                "Baby Shoes,Story,Overdone!",
            ]
        ).encode()
    )
    b.seek(0)

    result = uut.read_pub_order_csv(b)  # type: ignore

    assert_frame_equal(
        result,
        pd.DataFrame(
            {
                "Title": ["Plums", "Baby Shoes"],
                "Type": ["Poem", "Story"],
                "Info": ["We liked this!", "Overdone!"],
            }
        ),
    )


def test_read_pub_order_csv_raises_exception_on_missing_title_column():
    b = BytesIO()
    b.write("\n".join(["Type,Info", "Poem,We liked this!"]).encode())
    b.seek(0)

    with pytest.raises(RuntimeError, match="missing expected columns: Title"):
        uut.read_pub_order_csv(b)  # type: ignore

    # Test passes if exception raised


def test_read_pub_order_csv_raises_exception_on_missing_type_column():
    b = BytesIO()
    b.write("\n".join(["Title,Info", "Plums,We liked this!"]).encode())
    b.seek(0)

    with pytest.raises(RuntimeError, match="missing expected columns: Type"):
        uut.read_pub_order_csv(b)  # type: ignore

    # Test passes if exception raised


def test_read_pub_order_csv_raises_exception_on_missing_info_column():
    b = BytesIO()
    b.write("\n".join(["Title,Type", "Plums,Story"]).encode())
    b.seek(0)

    with pytest.raises(RuntimeError, match="missing expected columns: Info"):
        uut.read_pub_order_csv(b)  # type: ignore

    # Test passes if exception raised


def test_read_pub_order_csv_raises_exception_on_multiple_missing_columns():
    b = BytesIO()
    b.write("\n".join(["Title", "Plums"]).encode())
    b.seek(0)

    with pytest.raises(RuntimeError, match="missing expected columns: Type, Info"):
        uut.read_pub_order_csv(b)  # type: ignore

    # Test passes if exception raised


def test_order_pieces_returns_info_in_dataframe_order():
    pieces_info = {
        "gideon the ninth": (Path("ninth.md"), "Gideon the Ninth", "Tamsyn Muir"),
        "plums": (Path("plums.md"), "Plums", "Mx. Author"),
        "baby shoes": (Path("shoes.md"), "Baby Shoes", "Canon Lit"),
    }
    pub_order_df = pd.DataFrame(
        {
            "Title": ["Plums", "Baby Shoes", "Gideon the Ninth"],
            "Type": ["Poem", "Story", "Novel"],
            "Info": ["We liked this!", "Overdone!", "Yes please."],
        }
    )
    errors = []
    warnings = []

    result = uut.order_pieces(pieces_info, pub_order_df, errors, warnings)

    assert result == [
        (Path("plums.md"), "Plums", "Mx. Author"),
        (Path("shoes.md"), "Baby Shoes", "Canon Lit"),
        (Path("ninth.md"), "Gideon the Ninth", "Tamsyn Muir"),
    ]


def test_order_pieces_creates_error_message_for_missing_pieces():
    pieces_info = {
        "gideon the ninth": (Path("ninth.md"), "Gideon the Ninth", "Tamsyn Muir"),
        "baby shoes": (Path("shoes.md"), "Baby Shoes", "Canon Lit"),
    }
    pub_order_df = pd.DataFrame(
        {
            "Title": ["Plums", "Baby Shoes", "Gideon the Ninth"],
            "Type": ["Poem", "Story", "Novel"],
            "Info": ["We liked this!", "Overdone!", "Yes please."],
        }
    )
    errors = []
    warnings = []

    uut.order_pieces(pieces_info, pub_order_df, errors, warnings)

    assert errors == ["Missing pieces: Plums"]


def test_order_pieces_creates_warning_message_for_extra_pieces():
    pieces_info = {
        "gideon the ninth": (Path("ninth.md"), "Gideon the Ninth", "Tamsyn Muir"),
        "plums": (Path("plums.md"), "Plums", "Mx. Author"),
        "whoops extra": (Path("unexpected.md"), "Whoops Extra", "Snuck In"),
        "baby shoes": (Path("shoes.md"), "Baby Shoes", "Canon Lit"),
    }
    pub_order_df = pd.DataFrame(
        {
            "Title": ["Plums", "Baby Shoes", "Gideon the Ninth"],
            "Type": ["Poem", "Story", "Novel"],
            "Info": ["We liked this!", "Overdone!", "Yes please."],
        }
    )
    errors = []
    warnings = []

    uut.order_pieces(pieces_info, pub_order_df, errors, warnings)

    assert warnings == ["Files whose titles didn't match: unexpected.md (Whoops Extra)"]


def test_get_bio_and_avi_paths_returns_bio_paths():
    with patch.object(Path, "exists", autospec=True) as mock_exists:
        p1 = Path("story1.md")
        mock_exists.side_effect = lambda self: True
        errors = []

        result, _ = uut.get_bio_and_avi_paths([p1], errors)

    assert result == [Path("story1-author.md")]
    assert not errors


def test_get_bio_and_avi_paths_returns_avi_paths():
    with patch.object(Path, "exists", autospec=True) as mock_exists:
        p1 = Path("story1.md")
        mock_exists.side_effect = lambda self: True
        errors = []

        _, result = uut.get_bio_and_avi_paths([p1], [])

    assert result == [Path("story1.jpg")]
    assert not errors


def test_get_bio_and_avi_paths_returns_errors_for_missing_bios_and_avis():
    with patch.object(Path, "exists", autospec=True) as mock_exists:
        p1 = Path("story1.md")
        mock_exists.side_effect = lambda self: False
        errors = []

        uut.get_bio_and_avi_paths([p1], errors)

    assert errors == [
        "Missing bios: story1-author.md",
        "Missing author avatars: story1.jpg",
    ]
