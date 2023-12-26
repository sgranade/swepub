from unittest.mock import MagicMock, Mock

import pytest

import build_ebook as uut


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
