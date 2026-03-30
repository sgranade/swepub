import re
from collections.abc import Callable
from contextlib import suppress
from itertools import accumulate
from pathlib import Path

from markdown_it import MarkdownIt

_ebook_md = MarkdownIt("commonmark", {"typographer": True})
_ebook_md.enable(["replacements", "smartquotes"])
_website_md = MarkdownIt("commonmark", {"typographer": True})
_website_md.enable(["replacements"])


def render_story_for_epub(p: Path) -> str:
    """Generate the ePUB HTML for a story.

    :param path: Path to the story's markdown file.
    :return: HTML for the story.
    """
    raw_html = _ebook_md.render(p.read_text(encoding="utf-8"))
    # Change <hr><p> into <p class="noindent"> the funky regex way
    # since lxml's HTML parser requires fragments have a single parent
    # (i.e. lxml wants to wrap the output of md.render() in a single div tag)
    raw_html = re.sub("<hr( /)?>\n*<p>", '<p class="noindent">', raw_html)
    # Also get rid of any leading `\` in paragraphs, which we use to prevent
    # Markdown from generating e.g. `<ol>` from numbered paragraphs
    raw_html = re.sub(r"<p>\\", "<p>", raw_html)

    return raw_html


def _poem_line_to_epub_html(line: str) -> str:
    """Wrap a poem's line in HTML for ePUB.

    :param line: Line from the poem.
    :return: HTML-ized poem line
    """
    classes = "poem"
    if not line.strip():
        # Non-breaking space needed to force ereaders to honor blank lines
        md_line = "&nbsp;"
    else:
        if line.startswith("=>"):
            classes += " rj"
            line = line[2:]
        elif line.startswith("<=>"):
            classes += " cj"
            line = line[3:]
        if line.startswith("\t"):
            cnt = len(re.match("\t+", line).group(0))  # type: ignore
            if cnt > 5:
                raise RuntimeError(f"Too many tabs {cnt} in line {line}")
            classes += f" tab{cnt}"
            line = line[cnt:]
        md_line = _ebook_md.renderInline(line)

    return f'<div class="{classes}">{md_line}</div>\n'


# On the website the poem HTML gets wrapped in a lazyblocks Gutenberg block, which requires
# that < and > get turned into Unicode characters.
poem_trans = str.maketrans({"<": "\\u003c", ">": "\\u003e", '"': "\\u0022"})


def _poem_line_to_website_html(line: str) -> str:
    """Wrap a poem's line in HTML for the website.

    :param line: Line from the poem.
    :return: HTML-ized poem line
    """
    right_justified = False
    center_justified = False
    if line.startswith("=>"):
        right_justified = True
        line = line[2:]
    elif line.startswith("<=>"):
        center_justified = True
        line = line[3:]
    md_line = _website_md.renderInline(line)
    md_line = md_line.replace("\t", "-> ") + "<br>"
    if right_justified:
        md_line = ">" + md_line
    elif center_justified:
        md_line = "<>" + md_line
    return md_line.translate(poem_trans)


def _render_poem(
    p: Path, md: MarkdownIt, poem_line_to_html: Callable[[str], str]
) -> tuple[str, str]:
    """Generate the HTML for a poem.

    :param p: Path to the poem's markdown file.
    :param md: Markdown parsing/rendering object.
    :param poem_line_to_html: Function to turn a single line into HTML.
    :return: HTML for the poem's header and contents in a tuple.
    """
    # Since poems need specialized formatting, we handle them on a line-by-line basis
    header_html = ""
    body_html = ""
    lines = p.read_text(encoding="utf-8").splitlines()
    in_content = False
    for line in lines:
        if not in_content:
            if not line.strip():
                continue
            m = re.match("#+", line)
            if m is None:
                in_content = True
            else:
                hashes = m.group(0)
                cnt = len(hashes)
                if cnt > 6:
                    raise RuntimeError(f"Too many hash marks ({cnt})) in line {line}")
                header_html += f"<h{cnt}>{md.renderInline(line[cnt:])}</h{cnt}>\n\n"
                continue

        # If we have a horizontal rule, honor that. Otherwise, parse the line separately
        md_line = md.render(line)
        if md_line.startswith("<hr />"):
            body_html += md_line
        else:
            body_html += poem_line_to_html(line)

    return header_html, body_html


def render_poem_for_epub(p: Path) -> str:
    """Generate the ePUB HTML for a poem.

    :param p: Path to the poem's markdown file.
    :return: HTML for the poem.
    """
    return "".join(_render_poem(p, _ebook_md, _poem_line_to_epub_html))


def _remove_header_markdown(text: str) -> str:
    """Remove Markdown headers from text."""
    return re.sub("#+[^#].*\n*", "", text)


def render_story_for_website(p: Path) -> tuple[str, str | None, str | None]:
    """Generate the WP website HTML for a story.

    :param p: Path to the story's markdown file.
    :return: Tuple with the story's HTML, the original publication (if any),
    and the original copyright year (if any).
    """
    text = p.read_text(encoding="utf-8")
    copyright_year = None
    orig_publication = None

    # Get rid of any header lines
    text = _remove_header_markdown(text)

    # If the text has "First published in..." at the end, pull that out
    # and extract the year from it
    m = re.search("First published in (.*)\n*", text)
    if m is not None:
        text = text[: m.start()] + text[m.end() :]
        orig_publication = _website_md.renderInline(m.group(1).strip())

    # Do the same for the year
    m = re.search(r"Copyright (\(c\)|©) (\d+).+\n*", text)
    if m is not None:
        text = text[: m.start()] + text[m.end() :]
        copyright_year = m.group(2)

    # Add Gutenberg block wrappers to various tags
    with _website_md.reset_rules():
        _website_md.add_render_rule(
            "paragraph_open", lambda *args, **kwargs: "<!-- wp:paragraph -->\n<p>"
        )
        _website_md.add_render_rule(
            "paragraph_close",
            lambda *args, **kwargs: "</p>\n<!-- /wp:paragraph -->\n\n",
        )
        _website_md.add_render_rule(
            "hr",
            lambda *args, **kwargs: (
                "<!-- wp:separator -->\n"
                '<hr class="wp-block-separator has-alpha-channel=opacity scene-break">\n'
                "<!-- /wp:separator -->\n\n"
            ),
        )

        # We also need to strip `\` from the beginning of paragraphs.
        # We'll do that the regex way
        rendered_text = _website_md.render(text)
        rendered_text = re.sub(r"<p>\\", "<p>", rendered_text)

        return rendered_text, orig_publication, copyright_year


def render_poem_for_website(p: Path) -> str:
    """Generate the WP website HTML for a poem.

    :param p: Path to the poem's markdown file.
    :return: HTML for the poem.
    """
    _, body = _render_poem(p, _website_md, _poem_line_to_website_html)
    return '<!-- wp:lazyblock/poem {"poem":"' + body + '"} /-->'


def render_author_bio_for_website(p: Path) -> str:
    """Read the author bio from its markdown file and return it as HTML."""
    return _website_md.renderInline(p.read_text(encoding="utf-8"))


def title_to_slug(title: str) -> str:
    """Given a title, return a (potentially truncated) slug."""
    title = title.translate(wp_slug_trans)
    # Remove all non-alpha-numeric characters
    title = re.sub("[^- \\w]", "", title)
    split_post_slug = title.lower().split(" ")
    post_slug_lengths = list(accumulate((len(s) + 1 for s in split_post_slug)))
    with suppress(StopIteration):
        max_ndx = next(ndx for ndx, item in enumerate(post_slug_lengths) if item > 40)
        split_post_slug = split_post_slug[:max_ndx]
    return "-".join(split_post_slug).rstrip("-")


# Translation table to match what WordPress uses
wp_slug_trans = str.maketrans(
    {
        "ª": "a",
        "º": "o",
        "À": "A",
        "Á": "A",
        "Â": "A",
        "Ã": "A",
        "Ä": "A",
        "Å": "A",
        "Æ": "AE",
        "Ç": "C",
        "È": "E",
        "É": "E",
        "Ê": "E",
        "Ë": "E",
        "Ì": "I",
        "Í": "I",
        "Î": "I",
        "Ï": "I",
        "Ð": "D",
        "Ñ": "N",
        "Ò": "O",
        "Ó": "O",
        "Ô": "O",
        "Õ": "O",
        "Ö": "O",
        "Ù": "U",
        "Ú": "U",
        "Û": "U",
        "Ü": "U",
        "Ý": "Y",
        "Þ": "TH",
        "ß": "s",
        "à": "a",
        "á": "a",
        "â": "a",
        "ã": "a",
        "ä": "a",
        "å": "a",
        "æ": "ae",
        "ç": "c",
        "è": "e",
        "é": "e",
        "ê": "e",
        "ë": "e",
        "ì": "i",
        "í": "i",
        "î": "i",
        "ï": "i",
        "ð": "d",
        "ñ": "n",
        "ò": "o",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ö": "o",
        "ø": "o",
        "ù": "u",
        "ú": "u",
        "û": "u",
        "ü": "u",
        "ý": "y",
        "þ": "th",
        "ÿ": "y",
        "Ø": "O",
        # Decompositions for Latin Extended-A.
        "Ā": "A",
        "ā": "a",
        "Ă": "A",
        "ă": "a",
        "Ą": "A",
        "ą": "a",
        "Ć": "C",
        "ć": "c",
        "Ĉ": "C",
        "ĉ": "c",
        "Ċ": "C",
        "ċ": "c",
        "Č": "C",
        "č": "c",
        "Ď": "D",
        "ď": "d",
        "Đ": "D",
        "đ": "d",
        "Ē": "E",
        "ē": "e",
        "Ĕ": "E",
        "ĕ": "e",
        "Ė": "E",
        "ė": "e",
        "Ę": "E",
        "ę": "e",
        "Ě": "E",
        "ě": "e",
        "Ĝ": "G",
        "ĝ": "g",
        "Ğ": "G",
        "ğ": "g",
        "Ġ": "G",
        "ġ": "g",
        "Ģ": "G",
        "ģ": "g",
        "Ĥ": "H",
        "ĥ": "h",
        "Ħ": "H",
        "ħ": "h",
        "Ĩ": "I",
        "ĩ": "i",
        "Ī": "I",
        "ī": "i",
        "Ĭ": "I",
        "ĭ": "i",
        "Į": "I",
        "į": "i",
        "İ": "I",
        "ı": "i",
        "Ĳ": "IJ",
        "ĳ": "ij",
        "Ĵ": "J",
        "ĵ": "j",
        "Ķ": "K",
        "ķ": "k",
        "ĸ": "k",
        "Ĺ": "L",
        "ĺ": "l",
        "Ļ": "L",
        "ļ": "l",
        "Ľ": "L",
        "ľ": "l",
        "Ŀ": "L",
        "ŀ": "l",
        "Ł": "L",
        "ł": "l",
        "Ń": "N",
        "ń": "n",
        "Ņ": "N",
        "ņ": "n",
        "Ň": "N",
        "ň": "n",
        "ŉ": "n",
        "Ŋ": "N",
        "ŋ": "n",
        "Ō": "O",
        "ō": "o",
        "Ŏ": "O",
        "ŏ": "o",
        "Ő": "O",
        "ő": "o",
        "Œ": "OE",
        "œ": "oe",
        "Ŕ": "R",
        "ŕ": "r",
        "Ŗ": "R",
        "ŗ": "r",
        "Ř": "R",
        "ř": "r",
        "Ś": "S",
        "ś": "s",
        "Ŝ": "S",
        "ŝ": "s",
        "Ş": "S",
        "ş": "s",
        "Š": "S",
        "š": "s",
        "Ţ": "T",
        "ţ": "t",
        "Ť": "T",
        "ť": "t",
        "Ŧ": "T",
        "ŧ": "t",
        "Ũ": "U",
        "ũ": "u",
        "Ū": "U",
        "ū": "u",
        "Ŭ": "U",
        "ŭ": "u",
        "Ů": "U",
        "ů": "u",
        "Ű": "U",
        "ű": "u",
        "Ų": "U",
        "ų": "u",
        "Ŵ": "W",
        "ŵ": "w",
        "Ŷ": "Y",
        "ŷ": "y",
        "Ÿ": "Y",
        "Ź": "Z",
        "ź": "z",
        "Ż": "Z",
        "ż": "z",
        "Ž": "Z",
        "ž": "z",
        "ſ": "s",
        # Decompositions for Latin Extended-B.
        "Ə": "E",
        "ǝ": "e",
        "Ș": "S",
        "ș": "s",
        "Ț": "T",
        "ț": "t",
        # Euro sign.
        "€": "E",
        # GBP (Pound) sign.
        "£": "",
        # Vowels with diacritic (Vietnamese). Unmarked.
        "Ơ": "O",
        "ơ": "o",
        "Ư": "U",
        "ư": "u",
        # Grave accent.
        "Ầ": "A",
        "ầ": "a",
        "Ằ": "A",
        "ằ": "a",
        "Ề": "E",
        "ề": "e",
        "Ồ": "O",
        "ồ": "o",
        "Ờ": "O",
        "ờ": "o",
        "Ừ": "U",
        "ừ": "u",
        "Ỳ": "Y",
        "ỳ": "y",
        # Hook.
        "Ả": "A",
        "ả": "a",
        "Ẩ": "A",
        "ẩ": "a",
        "Ẳ": "A",
        "ẳ": "a",
        "Ẻ": "E",
        "ẻ": "e",
        "Ể": "E",
        "ể": "e",
        "Ỉ": "I",
        "ỉ": "i",
        "Ỏ": "O",
        "ỏ": "o",
        "Ổ": "O",
        "ổ": "o",
        "Ở": "O",
        "ở": "o",
        "Ủ": "U",
        "ủ": "u",
        "Ử": "U",
        "ử": "u",
        "Ỷ": "Y",
        "ỷ": "y",
        # Tilde.
        "Ẫ": "A",
        "ẫ": "a",
        "Ẵ": "A",
        "ẵ": "a",
        "Ẽ": "E",
        "ẽ": "e",
        "Ễ": "E",
        "ễ": "e",
        "Ỗ": "O",
        "ỗ": "o",
        "Ỡ": "O",
        "ỡ": "o",
        "Ữ": "U",
        "ữ": "u",
        "Ỹ": "Y",
        "ỹ": "y",
        # Acute accent.
        "Ấ": "A",
        "ấ": "a",
        "Ắ": "A",
        "ắ": "a",
        "Ế": "E",
        "ế": "e",
        "Ố": "O",
        "ố": "o",
        "Ớ": "O",
        "ớ": "o",
        "Ứ": "U",
        "ứ": "u",
        # Dot below.
        "Ạ": "A",
        "ạ": "a",
        "Ậ": "A",
        "ậ": "a",
        "Ặ": "A",
        "ặ": "a",
        "Ẹ": "E",
        "ẹ": "e",
        "Ệ": "E",
        "ệ": "e",
        "Ị": "I",
        "ị": "i",
        "Ọ": "O",
        "ọ": "o",
        "Ộ": "O",
        "ộ": "o",
        "Ợ": "O",
        "ợ": "o",
        "Ụ": "U",
        "ụ": "u",
        "Ự": "U",
        "ự": "u",
        "Ỵ": "Y",
        "ỵ": "y",
        # Vowels with diacritic (Chinese, Hanyu Pinyin).
        "ɑ": "a",
        # Macron.
        "Ǖ": "U",
        "ǖ": "u",
        # Acute accent.
        "Ǘ": "U",
        "ǘ": "u",
        # Caron.
        "Ǎ": "A",
        "ǎ": "a",
        "Ǐ": "I",
        "ǐ": "i",
        "Ǒ": "O",
        "ǒ": "o",
        "Ǔ": "U",
        "ǔ": "u",
        "Ǚ": "U",
        "ǚ": "u",
        # Grave accent.
        "Ǜ": "U",
        "ǜ": "u",
    }
)
