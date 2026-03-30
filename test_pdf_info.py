from pathlib import Path
from unittest.mock import Mock

import pdf_info as uut
from ebook_info import PieceType


def _mock_path(text: str) -> Mock:
    """Return a Path-like mock whose read_text() returns *text*."""
    return Mock(read_text=Mock(return_value=text))


class TestCreateCoverSection:
    def test_contains_cover_image_filename(self):
        # No arrange

        result = uut.create_cover_section(Path("content/cover.jpg"))

        assert "cover.jpg" in result

    def test_has_cover_section_id(self):
        # No arrange
        
        result = uut.create_cover_section(Path("content/cover.jpg"))

        assert 'id="cover"' in result


class TestCreateTocEntry:
    def test_href_matches_piece_number(self):
        # No arrange
        
        result = uut.create_toc_entry(3, "Some Title", "Some Author")

        assert 'href="#piece-3"' in result

    def test_contains_title_and_author(self):
        # No arrange
        
        result = uut.create_toc_entry(1, "My Title", "Jo Author")

        assert "My Title" in result
        assert "Jo Author" in result


class TestCreateTocSection:
    def test_entry_hrefs_match_piece_ids(self):
        titles = ["Title A", "Title B", "Title C"]
        authors = ["Author A", "Author B", "Author C"]

        toc = uut.create_toc_section(titles, authors)
        pieces = [
            uut.create_piece_section(
                n + 1,
                _mock_path(f"# {titles[n]}\n\n## by {authors[n]}\n\nText."),
                PieceType.Original,
                authors[n],
                2025,
                Path(f"content/{n + 1}-author.jpg"),
                _mock_path("Bio."),
            )
            for n in range(3)
        ]

        for n in range(1, 4):
            href = f'href="#piece-{n}"'
            section_id = f'id="piece-{n}"'
            assert href in toc
            assert any(section_id in p for p in pieces)

    def test_has_toc_section_id(self):
        # No arrange
        
        result = uut.create_toc_section(["T"], ["A"])

        assert 'id="toc"' in result


class TestCreateFrontMatterSection:
    def test_has_correct_section_id(self):
        # No arrange
        
        result = uut.create_front_matter_section(2, _mock_path("Some content."))

        assert 'id="front-2"' in result

    def test_renders_markdown_content(self):
        # No arrange
        
        result = uut.create_front_matter_section(1, _mock_path("**Bold** text."))

        assert "<strong>Bold</strong>" in result


class TestCreatePieceSection:
    def _piece(self, n, piece_type, author="Author", copyright_year=2025, extra=""):
        text = f"# Title {n}\n\n## by {author}\n\nParagraph.{extra}"
        return uut.create_piece_section(
            n,
            _mock_path(text),
            piece_type,
            author,
            copyright_year,
            Path(f"content/{n}-author.jpg"),
            _mock_path("Bio text."),
        )

    def test_each_piece_gets_unique_section_id(self):
        for n in range(1, 10):
            # No arrange
        
            result = self._piece(n, PieceType.Original)
    
            assert f'id="piece-{n}"' in result

    def test_original_copyright_year_in_endmatter(self):
        # No arrange
        
        result = self._piece(1, PieceType.Original, author="Jo Writer", copyright_year=2025)

        assert "2025" in result
        assert "Jo Writer" in result

    def test_poem_piece_type_uses_poem_rendering(self):
        # No arrange
        
        result = self._piece(2, PieceType.Poem)

        # render_poem_for_epub wraps lines in divs with class "poem"
        assert 'class="poem"' in result

    def test_reprint_contains_original_copyright_line(self):
        text = (
            "# Title\n\n## by Original Author\n\nParagraph.\n\n"
            "Copyright (c) 2010 by Original Author\n\n"
            "First published in Some Magazine"
        )

        result = uut.create_piece_section(
            3,
            _mock_path(text),
            PieceType.Reprint,
            "Original Author",
            2025,
            Path("content/3-author.jpg"),
            _mock_path("Bio."),
        )

        assert "2010" in result
        assert "Original Author" in result

    def test_reprint_does_not_use_generated_copyright_year(self):
        text = (
            "# Title\n\n## by Author\n\nParagraph.\n\n"
            "Copyright (c) 1999 by Author\n\n"
            "First published in Some Magazine"
        )

        result = uut.create_piece_section(
            3,
            _mock_path(text),
            PieceType.Reprint,
            "Author",
            2025,
            Path("content/3-author.jpg"),
            _mock_path("Bio."),
        )

        assert "1999" in result
        assert "2025" not in result

    def test_avatar_src_in_output(self):
        # No arrange
        
        result = self._piece(5, PieceType.Original)

        assert "5-author.jpg" in result


_PIECE_TYPES = [PieceType.Original, PieceType.Poem, PieceType.Reprint] * 3
_TITLES = [f"Title {i}" for i in range(1, 10)]
_AUTHORS = [f"Author {i}" for i in range(1, 10)]


def _nine_piece_sections():
    sections = []
    for n in range(1, 10):
        piece_type = _PIECE_TYPES[n - 1]
        author = _AUTHORS[n - 1]
        title = _TITLES[n - 1]
        if piece_type == PieceType.Reprint:
            text = (
                f"# {title}\n\n## by {author}\n\nText.\n\n"
                f"Copyright (c) 2010 by {author}\n\nFirst published in Some Mag"
            )
        else:
            text = f"# {title}\n\n## by {author}\n\nText."
        sections.append(
            uut.create_piece_section(
                n,
                _mock_path(text),
                piece_type,
                author,
                2025,
                Path(f"content/{n}-author.jpg"),
                _mock_path("Bio."),
            )
        )
    return sections


class TestNinePieceAssembly:
    def test_all_nine_titles_appear_in_assembled_html(self):
        # No arrange
        
        html = "".join(_nine_piece_sections())

        for title in _TITLES:
            assert title in html

    def test_all_nine_author_names_appear_in_assembled_html(self):
        # No arrange
        
        toc = uut.create_toc_section(_TITLES, _AUTHORS)
        pieces = "".join(_nine_piece_sections())
        html = toc + pieces

        for author in _AUTHORS:
            assert author in html

    def test_front_matter_sections_appear_before_piece_sections(self):
        # No arrange
        
        front_matter = "".join(
            uut.create_front_matter_section(n + 1, _mock_path(f"Front matter {n}."))
            for n in range(3)
        )
        pieces = "".join(_nine_piece_sections())
        html = front_matter + pieces

        last_front = max(html.index(f'id="front-{n}"') for n in range(1, 4))
        first_piece = html.index('id="piece-1"')
        assert last_front < first_piece

    def test_copyright_year_in_non_reprint_endmatter(self):
        # No arrange
        
        sections = _nine_piece_sections()

        for n, (section, piece_type) in enumerate(zip(sections, _PIECE_TYPES), start=1):
            if piece_type != PieceType.Reprint:
                assert "2025" in section, f"Expected copyright year in piece {n}"
