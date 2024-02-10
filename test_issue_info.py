from unittest.mock import Mock

import pytest

import issue_info as uut


class TestIssueInfo:
    def test_piece_info_iterates_over_piece_path_title_bio_path_and_author_names(self):
        info = uut.IssueInfo(
            issue_num=1,
            cover_path=Mock(name="cover_path"),
            description="desc",
            editors=["a", "b"],
            piece_paths=["piece_path_1", "piece_path_2"],
            piece_post_days=[0, 2],
            titles=["one", "two"],
            bio_paths=["bio_path_1", "bio_path_2"],
            author_names=["ky", "se"],
            avatar_paths=["av1", "av2"],
        )

        result = info.piece_info()

        assert list(result) == [
            ("piece_path_1", 0, "one", "bio_path_1", "ky", "av1"),
            ("piece_path_2", 2, "two", "bio_path_2", "se", "av2"),
        ]


class TestGetIssueNum:
    def test_returns_first_found_issue_number_preceded_by_the_word_Issue(self):
        contents = "issue 10\nIssue 17x3\nIssue22"
        p = Mock(name="issue_path")
        p.read_text.return_value = contents

        result = uut.get_issue_num(p)

        assert result == 17

    def test_raises_error_if_issue_number_isnt_found(self):
        p = Mock(name="issue_path")
        p.read_text.return_value = "No issue number here"

        with pytest.raises(RuntimeError, match="Couldn't find issue number"):
            uut.get_issue_num(p)

        # Test passes if the exception is raised


class TestGetEditors:
    def test_returns_editors_one_per_line_with_whitespace_trimmed(self):
        contents = "\n".join(["Mx. Edone", " The Right Honorable Editrex "])
        p = Mock(name="editor_path")
        p.read_text.return_value = contents

        result = uut.get_editors(p)

        assert result == ["Mx. Edone", "The Right Honorable Editrex"]


class TestGetTitlesAndAuthors:
    def test_finds_title_from_first_heading_one(self):
        contents = "\n".join(["## Mx. Author", "# Title", "# Not a title"])
        p = Mock(name="piece_path")
        p.read_text.return_value = contents

        result, _ = uut.get_titles_and_authors([p])

        assert result == ["Title"]

    def test_finds_author_from_first_heading_two(self):
        contents = "\n".join(["# Title", "## Mx. Author", "## Not an author"])
        p = Mock(name="piece_path")
        p.read_text.return_value = contents

        _, result = uut.get_titles_and_authors([p])

        assert result == ["Mx. Author"]

    def test_strips_by_from_author_name(self):
        contents = "\n".join(["# Title", "## by  Mx. Author"])
        p = Mock(name="piece_path")
        p.read_text.return_value = contents

        _, result = uut.get_titles_and_authors([p])

        assert result == ["Mx. Author"]

    def test_raises_exception_on_missing_title(self):
        contents = "## Title"
        p = Mock(name="piece_path")
        p.read_text.return_value = contents

        with pytest.raises(RuntimeError, match="No title found."):
            uut.get_titles_and_authors([p])

        # Test passes if exception is raised

    def test_raises_exception_on_missing_author(self):
        contents = "# Mx. Author"
        p = Mock(name="piece_path")
        p.read_text.return_value = contents

        with pytest.raises(RuntimeError, match="No author found."):
            uut.get_titles_and_authors([p])

        # Test passes if exception is raised
