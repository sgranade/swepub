# Issue Generation for Small Wonders Magazine

Being a collection of scripts to create an issue of Small Wonders Magazine: post the pieces to the WordPress website, and create both the ePUB and PDF versions of the magazine.

## Installing

The scripts are written in Python maganed by [uv](https://github.com/astral-sh/uv). Install uv and you should be good to go, unless you're on Windows.

> [!IMPORTANT]
> The scripts use the [WeasyPrint](https://weasyprint.org/) PDF-writing package. If you're on Windows, there's a few more steps you need to take.

On Windows, install [MSYS2](https://www.msys2.org/), open the MSYS2 window, and run the following command:

```bash
pacman -S mingw-w64-x86_64-pango mingw-w64-x86_64-gdk-pixbuf2 mingw-w64-x86_64-libffi mingw-w64-x86_64-zlib
```

Once that's done, add `C:\msys64\mingw64\bin` to your Windows PATH.

## Input Structure

The scripts pull files from two sub-directories, `content` and `images`. `content` contains the stuff inside the magazine, while `images` contains the cover and author headshots or avatars.

```
├── content
│   ├── 0a-about.md          # Front matter about the current issue
│   ├── 0b-cover-artist.md   # Cover artist bio
│   ├── 0c-keyhole.md        # Thru the Keyhole editorial
│   ├── 1a-story.md          # 1st piece (story)
│   ├── 1b-author.md         # 1st piece author bio
│   ├── 2a-poem.md           # 2nd piece (poem)
│   ├── 2b-author.md         # 2nd piece author bio
│   ├── 3a-reprint.md        # 3rd piece (reprint)
│   ├── 3b-author.md         # 3rd piece author bio
│   ├── 4a-story.md
│   ├── 4b-author.md
│   ├── 5a-poem.md
│   ├── 5b-author.md
│   ├── 6a-reprint.md
│   ├── 6b-author.md
│   ├── 7a-story.md
│   ├── 7b-author.md
│   ├── 8a-poem.md
│   ├── 8b-author.md
│   ├── 9a-story.md
│   ├── 9b-reprint.md
│   ├── description.html     # 1-paragraph description of the issue
│   └── editors.txt          # Current editors' names, one per line
└── images
    ├── 1-author.jpg         # 1st piece author headshot/avatar
    ├── 2-author.jpg
    ├── 3-author.jpg
    ├── 4-author.jpg
    ├── 5-author.jpg
    ├── 6-author.jpg
    ├── 7-author.jpg
    ├── 8-author.jpg
    └── 9-author.jpg
```

## Content Files

All content Markdown files **other than author bio ones** should start with a `#` heading that describes that file.

`about.md` should include `Issue <#>` in its contents, where `<#>` is the current issue number.

All pieces, whether story, poem, or reprint, should start with the piece's title and authorship.

```markdown
# <Title>

## by <Author Name>
```

Reprints should end with the copyright statement dated the year of its first publication and an attribution for where it was first published, each in its own paragraph.

```markdown
Copyright (c) <YYYY> by <Author Name>

First published in <Publication>
```

`description.html` should be a one-paragraph description of the current issue contained in a paragraph tag.

```html
<p><em>Small Wonders</em> is a magazine of speculative flash fiction and poetry. Issue [#] ([Month YYYY]) contains: </p>
<p>
  <ul>
    <li>"[First Title]" by [Author] (fiction)</li>
    <li>"[Second Title]" by [Author] (poem)</li>
    <li>"[Third Title]" by [Author] (fiction)</li>
    ...
  </ul>
</p>
```

`editors.txt` contain the editors' names, one per line.

```text
[Editor 1]
[Editor 2]
```

### Changes From Standard Markdown

#### Stories

Any `\` at the beginning of a paragraph will be stripped from the output. This allows us to create numbered paragraphs that aren't turned into HTML ordered lists:

```markdown
\1. This paragraph won't turn into an ordered list.

\2. Neither will this.
```

#### Poems

To indent a line, use tabs. Each tab indents the poetry line by 2 em units.

To center justify a line, put `<=>` at its start. To right justify, put `=>` at its start.

## Uploading the Pieces

To upload pieces to the WordPress site, create an `issue_config.toml` file in the script's directories. Its contents are:

```toml
host = "<url to the WordPress site>"
username = "<your WordPress username>"
password = "<your application password>"
use_2fa = true
```

You'll need to activate two-factor authentication on your WordPress account and then generate the [application password](https://wordpress.com/support/security/two-step-authentication/application-specific-passwords/) to add to the TOML file.

Once that's set up, run `uv run python post_issue.py`.

## Building the Ebooks

To build the ePUB and PDF files, in the repository, run the command

```bash
uv run python build_ebook.py
```

The ebook files will be named `Small Wonders Magazine Issue <#>.epub` and `.pdf`.