# Blog workflow

## Build and serve

1. Build from Markdown:

   ```bash
   python3 build.py
   ```

2. Optional: auto-rebuild on save (native, no install needed):

   ```bash
   python3 -u build.py --watch
   ```

3. Run a local server:

   ```bash
   python3 -m http.server 8000
   ```

4. Open `http://localhost:8000/`.

Notes:
- `index.html` and each `post.html` are generated files. Edit sources, then rerun `python3 build.py`.
- `python3 -u build.py --watch` rebuilds whenever `posts/**/post.md` or `site.json` changes.
- You can also use `watchexec`/`fswatch` via Homebrew if preferred, but they are optional.
- Site header/banner text is configured in `site.json`.

## Post format

Each post lives at `posts/tab1/<slug>/post.md` or `posts/tab2/<slug>/post.md`.

Top metadata block must include:

```md
title: Your Title
date: February 26, 2026
done: true
references: [https://example.com/paper, https://example.com/video]

Your Markdown starts here.
```

Rules:
- `done: true` publishes the post and includes it on the home page.
- `done: false` removes `post.html` and hides the post from the home page.
- `title` and `date` are used on the post page and card listing.
- `references` is rendered at the bottom as an ordered "References" section.

## Math and embeds

- Inline math: `$...$`
- Display math: `$$...$$`
- Images: `![alt](assets/image.png)`
- Videos/iframes: use raw HTML blocks directly in Markdown.
