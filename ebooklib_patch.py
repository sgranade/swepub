import os
from contextlib import suppress
from pathlib import Path

import ebooklib
from ebooklib import epub
from ebooklib.epub import (
    NAMESPACES,
    EpubHtml,
    EpubNav,
    Link,
    Section,
    get_pages_for_items,
    parse_string,
)
from lxml import etree, html
from PIL import Image

if epub.VERSION != (0, 20, 0):
    raise ImportWarning(f"Expected ebooklib version (0, 20, 0) but got {epub.VERSION}")


def _append_html_as_elements(parent, html_text) -> None:
    """Appends HTML as rendered elements to the parent element.

    :param parent: Parent element.
    :param html_text: HTML to append to the element.
    """
    # Wrap so fragment_fromstring() always has a single root.
    wrapper = html.fragment_fromstring(
        f"<span>{html_text}</span>",
        create_parent=False,
    )

    parent.text = wrapper.text

    for child in wrapper:
        parent.append(child)


def _strip_html_markup(html_text: str) -> str:
    """Strip the HTML markup from a string."""
    return html.fragment_fromstring(
        f"<span>{html_text}</span>",
        create_parent=False,
    ).text_content()


# Adapted from the ebooklib class so I could tweak it -- the existing class lower-cases all
# xml attributes, which wrecks the viewBox attribute
class SWEpubCoverHtml(epub.EpubHtml):
    def __init__(
        self, uid="cover", file_name="cover.xhtml", image_name="", title="Cover"
    ):
        super(SWEpubCoverHtml, self).__init__(uid=uid, file_name=file_name, title=title)

        self.image_name = image_name
        # Changing is_linear so the cover shows up at the start of the
        # ebook instead of at the end
        # self.is_linear = False
        self.is_linear = True

    def is_chapter(self):
        return False

    def set_content(self, cover_path):
        self.content = self._get_cover_html_content(cover_path)

    def get_content(self):
        return self.content

    def _get_cover_html_content(self, cover_path: Path) -> bytes:
        with Image.open(cover_path) as img:
            cover_width, cover_height = img.size

        return (
            """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">
 <head>
  <style>
    body { margin: 0em; padding: 0em; }
    img { max-width: 100%; max-height: 100%; }
  </style>
 </head>
 <body>
   <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
   height="100%" width="100%" viewBox="0 0 """
            + f"{cover_width} {cover_height}"
            + '''" preserveAspectRatio="xMidYMid meet" version="1.1">
     <image href="'''
            + self.image_name
            + """" alt="Cover art"/></svg>
 </body>
</html>"""
        ).encode()

    def __str__(self):
        return "<EpubCoverHtml:%s:%s>" % (self.id, self.file_name)


class SWEpubWriter(epub.EpubWriter):
    """Adaption of the base class to tweak its output."""

    def _get_nav(self, item):
        # just a basic navigation for now
        nav_xml = parse_string(self.book.get_template("nav"))
        root = nav_xml.getroot()

        root.set("lang", self.book.language)
        root.attrib["{%s}lang" % NAMESPACES["XML"]] = self.book.language

        nav_dir_name = os.path.dirname(item.file_name)

        head = etree.SubElement(root, "head")
        title = etree.SubElement(head, "title")
        _append_html_as_elements(title, item.title or self.book.title)

        # for now this just handles css files and ignores others
        for _link in item.links:
            _lnk = etree.SubElement(
                head,
                "link",
                {
                    "href": _link.get("href", ""),
                    "rel": "stylesheet",
                    "type": "text/css",
                },
            )

        body = etree.SubElement(root, "body")
        nav = etree.SubElement(
            body,
            "nav",
            {
                "{%s}type" % NAMESPACES["EPUB"]: "toc",
                "id": "id",
                "role": "doc-toc",
            },
        )

        content_title = etree.SubElement(nav, "h2")
        content_title.text = item.title or self.book.title

        def _create_toc_section(itm, items):
            """SRG Creates a table of contents with links in paragraphs instead of ordered lists"""
            # Note that titles are HTML as rendered from Markdown, and so shouldn't
            # be escaped. To prevent that, we'll append titles as lxml-rendered elements
            div = etree.SubElement(itm, "div", {"class": "toc"})
            for item in items:
                p = etree.SubElement(div, "p")
                if isinstance(item, tuple) or isinstance(item, list):
                    raise NotImplementedError(
                        "I haven't implemented lists for Table of Contents"
                    )
                elif isinstance(item, Link):
                    a = etree.SubElement(
                        itm, "a", {"href": os.path.relpath(item.href, nav_dir_name)}
                    )
                    _append_html_as_elements(a, item.title)
                elif isinstance(item, EpubHtml):
                    a = etree.SubElement(
                        p, "a", {"href": os.path.relpath(item.file_name, nav_dir_name)}
                    )
                    _append_html_as_elements(a, item.title)

        def _create_section(itm, items):
            """SRG Left in, but not used in this implementation"""
            ol = etree.SubElement(itm, "ol")
            for item in items:
                if isinstance(item, tuple) or isinstance(item, list):
                    li = etree.SubElement(ol, "li")
                    if isinstance(item[0], EpubHtml):
                        a = etree.SubElement(
                            li,
                            "a",
                            {"href": os.path.relpath(item[0].file_name, nav_dir_name)},
                        )
                    elif isinstance(item[0], Section) and item[0].href != "":
                        a = etree.SubElement(
                            li,
                            "a",
                            {"href": os.path.relpath(item[0].href, nav_dir_name)},
                        )
                    elif isinstance(item[0], Link):
                        a = etree.SubElement(
                            li,
                            "a",
                            {"href": os.path.relpath(item[0].href, nav_dir_name)},
                        )
                    else:
                        a = etree.SubElement(li, "span")
                    _append_html_as_elements(a, item[0].title)

                    _create_section(li, item[1])

                elif isinstance(item, Link):
                    li = etree.SubElement(ol, "li")
                    a = etree.SubElement(
                        li, "a", {"href": os.path.relpath(item.href, nav_dir_name)}
                    )
                    _append_html_as_elements(a, item.title)
                elif isinstance(item, EpubHtml):
                    li = etree.SubElement(ol, "li")
                    a = etree.SubElement(
                        li, "a", {"href": os.path.relpath(item.file_name, nav_dir_name)}
                    )
                    _append_html_as_elements(a, item.title)

        _create_toc_section(nav, self.book.toc)  # SRG to get rid of the ordered list

        # LANDMARKS / GUIDE
        # - http://www.idpf.org/epub/30/spec/epub30-contentdocs.html#sec-xhtml-nav-def-types-landmarks

        if len(self.book.guide) > 0 and self.options.get("epub3_landmark"):
            # Epub2 guide types do not map completely to epub3 landmark types.
            guide_to_landscape_map = {"notes": "rearnotes", "text": "bodymatter"}

            guide_nav = etree.SubElement(
                body, "nav", {"{%s}type" % NAMESPACES["EPUB"]: "landmarks"}
            )

            guide_content_title = etree.SubElement(guide_nav, "h2")
            guide_content_title.text = self.options.get("landmark_title", "Guide")

            guild_ol = etree.SubElement(guide_nav, "ol")

            for elem in self.book.guide:
                li_item = etree.SubElement(guild_ol, "li")

                if "item" in elem:
                    chap = elem.get("item", None)
                    if chap:
                        _href = chap.file_name
                        _title = chap.title
                else:
                    _href = elem.get("href", "")
                    _title = elem.get("title", "")

                guide_type = elem.get("type", "")
                a_item = etree.SubElement(
                    li_item,
                    "a",
                    {
                        "{%s}type" % NAMESPACES["EPUB"]: guide_to_landscape_map.get(
                            guide_type, guide_type
                        ),
                        "href": os.path.relpath(_href, nav_dir_name),
                    },
                )
                a_item.text = _title

        # PAGE-LIST
        if self.options.get("epub3_pages"):
            inserted_pages = get_pages_for_items(
                [
                    item
                    for item in self.book.get_items_of_type(ebooklib.ITEM_DOCUMENT)
                    if not isinstance(item, EpubNav)
                ]
            )

            if len(inserted_pages) > 0:
                pagelist_nav = etree.SubElement(
                    body,
                    "nav",
                    {
                        "{%s}type" % NAMESPACES["EPUB"]: "page-list",
                        "id": "pages",
                        "hidden": "hidden",
                    },
                )
                pagelist_content_title = etree.SubElement(pagelist_nav, "h2")
                pagelist_content_title.text = self.options.get("pages_title", "Pages")

                pages_ol = etree.SubElement(pagelist_nav, "ol")

                for filename, pageref, label in inserted_pages:
                    li_item = etree.SubElement(pages_ol, "li")

                    _href = "{}#{}".format(filename, pageref)
                    _title = label

                    a_item = etree.SubElement(
                        li_item,
                        "a",
                        {
                            "href": os.path.relpath(_href, nav_dir_name),
                        },
                    )
                    a_item.text = _title

        tree_str = etree.tostring(
            nav_xml, pretty_print=True, encoding="utf-8", xml_declaration=True
        )

        return tree_str

    def _get_ncx(self):

        # we should be able to setup language for NCX as also
        ncx = parse_string(self.book.get_template("ncx"))
        root = ncx.getroot()

        head = etree.SubElement(root, "head")

        # get this id
        uid = etree.SubElement(
            head, "meta", {"content": self.book.uid, "name": "dtb:uid"}
        )
        uid = etree.SubElement(head, "meta", {"content": "0", "name": "dtb:depth"})
        uid = etree.SubElement(
            head, "meta", {"content": "0", "name": "dtb:totalPageCount"}
        )
        uid = etree.SubElement(
            head, "meta", {"content": "0", "name": "dtb:maxPageNumber"}
        )

        doc_title = etree.SubElement(root, "docTitle")
        title = etree.SubElement(doc_title, "text")
        title.text = self.book.title

        #        doc_author = etree.SubElement(root, 'docAuthor')
        #        author = etree.SubElement(doc_author, 'text')
        #        author.text = 'Name of the person'

        # For now just make a very simple navMap
        nav_map = etree.SubElement(root, "navMap")

        def _add_play_order(nav_point):
            nav_point.set("playOrder", str(self._play_order["start_from"]))
            self._play_order["start_from"] += 1

        def _create_section(itm, items, uid):
            for item in items:
                if isinstance(item, tuple) or isinstance(item, list):
                    section, subsection = item[0], item[1]

                    np = etree.SubElement(
                        itm,
                        "navPoint",
                        {
                            "id": section.get_id()
                            if isinstance(section, EpubHtml)
                            else "sep_%d" % uid
                        },
                    )

                    if self._play_order["enabled"]:
                        _add_play_order(np)

                    nl = etree.SubElement(np, "navLabel")
                    nt = etree.SubElement(nl, "text")
                    # SRG: Strip out any HTML in the title
                    nt.text = _strip_html_markup(section.title)

                    # CAN NOT HAVE EMPTY SRC HERE
                    href = ""
                    if isinstance(section, EpubHtml):
                        href = section.file_name
                    elif isinstance(section, Section) and section.href != "":
                        href = section.href
                    elif isinstance(section, Link):
                        href = section.href

                    nc = etree.SubElement(np, "content", {"src": href})

                    uid = _create_section(np, subsection, uid + 1)
                elif isinstance(item, Link):
                    _parent = itm
                    _content = _parent.find("content")

                    if _content is not None:
                        if _content.get("src") == "":
                            _content.set("src", item.href)

                    np = etree.SubElement(itm, "navPoint", {"id": item.uid})

                    if self._play_order["enabled"]:
                        _add_play_order(np)

                    nl = etree.SubElement(np, "navLabel")
                    nt = etree.SubElement(nl, "text")
                    nt.text = _strip_html_markup(item.title)

                    nc = etree.SubElement(np, "content", {"src": item.href})
                elif isinstance(item, EpubHtml):
                    _parent = itm
                    _content = _parent.find("content")

                    if _content is not None:
                        if _content.get("src") == "":
                            _content.set("src", item.file_name)

                    np = etree.SubElement(itm, "navPoint", {"id": item.get_id()})

                    if self._play_order["enabled"]:
                        _add_play_order(np)

                    nl = etree.SubElement(np, "navLabel")
                    nt = etree.SubElement(nl, "text")
                    nt.text = _strip_html_markup(item.title)

                    nc = etree.SubElement(np, "content", {"src": item.file_name})

            return uid

        _create_section(nav_map, self.book.toc, 0)

        tree_str = etree.tostring(
            root, pretty_print=True, encoding="utf-8", xml_declaration=True
        )

        return tree_str


def write_epub(name, book, options=None):
    """
    Creates epub file with the content defined in EpubBook.

    >>> ebooklib.write_epub('book.epub', book)

    :Args:
      - name: file name for the output file
      - book: instance of EpubBook
      - options: extra opions as dictionary (optional)
    """
    epub = SWEpubWriter(name, book, options)

    epub.process()

    with suppress(IOError):
        epub.write()
