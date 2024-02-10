import re
from pathlib import Path

from markdown_it import MarkdownIt

_ebook_md = MarkdownIt("commonmark", {"typographer": True})
_ebook_md.enable(["replacements", "smartquotes"])


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


def render_poem_for_ebook(p: Path):
    """Generate the HTML for a poem.

    :param p: Path to the poem's markdown file.
    :return: HTML for the poem.
    """
    # Since poems need specialized formatting, we handle them on a line-by-line basis
    html = ""
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
                html += f"<h{cnt}>{_ebook_md.renderInline(line[cnt:])}</h{cnt}>\n\n"
                continue

        # If we have a horizontal rule, honor that. Otherwise, parse the line separately
        md_line = _ebook_md.render(line)
        if md_line.startswith("<hr />"):
            html += md_line
        else:
            html += _poem_line_to_ebook_html(line)

    return html


def render_story_for_website(p: Path):
    raise NotImplementedError


def render_poem_for_website(p: Path):
    raise NotImplementedError
