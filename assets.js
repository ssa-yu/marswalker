// SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
/* Where the large static files come from (map library, HiRISE tiles, grids, 3D textures).
   On the public site (github.io) they are read from jsDelivr's copy of this repository's gh-pages commit below
   (tag site-assets-1): GitHub Pages delivered about 90 KB/s on the team's connection on 2026-11-15, jsDelivr 4-9x
   that, and the 3D walk alone needs 4 MB. Same files, same commit; nothing else is sent anywhere.
   Local / other hosts: same origin. ?cdn forces the CDN, ?nocdn forces same origin. If the CDN cannot be reached the
   pages fall back to same origin. After changing anything under web/data/ or web/lib/: tag the new gh-pages commit
   and put its hash here. */
window.ASSET_COMMIT = '493601d51bb4038be77f963081f75e7b38419b5d';
window.ASSET = (/\.github\.io$/.test(location.hostname) || /[?&]cdn\b/.test(location.search)) && !/[?&]nocdn\b/.test(location.search)
  ? 'https://cdn.jsdelivr.net/gh/ssa-yu/marswalker@' + window.ASSET_COMMIT + '/' : '';
