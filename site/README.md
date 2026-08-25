# The Anvil landing page

One hand-written, self-contained `index.html` plus pre-rendered assets. No build step — what's here is what ships.

## Preview locally

Open `index.html` in a browser. That's it.

## Screenshot it

`shoot.mjs` drives Playwright (channel: `chrome`) — it scrolls the page like a
reader so the scroll-reveal animations fire, then captures:

```sh
# from ../shotgun/site, which has playwright installed:
node anvil-shoot.mjs --out /tmp/hero.png --sel "#masthead"
node anvil-shoot.mjs --out /tmp/full.png --full
node anvil-shoot.mjs --out /tmp/mobile.png --width 420
```

## Deploy

Push to `main` — `.github/workflows/pages.yml` publishes `index.html` +
`assets/` to GitHub Pages. Requires Pages to be enabled with **Source:
GitHub Actions** (repo settings → Pages).
