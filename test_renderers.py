from unittest.mock import Mock

import pytest

import renderers as uut


class TestRenderStoryForEbook:
    def test_renders_basic_markdown(self):
        text = "Para 1 _with italics_.\n\nPara 2 **with bold**."
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result = uut.render_story_for_ebook(mock_path)

        assert (
            result
            == "<p>Para 1 <em>with italics</em>.</p>\n<p>Para 2 <strong>with bold</strong>.</p>\n"
        )

    def test_changes_hr_to_noindent_para(self):
        text = "Para 1.\n\n----\n\nPara 2."
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result = uut.render_story_for_ebook(mock_path)

        assert result == '<p>Para 1.</p>\n<p class="noindent">Para 2.</p>\n'


class TestRenderPoemForEbook:
    def test_converts_two_hashes_to_heading_2(self):
        text = "##Title _Italics_"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result = uut.render_poem_for_ebook(mock_path)

        assert result == "<h2>Title <em>Italics</em></h2>\n\n"

    def test_converts_six_hashes_to_heading_6(self):
        text = "######Title _Italics_"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result = uut.render_poem_for_ebook(mock_path)

        assert result == "<h6>Title <em>Italics</em></h6>\n\n"

    def test_raises_error_on_seven_hashes(self):
        text = "#######Nope"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        with pytest.raises(RuntimeError):
            uut.render_poem_for_ebook(mock_path)

        # Test passes if exception is raised

    def test_wraps_lines_in_divs(self):
        text = "first line\nsecond line\n"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result = uut.render_poem_for_ebook(mock_path)

        assert (
            result
            == '<div class="poem">first line</div>\n'
            + '<div class="poem">second line</div>\n'
        )

    def test_honors_horizontal_rules(self):
        text = "first line\n\n---\n\nsecond line\n"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result = uut.render_poem_for_ebook(mock_path)

        assert (
            result
            == '<div class="poem">first line</div>\n'
            + '<div class="poem">&nbsp;</div>\n'
            + "<hr />\n"
            + '<div class="poem">&nbsp;</div>\n'
            + '<div class="poem">second line</div>\n'
        )

    def test_parses_markdown_in_a_given_line(self):
        text = "_first_ line\n**second** line\n"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result = uut.render_poem_for_ebook(mock_path)

        assert (
            result
            == '<div class="poem"><em>first</em> line</div>\n'
            + '<div class="poem"><strong>second</strong> line</div>\n'
        )

    def test_renders_blank_lines_as_div_with_non_breaking_space(self):
        text = "start line\n\nend line\n"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result = uut.render_poem_for_ebook(mock_path)

        assert (
            result
            == '<div class="poem">start line</div>\n'
            + '<div class="poem">&nbsp;</div>\n'
            + '<div class="poem">end line</div>\n'
        )

    def test_skips_leading_blank_lines(self):
        text = "\n\n\nstart line\nend line\n"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result = uut.render_poem_for_ebook(mock_path)

        assert (
            result
            == '<div class="poem">start line</div>\n'
            + '<div class="poem">end line</div>\n'
        )

    def test_adds_indent_class_on_tabs(self):
        text = "\tIndent one\n\t\tIndent two"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result = uut.render_poem_for_ebook(mock_path)

        assert (
            result
            == '<div class="poem tab1">Indent one</div>\n'
            + '<div class="poem tab2">Indent two</div>\n'
        )

    def test_raises_error_on_six_tabs(self):
        text = "\t\t\t\t\t\tNope"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        with pytest.raises(RuntimeError):
            uut.render_poem_for_ebook(mock_path)

        # Test passes if exception is raised


class TestRenderStoryForWebsite:
    def test_wraps_paragraphs_with_gutenberg_block_tags(self):
        text = "Para 1\n\nPara 2"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result, _, _ = uut.render_story_for_website(mock_path)

        assert result == (
            "<!-- wp:paragraph -->\n"
            "<p>Para 1</p>\n"
            "<!-- /wp:paragraph -->\n\n"
            "<!-- wp:paragraph -->\n"
            "<p>Para 2</p>\n"
            "<!-- /wp:paragraph -->\n\n"
        )

    def test_turns_horizontal_rules_into_scene_break(self):
        text = "----\n"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result, _, _ = uut.render_story_for_website(mock_path)

        assert result == (
            "<!-- wp:separator -->\n"
            '<hr class="wp-block-separator has-alpha-channel=opacity scene-break">\n'
            "<!-- /wp:separator -->\n\n"
        )

    def test_gets_rid_of_headers(self):
        text = "# Title\n\n## By Meeeee!\n\nA paragraph\n"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result, _, _ = uut.render_story_for_website(mock_path)

        assert result == (
            "<!-- wp:paragraph -->\n"
            "<p>A paragraph</p>\n"
            "<!-- /wp:paragraph -->\n\n"
        )

    def test_returns_copyright_year_if_available(self):
        text = "Copyright (c) 2017, N. E. Body\n"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result, _, year = uut.render_story_for_website(mock_path)

        assert result == ""
        assert year == "2017"

    def test_returns_original_publication_if_available(self):
        text = "First published in *Yep That's My Baby* magazine\n"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result, pub, _ = uut.render_story_for_website(mock_path)

        assert result == ""
        assert pub == "<em>Yep That's My Baby</em> magazine"


class TestRenderPoemForWebsite:
    def test_translates_special_characters_to_unicode_but_only_in_the_poem_itself(self):
        text = '# "The Quoted Title"\n\nTo <bracket> a "quote"'
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result = uut.render_poem_for_website(mock_path)

        assert result == (
            '<!-- wp:lazyblock/poem {"poem":"'
            "To \\u003cbracket\\u003e a &quot;quote&quot;\\u003cbr\\u003e"
            '"} /-->'
        )

    def test_adds_arrows_on_tabs(self):
        text = "\tIndent one\n\t\tIndent two"
        mock_path = Mock(read_text=Mock(side_effect=lambda *args, **kwargs: text))

        result = uut.render_poem_for_website(mock_path)

        assert result == (
            '<!-- wp:lazyblock/poem {"poem":"'
            "-\\u003e Indent one\\u003cbr\\u003e"
            "-\\u003e -\\u003e Indent two\\u003cbr\\u003e"
            '"} /-->'
        )


class TestRenderAuthorBioForWebsite:
    def test_bio_strips_para_tags(self):
        md_text = "_This_ is the bio."
        mock_path = Mock()
        mock_path.read_text.return_value = md_text

        result = uut.render_author_bio_for_website(mock_path)

        assert result == "<em>This</em> is the bio."


class TestTitleToSlug:
    def test_lowercases_and_turns_spaces_into_dashes(self):
        # No arrange

        result = uut.title_to_slug("Title to Spaces")

        assert result == "title-to-spaces"

    def test_normalizes_accents(self):
        # No arrange

        result = uut.title_to_slug("Titlé")

        assert result == "title"

    def test_strips_quote_marks(self):
        # No arrange

        result = uut.title_to_slug('Wizard\'s "Rule"')

        assert result == "wizards-rule"

    def test_truncates_slug_to_first_break_before_40_characters(self):
        # No arrange

        result = uut.title_to_slug("123456789 123456789 12 456 89012 4567 9012")

        assert result == "123456789-123456789-12-456-89012-4567"
