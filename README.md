# Epub Generation for Small Wonders Magazine

Being a collection of scripts to create an epub version of Small Wonders Magazine.

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

## Building the Epub File

To build the epub file, in the repository, run the command

```bash
python build_ebook.py
```

The epub file will be named `Small Wonders Magazine Issue <#>.epub`.