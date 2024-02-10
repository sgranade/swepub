import re
from collections.abc import Callable
from pathlib import Path

from markdown_it import MarkdownIt

_ebook_md = MarkdownIt("commonmark", {"typographer": True})
_ebook_md.enable(["replacements", "smartquotes"])
_website_md = MarkdownIt("commonmark", {"typographer": True})
_website_md.enable(["replacements"])


def render_story_for_ebook(p: Path):
    """Generate the HTML for a story.

    :param path: Path to the story's markdown file.
    :return: HTML for the story.
    """
    raw_html = _ebook_md.render(p.read_text(encoding="utf-8"))
    # Change <hr><p> into <p class="noindent"> the funky regex way
    # since lxml's HTML parser requires fragments have a single parent
    # (i.e. lxml wants to wrap the output of md.render() in a single div tag)
    raw_html = re.sub("<hr( /)?>\n*<p>", '<p class="noindent">', raw_html)

    return raw_html


def _poem_line_to_ebook_html(line: str) -> str:
    """Wrap a poem's line in HTML for an ebook.

    :param line: Line from the poem.
    :return: HTML-ized poem line
    """
    classes = "poem"
    if not line.strip():
        # Non-breaking space needed to force ereaders to honor blank lines
        md_line = "&nbsp;"
    else:
        if line.startswith("\t"):
            cnt = len(re.match("\t+", line).group(0))
            if cnt > 4:
                raise RuntimeError(f"Too many tabs {cnt} in line {line}")
            classes += f" tab{cnt}"
            line = line[cnt:]
        md_line = _ebook_md.renderInline(line)

    return f'<div class="{classes}">{md_line}</div>\n'


# The poem HTML gets wrapped in a lazyblocks Gutenberg block, which requires that < and >
# get turned into Unicode characters.
poem_trans = str.maketrans({"<": "\\u003c", ">": "\\u003e", '"': "\\u0022"})


def _poem_line_to_website_html(line: str) -> str:
    """Wrap a poem's line in HTML for the website.

    :param line: Line from the poem.
    :return: HTML-ized poem line
    """
    md_line = _website_md.renderInline(line)
    md_line = md_line.replace("\t", "-> ") + "<br>"
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


def render_poem_for_ebook(p: Path):
    """Generate the HTML for a poem.

    :param p: Path to the poem's markdown file.
    :return: HTML for the poem.
    """
    return "".join(_render_poem(p, _ebook_md, _poem_line_to_ebook_html))


def render_story_for_website(p: Path):
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
            "hr", lambda *args, **kwargs: '<hr class="scene-break">\n\n'
        )
        return _website_md.render(p.read_text(encoding="utf-8"))


def render_poem_for_website(p: Path):
    header, body = _render_poem(p, _website_md, _poem_line_to_website_html)
    return header + '<!-- wp:lazyblock/poem {"poem":"' + body + '"} /-->'


def render_author_bio_for_website(p: Path) -> str:
    """Read the author bio from its markdown file and return it as HTML."""
    return _website_md.renderInline(p.read_text(encoding="utf-8"))
