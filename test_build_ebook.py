from unittest.mock import MagicMock, Mock

import pytest

import build_ebook as uut


class TestGeneratePoem:
    def test_wraps_lines_in_divs(self):
        text = "first line\nsecond line\n"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result = uut.generate_poem(mock_path)

        assert (
            result
            == '<div class="poem">first line&nbsp;</div>\n'
            + '<div class="poem">second line&nbsp;</div>\n'
        )

    def test_parses_markdown_in_a_given_line(self):
        text = "_first_ line\n**second** line\n"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result = uut.generate_poem(mock_path)

        assert (
            result
            == '<div class="poem"><em>first</em> line&nbsp;</div>\n'
            + '<div class="poem"><strong>second</strong> line&nbsp;</div>\n'
        )

    def test_renders_blank_lines_as_div_with_non_breaking_space(self):
        text = "start line\n\nend line\n"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result = uut.generate_poem(mock_path)

        assert (
            result
            == '<div class="poem">start line&nbsp;</div>\n'
            + '<div class="poem">&nbsp;</div>\n'
            + '<div class="poem">end line&nbsp;</div>\n'
        )

    def test_skips_leading_blank_lines(self):
        text = "\n\n\nstart line\nend line\n"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result = uut.generate_poem(mock_path)

        assert (
            result
            == '<div class="poem">start line&nbsp;</div>\n'
            + '<div class="poem">end line&nbsp;</div>\n'
        )

    def test_converts_two_hashes_to_heading_2(self):
        text = "##Title _Italics_"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result = uut.generate_poem(mock_path)

        assert result == "<h2>Title <em>Italics</em></h2>\n\n"

    def test_converts_six_hashes_to_heading_6(self):
        text = "######Title _Italics_"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result = uut.generate_poem(mock_path)

        assert result == "<h6>Title <em>Italics</em></h6>\n\n"

    def test_raises_error_on_seven_hashes(self):
        text = "#######Nope"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        with pytest.raises(RuntimeError):
            uut.generate_poem(mock_path)

        # Test passes if exception is raised

    def test_adds_indent_class_on_tabs(self):
        text = "\tIndent one\n\t\tIndent two"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result = uut.generate_poem(mock_path)

        assert (
            result
            == '<div class="poem tab1">Indent one&nbsp;</div>\n'
            + '<div class="poem tab2">Indent two&nbsp;</div>\n'
        )

    def test_raises_error_on_five_tabs(self):
        text = "\t\t\t\t\tNope"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        with pytest.raises(RuntimeError):
            uut.generate_poem(mock_path)

        # Test passes if exception is raised


class TestGenerateStory:
    def test_renders_basic_markdown(self):
        text = "Para 1 _with italics_.\n\nPara 2 **with bold**."
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result = uut.generate_story(mock_path)

        assert (
            result
            == "<p>Para 1 <em>with italics</em>.</p>\n<p>Para 2 <strong>with bold</strong>.</p>\n"
        )

    def test_changes_hr_to_noindent_para(self):
        text = "Para 1.\n\n----\n\nPara 2."
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result = uut.generate_story(mock_path)

        assert result == '<p>Para 1.</p>\n<p class="noindent">Para 2.</p>\n'
