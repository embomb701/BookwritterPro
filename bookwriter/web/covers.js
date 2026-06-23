/* ===========================================================================
   Bookwriter Pro — procedural book covers (covers.js)
   --------------------------------------------------------------------------
   A deterministic, self-contained cover generator. Given a stable seed (the
   book id, plus title/genre for flavour) it renders a real-looking book cover
   as an inline SVG string: a tasteful color field from a *curated* palette set
   (never random garish), the title set in the serif display face with proper
   hierarchy, a small "BOOKWRITERPRO" imprint, a subtle grain/foil/spine
   treatment, and a genre-appropriate motif.

   Same seed -> same cover, stable across reloads. No network, no deps.

   Public API (attached to window.Covers):
     Covers.svg(book, opts)      -> SVG markup string for a single cover
     Covers.spineSvg(book)       -> a thin vertical spine SVG (for shelves)
     Covers.paletteFor(book)     -> the chosen palette object (debug/inspect)
   where `book` is any object with at least { id }, ideally { id, title,
   genre, logline }.
   =========================================================================== */
(function () {
  "use strict";

  /* ---------------------------- seeded PRNG ------------------------------ */
  // FNV-1a-ish string hash -> uint32 seed (stable, fast, no deps).
  function hashStr(str) {
    str = String(str == null ? "" : str);
    let h = 0x811c9dc5;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
    }
    return h >>> 0;
  }
  // mulberry32 — small, fast, deterministic PRNG.
  function rng(seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0; a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  /* --------------------------- curated palettes -------------------------- */
  // Each palette: a tasteful pairing for a cloth-bound / dust-jacket look.
  //   bg   — deep field colour
  //   bg2  — gradient companion (usually a touch darker/shifted)
  //   ink  — title colour on the field (light, high contrast)
  //   foil — accent for rules, motif, imprint (metallic feel)
  //   sub  — muted secondary text colour
  const PALETTES = [
    { name: "oxblood",   bg: "#5c1a1b", bg2: "#380f10", ink: "#f4e6d2", foil: "#d9a441", sub: "#c79a7e" },
    { name: "midnight",  bg: "#15233f", bg2: "#0a1426", ink: "#e7ecf6", foil: "#b9c6e8", sub: "#8ea0c4" },
    { name: "forest",    bg: "#1c3a2e", bg2: "#0f2219", ink: "#eef0e2", foil: "#cda85a", sub: "#9bb39c" },
    { name: "plum",      bg: "#3a1f4d", bg2: "#22112f", ink: "#f1e6f3", foil: "#d9a441", sub: "#b89fc4" },
    { name: "ember",     bg: "#7a2414", bg2: "#48140a", ink: "#fbe9d6", foil: "#f0b34a", sub: "#d99a78" },
    { name: "slate",     bg: "#2b2f36", bg2: "#171a1f", ink: "#eef1f4", foil: "#c7ccd4", sub: "#9aa1ab" },
    { name: "teal",      bg: "#0f3b40", bg2: "#072225", ink: "#e6f2f0", foil: "#e0b35a", sub: "#86b3b0" },
    { name: "sand",      bg: "#7c5a2e", bg2: "#4f3819", ink: "#fcf3e2", foil: "#f3d9a8", sub: "#d8bd92" },
    { name: "ink",       bg: "#1a1816", bg2: "#0c0b0a", ink: "#f0e7d8", foil: "#c0392b", sub: "#a89a86" },
    { name: "indigo",    bg: "#241a52", bg2: "#140d31", ink: "#e9e6f7", foil: "#cdb3f0", sub: "#9d96c8" },
    { name: "rose",      bg: "#6b2440", bg2: "#3f1326", ink: "#f7e6ec", foil: "#e6b86a", sub: "#cf99ad" },
    { name: "copper",    bg: "#5a2c1a", bg2: "#33180e", ink: "#f6e7d4", foil: "#e8a857", sub: "#c79877" },
  ];

  /* --------------------------- genre -> motif ---------------------------- */
  // Map a freeform genre string to a motif key + a palette bias. Motifs are
  // drawn as small, abstract SVG glyphs — evocative, never literal clip-art.
  function classifyGenre(genre) {
    const g = String(genre || "").toLowerCase();
    const has = (re) => re.test(g);
    // Romance (incl. erotica/paranormal-romance) — check before horror/fantasy so
    // "paranormal romance"/"steamy" land on the romance motif, not moon/spire.
    if (has(/romance|romantic|love|cozy|heart|relationship|erotic|steamy|sensual|lgbtq|sapphic|mm |rom-?com/)) return { motif: "bloom", bias: ["rose", "sand", "copper", "plum"] };
    if (has(/horror|gothic|dark|gritty|haunt|terror|macabre|supernatural|paranormal|occult|witch|vampire|demon|ghost/)) return { motif: "moon", bias: ["ink", "oxblood", "plum", "ember"] };
    if (has(/myster|crime|noir|detective|thriller|suspense|spy|psychological/)) return { motif: "key", bias: ["slate", "midnight", "ink", "teal", "copper"] };
    if (has(/sci|space|future|cyber|tech|dystop|apocalyp|alien|steampunk/)) return { motif: "orbit", bias: ["midnight", "indigo", "teal", "slate"] };
    if (has(/fantas|myth|magic|epic|dragon|sword|saga|urban fantasy/)) return { motif: "spire", bias: ["forest", "plum", "indigo", "ember"] };
    if (has(/histor|war|classic|literary|drama/))        return { motif: "rule",   bias: ["oxblood", "sand", "copper"] };
    if (has(/adventur|action|quest|journey|explor|sea|ocean/)) return { motif: "compass", bias: ["teal", "midnight", "forest"] };
    if (has(/poet|verse|essay|memoir|biograph|auto/))    return { motif: "quill",  bias: ["sand", "ember", "rose"] };
    // Nonfiction / how-to / business / self-help / cookbook -> a clean ruled mark.
    if (has(/cook|recipe|how.?to|guide|manual|business|self.?help|nonfiction|reference|textbook|educational|personal development/)) return { motif: "rule", bias: ["sand", "slate", "copper"] };
    return { motif: "diamond", bias: ["oxblood", "midnight", "forest", "ember"] };
  }

  function paletteFor(book, opts) {
    // Seed precedence (all backward-compatible — default behaviour unchanged):
    //   1. an explicit opts.seed (lets the Live Cover Forge pin a STABLE palette
    //      + archetype for a whole composer session while the title is typed),
    //   2. otherwise the book id ^ title hash (the original, deterministic seed).
    const override = opts && opts.seed != null;
    const seed = override
      ? (hashStr(opts.seed) >>> 0)
      : (hashStr((book && book.id) || "") ^ hashStr((book && book.title) || ""));
    const r = rng(seed >>> 0);
    const cls = classifyGenre(book && book.genre);
    // Prefer a biased palette for the genre, but let the seed pick among them
    // (and occasionally stray) so two same-genre books still differ.
    let pool = cls.bias.map((n) => PALETTES.find((p) => p.name === n)).filter(Boolean);
    // Stray to the full curated palette set fairly often so a shelf shows real
    // colour range (not a monochrome run) even when several books share a
    // dark-leaning genre; the genre bias still shapes the common case.
    if (!pool.length || r() < 0.42) pool = PALETTES;
    const pal = pool[Math.floor(r() * pool.length) % pool.length];
    return { pal, motif: cls.motif, seed: seed >>> 0 };
  }

  /* ------------------------------ utilities ------------------------------ */
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // Hard-break a single token that is wider than `maxChars` (no whitespace to
  // wrap on, e.g. "Untranslatable" / "Lighthouse-keeper"). Prefer breaking on a
  // hyphen; otherwise split the run into near-equal chunks.
  function breakLongWord(word, maxChars) {
    if (word.length <= maxChars) return [word];
    // Prefer an existing hyphen split if both halves fit better.
    const hy = word.indexOf("-");
    if (hy > 0 && hy < word.length - 1) {
      const a = word.slice(0, hy + 1), b = word.slice(hy + 1);
      return breakLongWord(a, maxChars).concat(breakLongWord(b, maxChars));
    }
    const parts = Math.ceil(word.length / maxChars);
    const per = Math.ceil(word.length / parts);
    const out = [];
    for (let i = 0; i < word.length; i += per) out.push(word.slice(i, i + per));
    return out;
  }

  // Break a title into balanced lines (max 4) for the cover plate. `maxChars`
  // caps per-line length so no line can be wider than the frame; over-long
  // single words are hard-broken so they never bleed past the foil rules.
  function titleLines(title, maxLines, maxChars) {
    maxLines = maxLines || 4;
    maxChars = maxChars || 14;
    // Expand any single word that is itself wider than the line budget.
    const raw = String(title || "Untitled").trim().split(/\s+/);
    const words = [];
    for (const w of raw) {
      if (w.length > maxChars) words.push(...breakLongWord(w, maxChars));
      else words.push(w);
    }
    if (words.length <= 1) return words;
    const target = Math.ceil(words.length / Math.min(maxLines, Math.ceil(words.length / 1.6)));
    const lines = [];
    let cur = [];
    for (const w of words) {
      const next = cur.length ? cur.join(" ") + " " + w : w;
      // Start a new line if adding this word overflows the char budget.
      if (cur.length && (next.length > maxChars || cur.length >= target)) {
        lines.push(cur.join(" ")); cur = [];
      }
      cur.push(w);
    }
    if (cur.length) lines.push(cur.join(" "));
    // Merge overflow into the last line if we exceeded maxLines.
    while (lines.length > maxLines) {
      const tail = lines.pop();
      lines[lines.length - 1] += " " + tail;
    }
    // Never orphan a short leading article/preposition on its own line — a lone
    // "The"/"A"/"Of" reads as a broken title (e.g. a giant "THE"). Pull it down
    // onto the next line so the title scans as one phrase.
    const ORPHAN = new Set(["the", "a", "an", "of", "and", "to", "in", "on",
      "for", "or", "at", "by"]);
    for (let i = 0; i < lines.length - 1; i++) {
      if (ORPHAN.has(lines[i].trim().toLowerCase())) {
        lines[i + 1] = lines[i].trim() + " " + lines[i + 1];
        lines.splice(i, 1);
        i--;
      }
    }
    return lines;
  }

  // Apply the archetype's caps decision once, up front, so every downstream
  // step (width estimate, font sizing, textLength cap, render) sees the SAME
  // glyph forms. Mixing mixed-case sizing with uppercased rendering is what let
  // a caps title overflow despite "fitting" at its mixed-case width.
  function castCaps(lines, allCaps) {
    return allCaps ? lines.map((l) => l.toUpperCase()) : lines;
  }

  // Conservative average glyph advance, as a fraction of the em, for the display
  // serif. Caps run wider than mixed-case, so we estimate them higher. This is
  // intentionally generous (over-, not under-estimating) so a line that is even
  // close to the frame width gets a textLength cap rather than silently bleeding
  // off the cover edge — the previous 0.54 estimate under-counted caps and let
  // long titles (e.g. "THE LIGHTHOUSE") clip on the bleed edges.
  function glyphAvg(line, fs) {
    const caps = /[A-Z]/.test(line) && line === line.toUpperCase();
    return fs * (caps ? 0.66 : 0.58);
  }
  // Widest line width (px) we'd expect at this font size, used to shrink type.
  function estLineW(lines, fs) {
    return lines.reduce((m, l) => Math.max(m, l.length * glyphAvg(l, fs)), 0);
  }

  // Size the title to fit BOTH the line count (height) and the frame width. The
  // base size comes from the number of lines (fewer -> bigger); we then shrink it
  // for long lines and, when a `maxW` is supplied, shrink further so the widest
  // line's *estimated* width fits the frame — so type fitting never relies on
  // textLength alone (which can over-condense and look squashed).
  //   `cap`  caps the starting size for archetypes that give the title less room.
  //   `maxW` is the drawable width; type is scaled so the widest line fits it.
  function titleFontSize(lines, cap, maxW) {
    const n = lines.length;
    const longest = lines.reduce((m, l) => Math.max(m, l.length), 0);
    let size = n <= 1 ? 58 : n === 2 ? 48 : n === 3 ? 38 : 30;
    if (cap) size = Math.min(size, cap);
    if (longest > 16) size *= 0.86;
    if (longest > 22) size *= 0.84;
    if (maxW) {
      // If the widest line would still overrun the frame at this size, scale the
      // whole block down so it fits with a little air (textLength then only ever
      // nudges, never heavily condenses). Floored so type stays legible.
      const w = estLineW(lines, size);
      if (w > maxW) size *= maxW / w;
      size = Math.max(size, 13);
    }
    return Math.round(size);
  }

  // Build the title <tspan>s with a per-line textLength cap so glyphs are gently
  // condensed to fit `maxW` rather than ever bleeding past the frame. We set
  // textLength on ANY line whose conservative estimate is within a hair of maxW
  // (using a small safety margin) so near-misses are clamped too — the headline
  // cover feature must never render a title clipped on the bleed edges.
  function titleTspans(lines, x, lh, fs, maxW) {
    return lines.map((ln, i) => {
      const est = ln.length * glyphAvg(ln, fs);
      // Clamp with a 4px safety margin: anything that even approaches the frame
      // width is pinned to maxW so it can't spill past the cover edge.
      const tl = est > maxW - 4
        ? ` textLength="${Math.round(maxW)}" lengthAdjust="spacingAndGlyphs"`
        : "";
      return `<tspan x="${x}" dy="${i === 0 ? 0 : lh}"${tl}>${esc(ln)}</tspan>`;
    }).join("");
  }

  /* ------------------------------- motifs -------------------------------- */
  // Each returns SVG markup centred around the given (cx, cy), in `foil`.
  function motifSvg(key, cx, cy, foil, r) {
    const s = (x) => x.toFixed(1);
    const stroke = `stroke="${foil}" fill="none" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"`;
    switch (key) {
      case "moon":
        return `<g opacity="0.92">
          <circle cx="${s(cx)}" cy="${s(cy)}" r="26" fill="${foil}" opacity="0.18"/>
          <path d="M${s(cx + 14)} ${s(cy - 20)} a24 24 0 1 0 0 40 a30 30 0 0 1 0 -40z" fill="${foil}"/>
        </g>`;
      case "key":
        return `<g ${stroke}>
          <circle cx="${s(cx - 12)}" cy="${s(cy - 10)}" r="11"/>
          <path d="M${s(cx - 4)} ${s(cy - 2)} L${s(cx + 18)} ${s(cy + 20)} M${s(cx + 12)} ${s(cy + 14)} l6 -6 M${s(cx + 18)} ${s(cy + 20)} l5 -5"/>
        </g>`;
      case "orbit":
        return `<g ${stroke}>
          <circle cx="${s(cx)}" cy="${s(cy)}" r="6" fill="${foil}"/>
          <ellipse cx="${s(cx)}" cy="${s(cy)}" rx="30" ry="13"/>
          <ellipse cx="${s(cx)}" cy="${s(cy)}" rx="13" ry="30" transform="rotate(28 ${s(cx)} ${s(cy)})"/>
        </g>`;
      case "spire":
        return `<g ${stroke}>
          <path d="M${s(cx)} ${s(cy - 26)} L${s(cx - 12)} ${s(cy + 22)} L${s(cx + 12)} ${s(cy + 22)} Z"/>
          <path d="M${s(cx)} ${s(cy - 26)} L${s(cx)} ${s(cy + 22)}"/>
          <path d="M${s(cx - 18)} ${s(cy + 22)} L${s(cx + 18)} ${s(cy + 22)}"/>
        </g>`;
      case "bloom":
        return `<g ${stroke}>
          ${[0, 72, 144, 216, 288].map((a) => {
            const rad = (a * Math.PI) / 180;
            return `<ellipse cx="${s(cx + Math.cos(rad) * 12)}" cy="${s(cy + Math.sin(rad) * 12)}" rx="6" ry="13" transform="rotate(${a} ${s(cx + Math.cos(rad) * 12)} ${s(cy + Math.sin(rad) * 12)})"/>`;
          }).join("")}
          <circle cx="${s(cx)}" cy="${s(cy)}" r="5" fill="${foil}"/>
        </g>`;
      case "compass":
        return `<g ${stroke}>
          <circle cx="${s(cx)}" cy="${s(cy)}" r="24"/>
          <path d="M${s(cx)} ${s(cy - 18)} L${s(cx + 7)} ${s(cy)} L${s(cx)} ${s(cy + 18)} L${s(cx - 7)} ${s(cy)} Z" fill="${foil}" opacity="0.85"/>
        </g>`;
      case "quill":
        return `<g ${stroke}>
          <path d="M${s(cx - 16)} ${s(cy + 18)} C ${s(cx - 4)} ${s(cy)} ${s(cx + 10)} ${s(cy - 20)} ${s(cx + 18)} ${s(cy - 22)} C ${s(cx + 12)} ${s(cy - 8)} ${s(cx + 4)} ${s(cy + 6)} ${s(cx - 16)} ${s(cy + 18)} Z"/>
          <path d="M${s(cx - 16)} ${s(cy + 18)} L${s(cx - 22)} ${s(cy + 24)}"/>
        </g>`;
      case "rule":
        return `<g>
          <rect x="${s(cx - 30)}" y="${s(cy - 2)}" width="60" height="3" rx="1.5" fill="${foil}"/>
          <circle cx="${s(cx)}" cy="${s(cy - 12)}" r="3.5" fill="${foil}"/>
          <rect x="${s(cx - 18)}" y="${s(cy + 8)}" width="36" height="2" rx="1" fill="${foil}" opacity="0.7"/>
        </g>`;
      case "diamond":
      default:
        return `<g ${stroke}>
          <path d="M${s(cx)} ${s(cy - 22)} L${s(cx + 16)} ${s(cy)} L${s(cx)} ${s(cy + 22)} L${s(cx - 16)} ${s(cy)} Z"/>
          <path d="M${s(cx)} ${s(cy - 11)} L${s(cx + 8)} ${s(cy)} L${s(cx)} ${s(cy + 11)} L${s(cx - 8)} ${s(cy)} Z" fill="${foil}" opacity="0.5"/>
        </g>`;
    }
  }

  /* ------------------------------- cover --------------------------------- */
  // Render a full cover at a 2:3 book ratio. opts.w sets internal coord width
  // (default 300 -> 450 tall). The returned <svg> scales to its container via
  // width/height 100% so cards can size it however they like.
  function svg(book, opts) {
    opts = opts || {};
    const W = opts.w || 300;
    const H = Math.round(W * 1.5);
    const { pal, motif, seed } = paletteFor(book, opts);
    const r = rng(seed);

    const title = (book && book.title) || "Untitled";
    const genre = (book && book.genre) || "";

    // NOTE: SVG presentation attributes don't resolve CSS var(); fonts are set
    // via the `style` attribute (where var() *does* resolve) so the cover uses
    // the app's Fraunces/Inter faces with system fallbacks, fully offline.
    const serifFont = "font-family:var(--font-display,Georgia),Georgia,'Times New Roman',serif";
    const textFont = "font-family:var(--font-text,system-ui),system-ui,-apple-system,Segoe UI,sans-serif";

    // Unique gradient/filter ids per cover so multiple covers coexist on a page.
    const uid = "c" + (seed >>> 0).toString(36);

    const pad = Math.round(W * 0.1);
    const spineW = Math.round(W * 0.06);
    // Inner content box (inside the foil frame) — everything must stay within it.
    const innerX = pad + 4, innerY = pad + 4;
    const innerW = W - (pad + 4) * 2, innerH = H - (pad + 4) * 2;
    const titleMaxW = W - pad * 2 - 8;

    // ---- seeded COMPOSITIONAL archetype --------------------------------
    // Four genuinely distinct layouts so a shelf reads as different books by
    // different designers, not palette swaps of one template. Selected by a
    // stable hash of the genre + seed so the choice is deterministic and a mix
    // appears across a library. The genre nudges the archetype (symbol-forward
    // suits big-motif genres; vertical suits literary) without ever locking it.
    //   0 CLASSIC   centred title block (the heritage look)
    //   1 BAND      foil title band across the top third; large motif below
    //   2 VERTICAL  left-aligned, asymmetric title; tall side rule
    //   3 SYMBOL    a hero motif dominates; small title plate in a corner
    const ARCH = 4;
    const archHash = (hashStr(motif) ^ Math.floor(r() * 0x7fffffff)) >>> 0;
    const layout = archHash % ARCH;
    const isClassic = layout === 0, isBand = layout === 1,
          isVertical = layout === 2, isSymbol = layout === 3;
    const allCaps = isBand || isSymbol || r() < 0.4;

    // Deterministic grain dots (sparse, low-opacity) for a printed-paper feel.
    let grain = "";
    const dots = 26;
    for (let i = 0; i < dots; i++) {
      const x = (r() * W).toFixed(1);
      const y = (r() * H).toFixed(1);
      const rr = (0.5 + r() * 1.2).toFixed(2);
      const op = (0.03 + r() * 0.06).toFixed(3);
      grain += `<circle cx="${x}" cy="${y}" r="${rr}" fill="#fff" opacity="${op}"/>`;
    }
    const sheenX = (W * (0.2 + r() * 0.5)).toFixed(1);

    // ---- per-archetype title geometry ----------------------------------
    // Each archetype owns its title zone (anchor, x, max width, font cap) so the
    // shared fitting/wrapping keeps the type inside its box at every size.
    let titleBlock = "", rules = "", motifMarkup = "", genreLabel = "";
    const motifFoil = pal.foil;
    const ssize = Math.round(W * 0.038); // genre label size

    if (isBand) {
      // BAND: title set in a flat foil band across the top third; a large genre
      // motif owns the lower half. The band ink flips to the field colour so the
      // title reads as foil-stamped lettering on a metallic strip.
      const bandH = Math.round(H * 0.30);
      const bandY = innerY;
      const bandMaxW = innerW - 20;
      // Cast to the final caps form FIRST so width fitting sees true glyph widths.
      const lines = castCaps(titleLines(title, 3, 16), allCaps);
      let fs = titleFontSize(lines, 40, bandMaxW);
      // shrink to fit the band height (line-height * lines must clear the band)
      const lh = Math.round(fs * 1.04);
      const blockH = lines.length * lh;
      if (blockH > bandH - 16) fs = Math.round(fs * (bandH - 16) / blockH);
      const lh2 = Math.round(fs * 1.04);
      const ty = Math.round(bandY + bandH / 2 - ((lines.length - 1) * lh2) / 2 + fs * 0.34);
      const spans = titleTspans(lines, W / 2, lh2, fs, bandMaxW);
      rules =
        `<rect x="${innerX}" y="${bandY}" width="${innerW}" height="${bandH}" fill="${pal.foil}" opacity="0.94"/>` +
        `<line x1="${innerX}" y1="${bandY + bandH + 3}" x2="${innerX + innerW}" y2="${bandY + bandH + 3}" stroke="${pal.foil}" stroke-width="1.2" opacity="0.7"/>`;
      titleBlock =
        `<text x="${W / 2}" y="${ty}" text-anchor="middle" font-weight="700" font-size="${fs}" fill="${pal.bg2}"
              style="${serifFont};letter-spacing:${allCaps ? "0.05em" : "0"}">${spans}</text>`;
      const mScale = (W / 300) * 2.6;
      motifMarkup =
        `<g transform="translate(${W / 2} ${Math.round(H * 0.64)}) scale(${mScale.toFixed(2)})">` +
        motifSvg(motif, 0, 0, motifFoil, 26) + `</g>`;
      if (genre) genreLabel =
        `<text x="${W / 2}" y="${Math.round(H * 0.88)}" text-anchor="middle" font-size="${ssize}"
              letter-spacing="3" fill="${pal.sub}" style="${textFont};text-transform:uppercase">${esc(genre).slice(0, 22)}</text>`;

    } else if (isVertical) {
      // VERTICAL: left-aligned, asymmetric title pushed off the centre, with a
      // tall foil rule running down the left margin and the motif tucked low-right.
      const lx = innerX + 14;
      // Left-aligned at lx, the title can run to the inner-right edge; keep a
      // small right margin so glyphs never touch the foil frame.
      const vMaxW = innerW - 28;
      const lines = castCaps(titleLines(title, 4, 13), allCaps);
      const fs = titleFontSize(lines, null, vMaxW);
      const lh = Math.round(fs * 1.08);
      const ty = Math.round(H * 0.30);
      const spans = titleTspans(lines, lx, lh, fs, vMaxW);
      rules =
        `<line x1="${lx - 7}" y1="${Math.round(H * 0.20)}" x2="${lx - 7}" y2="${ty + lines.length * lh}" stroke="${pal.foil}" stroke-width="2.4" opacity="0.9" stroke-linecap="round"/>`;
      titleBlock =
        `<text x="${lx}" y="${ty}" text-anchor="start" font-weight="600" font-size="${fs}" fill="${pal.ink}"
              style="${serifFont};letter-spacing:${allCaps ? "0.04em" : "-0.01em"}">${spans}</text>`;
      const mScale = (W / 300) * 1.7;
      motifMarkup =
        `<g transform="translate(${Math.round(W * 0.70)} ${Math.round(H * 0.74)}) scale(${mScale.toFixed(2)})">` +
        motifSvg(motif, 0, 0, motifFoil, 26) + `</g>`;
      if (genre) genreLabel =
        `<text x="${lx}" y="${ty + lines.length * lh + Math.round(H * 0.045)}" text-anchor="start" font-size="${ssize}"
              letter-spacing="3" fill="${pal.sub}" style="${textFont};text-transform:uppercase">${esc(genre).slice(0, 22)}</text>`;

    } else if (isSymbol) {
      // SYMBOL-FORWARD: a large genre motif is the hero, centred high; a compact
      // title plate sits along the bottom with a hairline frame. Title is small
      // but legible — the composition leads with the symbol.
      const mScale = (W / 300) * 3.4;
      motifMarkup =
        `<g transform="translate(${W / 2} ${Math.round(H * 0.40)}) scale(${mScale.toFixed(2)})">` +
        motifSvg(motif, 0, 0, motifFoil, 26) + `</g>`;
      const symMaxW = innerW - 28;
      const lines = castCaps(titleLines(title, 2, 18), allCaps);
      let fs = titleFontSize(lines, 34, symMaxW);
      const lh = Math.round(fs * 1.02);
      const plateTop = Math.round(H * 0.74);
      const plateH = innerY + innerH - plateTop - 2;
      const ty = Math.round(plateTop + plateH / 2 - ((lines.length - 1) * lh) / 2 + fs * 0.32);
      const spans = titleTspans(lines, W / 2, lh, fs, symMaxW);
      rules =
        `<rect x="${innerX + 8}" y="${plateTop}" width="${innerW - 16}" height="${plateH}" fill="${pal.bg2}" opacity="0.55"/>` +
        `<rect x="${innerX + 8}" y="${plateTop}" width="${innerW - 16}" height="${plateH}" fill="none" stroke="${pal.foil}" stroke-width="1" opacity="0.7"/>`;
      titleBlock =
        `<text x="${W / 2}" y="${ty}" text-anchor="middle" font-weight="600" font-size="${fs}" fill="${pal.ink}"
              style="${serifFont};letter-spacing:${allCaps ? "0.05em" : "0"}">${spans}</text>`;
      if (genre) genreLabel =
        `<text x="${W / 2}" y="${Math.round(H * 0.20)}" text-anchor="middle" font-size="${ssize}"
              letter-spacing="3" fill="${pal.sub}" style="${textFont};text-transform:uppercase">${esc(genre).slice(0, 22)}</text>`;

    } else {
      // CLASSIC: the heritage centred title stack with twin foil rules and a
      // motif set low. (The original, kept intact as one of the four.)
      const lines = castCaps(titleLines(title, 4), allCaps);
      const fs = titleFontSize(lines, null, titleMaxW);
      const lh = Math.round(fs * 1.06);
      const titleTop = Math.round(H * 0.30);
      const spans = titleTspans(lines, W / 2, lh, fs, titleMaxW);
      const ruleY1 = Math.round(H * 0.16), ruleY2 = Math.round(H * 0.205);
      rules =
        `<line x1="${pad + 14}" y1="${ruleY1}" x2="${W - pad - 14}" y2="${ruleY1}" stroke="${pal.foil}" stroke-width="1.4" opacity="0.85"/>` +
        `<line x1="${W * 0.3}" y1="${ruleY2}" x2="${W * 0.7}" y2="${ruleY2}" stroke="${pal.foil}" stroke-width="0.8" opacity="0.6"/>`;
      const bigMotif = r() < 0.22;
      const mScale = bigMotif ? (W / 300) * 2.1 : (W / 300);
      const my = Math.round(H * 0.72);
      motifMarkup =
        `<g transform="translate(${W / 2} ${my}) scale(${mScale.toFixed(2)})">` +
        motifSvg(motif, 0, 0, motifFoil, 26) + `</g>`;
      titleBlock =
        `<text x="${W / 2}" y="${titleTop}" text-anchor="middle" font-weight="600" font-size="${fs}" fill="${pal.ink}"
              style="${serifFont};letter-spacing:${allCaps ? "0.04em" : "-0.01em"}">${spans}</text>`;
      if (genre) genreLabel =
        `<text x="${W / 2}" y="${Math.round(H * 0.83)}" text-anchor="middle" font-size="${ssize}"
              letter-spacing="3" fill="${pal.sub}" style="${textFont};text-transform:uppercase">${esc(genre).slice(0, 22)}</text>`;
    }

    // The cover is decorative: the surrounding card/figure already carries the
    // accessible name, so the SVG is aria-hidden to avoid a contradictory
    // duplicate label inside aria-hidden wrappers.
    return `<svg viewBox="0 0 ${W} ${H}" class="cover-svg" preserveAspectRatio="xMidYMid slice"
        aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="${uid}-bg" x1="0" y1="0" x2="0.35" y2="1">
          <stop offset="0" stop-color="${pal.bg}"/>
          <stop offset="1" stop-color="${pal.bg2}"/>
        </linearGradient>
        <linearGradient id="${uid}-sheen" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#ffffff" stop-opacity="0"/>
          <stop offset="0.5" stop-color="#ffffff" stop-opacity="0.10"/>
          <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
        </linearGradient>
        <radialGradient id="${uid}-vig" cx="0.5" cy="0.42" r="0.75">
          <stop offset="0.55" stop-color="#000000" stop-opacity="0"/>
          <stop offset="1" stop-color="#000000" stop-opacity="0.34"/>
        </radialGradient>
        <!-- clip every cover element to the inner frame so nothing can bleed
             past the foil rules or off the cover edge on long/odd titles. -->
        <clipPath id="${uid}-clip">
          <rect x="${innerX}" y="${innerY}" width="${innerW}" height="${innerH}" rx="2"/>
        </clipPath>
      </defs>

      <!-- field -->
      <rect width="${W}" height="${H}" fill="url(#${uid}-bg)"/>
      <!-- diagonal sheen -->
      <rect x="${sheenX}" y="0" width="${W * 0.5}" height="${H}" fill="url(#${uid}-sheen)"
            transform="skewX(-12)" opacity="0.8"/>
      <!-- grain -->
      <g>${grain}</g>
      <!-- inner foil frame -->
      <rect x="${pad}" y="${pad}" width="${W - pad * 2}" height="${H - pad * 2}"
            fill="none" stroke="${pal.foil}" stroke-width="1" opacity="0.55"/>
      <rect x="${innerX}" y="${innerY}" width="${innerW}" height="${innerH}"
            fill="none" stroke="${pal.foil}" stroke-width="0.5" opacity="0.35"/>

      <!-- all type + motif clipped to the inner frame -->
      <g clip-path="url(#${uid}-clip)">
        ${motifMarkup}
        ${rules}
        ${titleBlock}
        ${genreLabel}
      </g>

      <!-- imprint -->
      <text x="${W / 2}" y="${H - pad - 6}" text-anchor="middle"
            font-size="${Math.round(W * 0.033)}"
            letter-spacing="4" fill="${pal.foil}" opacity="0.92"
            style="${textFont};text-transform:uppercase">Bookwriter&#8202;Pro</text>

      <!-- spine shading + vignette -->
      <rect x="0" y="0" width="${spineW}" height="${H}" fill="#000" opacity="0.22"/>
      <rect x="${spineW}" y="0" width="2" height="${H}" fill="#fff" opacity="0.08"/>
      <rect width="${W}" height="${H}" fill="url(#${uid}-vig)"/>
    </svg>`;
  }

  /* ------------------------------- spine --------------------------------- */
  // A slim vertical spine for shelf decoration (purely decorative).
  function spineSvg(book) {
    const { pal, seed } = paletteFor(book);
    const r = rng(seed ^ 0x9e3779b9);
    const W = 28, H = 200;
    const uid = "s" + (seed >>> 0).toString(36);
    const title = ((book && book.title) || "Untitled").slice(0, 26);
    return `<svg viewBox="0 0 ${W} ${H}" class="spine-svg" preserveAspectRatio="none"
        aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg">
      <defs><linearGradient id="${uid}" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="${pal.bg2}"/><stop offset="0.5" stop-color="${pal.bg}"/><stop offset="1" stop-color="${pal.bg2}"/>
      </linearGradient></defs>
      <rect width="${W}" height="${H}" fill="url(#${uid})"/>
      <rect x="3" y="${(8 + r() * 10).toFixed(0)}" width="${W - 6}" height="2" fill="${pal.foil}" opacity="0.8"/>
      <rect x="3" y="${H - 16}" width="${W - 6}" height="2" fill="${pal.foil}" opacity="0.8"/>
      <text x="${W / 2}" y="${H / 2}" text-anchor="middle"
            transform="rotate(90 ${W / 2} ${H / 2})"
            font-size="11" fill="${pal.ink}" opacity="0.92"
            style="font-family:var(--font-display,Georgia),Georgia,serif">${esc(title)}</text>
    </svg>`;
  }

  window.Covers = { svg, spineSvg, paletteFor };
})();
