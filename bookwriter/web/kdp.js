/* ===========================================================================
   Bookwriter Pro — "Publish to KDP" screen (kdp.js)
   --------------------------------------------------------------------------
   Defines Views.publish(id): a polished form that mirrors Amazon KDP's
   "page 1" (book details) field-for-field, an "Auto-fill with AI" action that
   calls POST /api/books/{id}/kdp (embedding the real procedural cover so the
   generated EPUB carries it), and download/copy/launch actions.

   Self-contained: it reuses globals from app.js ($, $$, esc, toast, fmtInt,
   API, paintCover, mountView, setActiveNav, Router) and window.Covers. It only
   touches ids/classes it creates here (all `kdp-*` / `.kdp-*`), so it never
   collides with other views' contracts.

   Loaded AFTER app.js in index.html so Views / API exist when this runs.
   =========================================================================== */
"use strict";

(function () {
  // KDP listing-text endpoint (plain text for the clipboard) is fetched
  // directly so we control the Accept/parse; the JSON helpers live on API.
  const KDP_NEW_TITLE_URL =
    "https://kdp.amazon.com/en_US/title-setup/kindle/new/details";

  // ---- KDP field limits (the rules the form enforces inline) ----
  const DESC_MAX = 4000;
  const MAX_KEYWORDS = 7;
  const KEYWORD_MAX = 50;
  const MAX_CATEGORIES = 3;
  const MAX_CONTRIBUTORS = 9;
  const STORYTELLER_KEYWORD = "StorytellerUK2026";

  // Cover raster target: KDP wants a ~1.6:1 ebook cover, longest side 2560px.
  const COVER_W = 1600;
  const COVER_H = 2560;

  // A few sensible fiction category suggestions (BISAC-ish Kindle store paths).
  const CATEGORY_SUGGESTIONS = [
    "Fiction / Literary",
    "Fiction / Thrillers / Suspense",
    "Fiction / Mystery & Detective",
    "Fiction / Science Fiction",
    "Fiction / Fantasy / Epic",
    "Fiction / Horror",
    "Fiction / Romance / Contemporary",
    "Fiction / Historical",
    "Fiction / Coming of Age",
  ];

  const READING_AGES = ["", "0", "2", "4", "6", "8", "10", "12", "14", "16", "18"];

  // ----------------------------------------------------------------- helpers
  // Split a single "Author Name" string into first / last for the prefilled
  // author fields. Everything but the final token is the first name (so
  // middle names land in the first-name field, per KDP guidance); the final
  // token is the last name.
  function splitName(name) {
    const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return { first: "", last: "" };
    if (parts.length === 1) return { first: parts[0], last: "" };
    return { first: parts.slice(0, -1).join(" "), last: parts[parts.length - 1] };
  }

  // Render the book's procedural cover to an SVG string (for the EPUB payload).
  function coverSvgFor(book) {
    if (window.Covers && typeof window.Covers.svg === "function") {
      try { return window.Covers.svg(book); } catch { /* fall through */ }
    }
    return "";
  }

  // -------------------------------------------------------------- the markup
  function viewMarkup() {
    return (
`<section class="view view-publish">
  <div class="subview-head">
    <div>
      <p class="eyebrow" id="kdp-eyebrow">Publish</p>
      <h1 class="display">Send it to the world</h1>
    </div>
    <div class="subview-actions">
      <a class="btn btn-ghost" id="kdp-back" href="#">← Studio</a>
      <button class="btn btn-primary" id="kdp-autofill" type="button">
        <span class="btn-label">✨ Auto-fill with AI</span>
        <span class="btn-spinner" aria-hidden="true"></span>
      </button>
    </div>
  </div>

  <div class="kdp-layout">
    <!-- LEFT: the KDP page-1 form -->
    <form class="kdp-form" id="kdp-form" novalidate aria-label="Amazon KDP book details">

      <fieldset class="kdp-group">
        <legend>Language &amp; title</legend>
        <div class="field">
          <label for="kdp-language">Language</label>
          <select id="kdp-language" name="language">
            <option value="English" selected>English</option>
          </select>
          <p class="field-hint">English is the supported language for now.</p>
        </div>
        <div class="field">
          <label for="kdp-title">Book title <span class="req">*</span></label>
          <input id="kdp-title" name="title" type="text" placeholder="Your book's title" />
        </div>
        <div class="field">
          <label for="kdp-subtitle">Subtitle <span class="opt">optional</span></label>
          <input id="kdp-subtitle" name="subtitle" type="text" placeholder="A short, evocative subtitle" />
          <p class="field-hint">KDP inserts a colon between title and subtitle automatically — keep them separate. Title &amp; subtitle can't change after publishing.</p>
        </div>
        <div class="field-row field-row-3">
          <div class="field">
            <label for="kdp-series">Series <span class="opt">optional</span></label>
            <input id="kdp-series" name="series" type="text" placeholder="Series name" />
          </div>
          <div class="field">
            <label for="kdp-series-part">Series #</label>
            <input id="kdp-series-part" name="series_part" type="number" min="1" placeholder="e.g. 1" />
          </div>
          <div class="field">
            <label for="kdp-edition">Edition <span class="opt">optional</span></label>
            <input id="kdp-edition" name="edition" type="number" min="1" placeholder="e.g. 1" />
          </div>
        </div>
      </fieldset>

      <fieldset class="kdp-group">
        <legend>Author &amp; contributors</legend>
        <div class="field-row">
          <div class="field">
            <label for="kdp-author-first">Primary author — first name <span class="req">*</span></label>
            <input id="kdp-author-first" name="author_first" type="text" placeholder="First (middle/prefix here)" />
          </div>
          <div class="field">
            <label for="kdp-author-last">Last name</label>
            <input id="kdp-author-last" name="author_last" type="text" placeholder="Last (suffix here)" />
          </div>
        </div>
        <div class="field">
          <div class="kdp-row-head">
            <label>Contributors <span class="opt">up to 9, optional</span></label>
            <button class="kdp-mini-btn" id="kdp-add-contributor" type="button">+ Add contributor</button>
          </div>
          <div class="kdp-contributors" id="kdp-contributors"></div>
        </div>
      </fieldset>

      <fieldset class="kdp-group">
        <legend>Description</legend>
        <div class="field">
          <label for="kdp-description">Product description</label>
          <textarea id="kdp-description" name="description" rows="7"
            placeholder="Punchy back-cover marketing copy — hook, stakes, voice. Light HTML allowed (&lt;b&gt; &lt;i&gt; &lt;br&gt; &lt;ul&gt;/&lt;li&gt; &lt;h4&gt;)."></textarea>
          <p class="field-hint kdp-counter" id="kdp-desc-counter">4000 remaining</p>
        </div>
      </fieldset>

      <fieldset class="kdp-group">
        <legend>Rights &amp; audience</legend>
        <div class="field">
          <span class="kdp-label">Publishing rights</span>
          <label class="kdp-radio"><input type="radio" name="rights" value="owned" checked />
            <span>I own the copyright and hold the necessary publishing rights</span></label>
          <label class="kdp-radio"><input type="radio" name="rights" value="public_domain" />
            <span>This is a public-domain work</span></label>
        </div>
        <div class="field">
          <span class="kdp-label">Sexually explicit images or title</span>
          <div class="kdp-radio-inline">
            <label class="kdp-radio"><input type="radio" name="explicit" value="no" checked /><span>No</span></label>
            <label class="kdp-radio"><input type="radio" name="explicit" value="yes" /><span>Yes</span></label>
          </div>
        </div>
        <div class="field-row">
          <div class="field">
            <label for="kdp-age-min">Reading age — min <span class="opt">optional</span></label>
            <select id="kdp-age-min" name="age_min"></select>
          </div>
          <div class="field">
            <label for="kdp-age-max">Reading age — max <span class="opt">optional</span></label>
            <select id="kdp-age-max" name="age_max"></select>
          </div>
        </div>
        <p class="field-hint">Reading age is only for children's / YA titles — leave blank for adult fiction.</p>
        <div class="field">
          <label for="kdp-marketplace">Primary marketplace</label>
          <select id="kdp-marketplace" name="marketplace">
            <option value="Amazon.com" selected>Amazon.com</option>
          </select>
        </div>
      </fieldset>

      <fieldset class="kdp-group">
        <legend>Categories</legend>
        <div class="field">
          <div class="kdp-row-head">
            <label for="kdp-category-input">Categories <span class="opt">up to 3</span></label>
            <span class="kdp-count" id="kdp-cat-count">0 / 3</span>
          </div>
          <div class="kdp-chips" id="kdp-categories" aria-label="Chosen categories"></div>
          <div class="kdp-add-line">
            <input id="kdp-category-input" type="text" list="kdp-category-list"
              placeholder="Add a category, then Enter" />
            <button class="kdp-mini-btn" id="kdp-add-category" type="button">Add</button>
          </div>
          <datalist id="kdp-category-list"></datalist>
          <p class="field-hint" id="kdp-cat-hint"></p>
        </div>
      </fieldset>

      <fieldset class="kdp-group">
        <legend>Keywords</legend>
        <div class="field">
          <div class="kdp-row-head">
            <label for="kdp-keyword-input">Keywords <span class="opt">up to 7, ≤ 50 chars each</span></label>
            <span class="kdp-count" id="kdp-kw-count">0 / 7</span>
          </div>
          <div class="kdp-chips" id="kdp-keywords" aria-label="Chosen keywords"></div>
          <div class="kdp-add-line">
            <input id="kdp-keyword-input" type="text" maxlength="50"
              placeholder="A phrase a reader would search, then Enter" />
            <button class="kdp-mini-btn" id="kdp-add-keyword" type="button">Add</button>
          </div>
          <div class="kdp-kw-foot">
            <button class="kdp-mini-btn kdp-storyteller" id="kdp-add-storyteller" type="button">+ Add StorytellerUK2026</button>
            <p class="field-hint">No title/author, no other books' titles, no "bestseller/free/on sale", no subjective claims.</p>
          </div>
          <p class="field-hint kdp-error" id="kdp-kw-error" hidden></p>
        </div>
      </fieldset>

      <p class="kdp-form-note" id="kdp-form-note" role="status" aria-live="polite"></p>
    </form>

    <!-- RIGHT: cover preview, actions, checklist -->
    <aside class="kdp-side" aria-label="Cover and publishing actions">
      <div class="kdp-cover-card">
        <div class="kdp-cover" id="kdp-cover" data-cover aria-hidden="true"></div>
        <p class="kdp-cover-cap">Your KDP-ready cover · ${COVER_W}×${COVER_H}</p>
      </div>

      <div class="kdp-actions-card">
        <h2 class="rail-title">Get your files</h2>
        <a class="btn btn-primary kdp-action" id="kdp-epub" href="#" download>
          <svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M5 19h14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
          Download EPUB
        </a>
        <button class="btn btn-ghost kdp-action" id="kdp-cover-dl" type="button">
          <svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true"><path d="M4 16l4-5 3 3 4-5 5 7M4 20h16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
          Download cover (PNG)
        </button>
        <button class="btn btn-ghost kdp-action" id="kdp-copy" type="button">
          <svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" fill="none" stroke="currentColor" stroke-width="2"/></svg>
          Copy KDP listing
        </button>
        <a class="btn btn-ghost kdp-action" id="kdp-open" href="${KDP_NEW_TITLE_URL}" target="_blank" rel="noopener noreferrer">
          <svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true"><path d="M14 5h5v5M19 5l-9 9M11 5H7a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
          Open Amazon KDP
        </a>
      </div>

      <div class="kdp-checklist-card">
        <h2 class="rail-title">How to publish</h2>
        <ol class="kdp-checklist">
          <li><span class="kdp-step">1</span> Paste these fields into KDP page&nbsp;1 (book details).</li>
          <li><span class="kdp-step">2</span> Upload <code>manuscript.epub</code> + your cover on page&nbsp;2.</li>
          <li><span class="kdp-step">3</span> Set price &amp; publish.</li>
        </ol>
        <p class="kdp-note">Heads up: title, subtitle and edition number can't be changed once the book is published.</p>
      </div>
    </aside>
  </div>
</section>`
    );
  }

  // ----------------------------------------------------------- chip widgets
  // A generic chip collection (categories / keywords). Tracks an array of
  // string values; re-renders chips with a per-chip remove button and an
  // optional per-chip char counter (keywords). `onChange` runs after edits.
  function ChipBox(holderEl, opts) {
    opts = opts || {};
    const max = opts.max || 99;
    const charMax = opts.charMax || 0;
    let values = [];

    function render() {
      holderEl.innerHTML = "";
      values.forEach((v, i) => {
        const chip = document.createElement("span");
        const over = charMax && v.length > charMax;
        chip.className = "kdp-chip" + (over ? " is-over" : "");
        const counter = charMax
          ? `<span class="kdp-chip-count">${v.length}/${charMax}</span>` : "";
        chip.innerHTML =
          `<span class="kdp-chip-text">${esc(v)}</span>${counter}` +
          `<button type="button" class="kdp-chip-x" aria-label="Remove ${esc(v)}">×</button>`;
        chip.querySelector(".kdp-chip-x").addEventListener("click", () => {
          values.splice(i, 1); render(); opts.onChange && opts.onChange();
        });
        holderEl.appendChild(chip);
      });
      opts.onChange && opts.onChange();
    }

    return {
      get: () => values.slice(),
      set(arr) { values = (arr || []).map((s) => String(s).trim()).filter(Boolean).slice(0, max); render(); },
      add(v) {
        v = String(v || "").trim();
        if (!v) return false;
        if (values.length >= max) return false;
        if (values.some((x) => x.toLowerCase() === v.toLowerCase())) return false;
        values.push(v); render(); return true;
      },
      count: () => values.length,
      max,
      render,
    };
  }

  // -------------------------------------------------------- contributor rows
  function makeContributorRow(holder, first, last) {
    if (holder.children.length >= MAX_CONTRIBUTORS) return;
    const row = document.createElement("div");
    row.className = "kdp-contributor";
    row.innerHTML =
      `<input type="text" class="kdp-contrib-first" placeholder="First name" />` +
      `<input type="text" class="kdp-contrib-last" placeholder="Last name" />` +
      `<button type="button" class="kdp-chip-x kdp-contrib-x" aria-label="Remove contributor">×</button>`;
    row.querySelector(".kdp-contrib-first").value = first || "";
    row.querySelector(".kdp-contrib-last").value = last || "";
    row.querySelector(".kdp-contrib-x").addEventListener("click", () => row.remove());
    holder.appendChild(row);
  }

  // -------------------------------------------------------------- the view
  Views.publish = async function (id) {
    setActiveNav("");
    const wrap = document.createElement("div");
    wrap.innerHTML = viewMarkup();
    const view = wrap.firstElementChild;
    mountView(view);

    $("#kdp-back", view).setAttribute("href", `#/b/${id}`);
    $("#kdp-epub", view).setAttribute("href", `/api/books/${id}/export/epub?download=1`);

    // Populate reading-age selects.
    const ageMin = $("#kdp-age-min", view), ageMax = $("#kdp-age-max", view);
    READING_AGES.forEach((a) => {
      const label = a === "" ? "—" : a;
      ageMin.appendChild(new Option(label, a));
      ageMax.appendChild(new Option(label, a));
    });

    // Category datalist suggestions.
    const dl = $("#kdp-category-list", view);
    CATEGORY_SUGGESTIONS.forEach((c) => dl.appendChild(new Option(c)));

    // Chip boxes (categories + keywords) with live counters / validation.
    const cats = ChipBox($("#kdp-categories", view), {
      max: MAX_CATEGORIES,
      onChange() {
        const n = cats.count();
        $("#kdp-cat-count", view).textContent = `${n} / ${MAX_CATEGORIES}`;
        const full = n >= MAX_CATEGORIES;
        $("#kdp-category-input", view).disabled = full;
        $("#kdp-add-category", view).disabled = full;
        $("#kdp-cat-hint", view).textContent = full ? "Maximum of 3 categories reached." : "";
      },
    });
    const keywords = ChipBox($("#kdp-keywords", view), {
      max: MAX_KEYWORDS, charMax: KEYWORD_MAX,
      onChange() {
        const n = keywords.count();
        $("#kdp-kw-count", view).textContent = `${n} / ${MAX_KEYWORDS}`;
        const full = n >= MAX_KEYWORDS;
        $("#kdp-keyword-input", view).disabled = full;
        $("#kdp-add-keyword", view).disabled = full;
        const over = keywords.get().filter((k) => k.length > KEYWORD_MAX);
        const errEl = $("#kdp-kw-error", view);
        if (over.length) { errEl.hidden = false; errEl.textContent = `${over.length} keyword(s) exceed 50 characters.`; }
        else errEl.hidden = true;
        // Storyteller helper: disable once present or when full.
        const has = keywords.get().some((k) => k.toLowerCase() === STORYTELLER_KEYWORD.toLowerCase());
        $("#kdp-add-storyteller", view).disabled = has || full;
      },
    });
    cats.render(); keywords.render();

    // Wire chip add controls (Enter in the input or the Add button).
    const wireAdd = (inputId, btnId, box, onFull) => {
      const input = $(`#${inputId}`, view), btn = $(`#${btnId}`, view);
      const commit = () => {
        const ok = box.add(input.value);
        if (ok) input.value = "";
        else if (box.count() >= box.max) onFull && onFull();
      };
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); commit(); }
      });
      btn.addEventListener("click", commit);
    };
    wireAdd("kdp-category-input", "kdp-add-category", cats);
    wireAdd("kdp-keyword-input", "kdp-add-keyword", keywords);

    $("#kdp-add-storyteller", view).addEventListener("click", () => keywords.add(STORYTELLER_KEYWORD));

    // Contributors.
    const contribHolder = $("#kdp-contributors", view);
    $("#kdp-add-contributor", view).addEventListener("click", () => makeContributorRow(contribHolder));

    // Description live counter.
    const desc = $("#kdp-description", view), descCounter = $("#kdp-desc-counter", view);
    const updateDesc = () => {
      const left = DESC_MAX - desc.value.length;
      descCounter.textContent = `${left} remaining`;
      descCounter.classList.toggle("is-over", left < 0);
    };
    desc.addEventListener("input", updateDesc);
    updateDesc();

    // Load the book, prefill the form, paint the cover.
    let book = { id, title: "Untitled" };
    try {
      const data = await API.book(id);
      book = (data && data.book) || book;
    } catch (err) {
      toast(err.message || "Couldn't load the book.", { title: "Publish", type: "error" });
    }
    const meta = {
      id: book.id || id,
      title: book.title || "",
      genre: book.genre || "",
      logline: book.logline || "",
    };

    $("#kdp-eyebrow", view).textContent = meta.genre || "Publish";
    $("#kdp-title", view).value = meta.title;
    const an = splitName(book.author || book.pen_name || "");
    $("#kdp-author-first", view).value = an.first;
    $("#kdp-author-last", view).value = an.last;
    paintCover($("#kdp-cover", view), meta);

    // If a listing was generated before, hydrate the editable fields with it.
    try {
      const prev = await API.kdp(id);
      if (prev && prev.metadata) applyMetadata(prev.metadata);
    } catch { /* none yet — fine */ }

    // -------- apply server metadata -> form fields (shared by GET + autofill)
    function applyMetadata(m) {
      if (!m) return;
      if (m.subtitle != null && !$("#kdp-subtitle", view).value) $("#kdp-subtitle", view).value = m.subtitle;
      if (m.description != null) { desc.value = m.description; updateDesc(); }
      if (Array.isArray(m.keywords)) keywords.set(m.keywords);
      if (Array.isArray(m.categories)) cats.set(m.categories);
      if (m.reading_age) {
        if (m.reading_age.min != null) ageMin.value = String(m.reading_age.min);
        if (m.reading_age.max != null) ageMax.value = String(m.reading_age.max);
      }
    }

    // ---------------------------------------------------- Auto-fill with AI
    const autofillBtn = $("#kdp-autofill", view);
    autofillBtn.addEventListener("click", async () => {
      autofillBtn.classList.add("is-busy"); autofillBtn.disabled = true;
      $(".btn-label", autofillBtn).textContent = "Generating…";
      const note = $("#kdp-form-note", view);
      note.textContent = ""; note.classList.remove("is-error");
      try {
        const payload = {
          author_first: $("#kdp-author-first", view).value.trim() || undefined,
          author_last: $("#kdp-author-last", view).value.trim() || undefined,
          cover_svg: coverSvgFor(meta) || undefined,
        };
        const res = await API.kdpGenerate(id, payload);
        applyMetadata((res && res.metadata) || res);
        note.textContent = "Description, keywords and categories filled in. Review, then copy into KDP.";
        toast("Listing generated.", { title: "Auto-filled", type: "good" });
      } catch (err) {
        note.textContent = err.message || "Auto-fill failed.";
        note.classList.add("is-error");
        toast(err.message || "Auto-fill failed.", { title: "Couldn't auto-fill", type: "error" });
      } finally {
        autofillBtn.classList.remove("is-busy"); autofillBtn.disabled = false;
        $(".btn-label", autofillBtn).textContent = "✨ Auto-fill with AI";
      }
    });

    // ------------------------------------------------- Download cover (PNG)
    $("#kdp-cover-dl", view).addEventListener("click", () => downloadCoverPng(meta, view));

    // ------------------------------------------------------- Copy listing
    $("#kdp-copy", view).addEventListener("click", () => copyListing(id));

    // ---- Pre-flight validation badge on EPUB / open (non-blocking hints) ----
    function validate() {
      const problems = [];
      if (!$("#kdp-title", view).value.trim()) problems.push("a book title");
      const hasAuthor = $("#kdp-author-first", view).value.trim() || $("#kdp-author-last", view).value.trim();
      if (!hasAuthor) problems.push("an author name");
      if (keywords.count() > MAX_KEYWORDS) problems.push("≤ 7 keywords");
      if (keywords.get().some((k) => k.length > KEYWORD_MAX)) problems.push("keywords ≤ 50 chars");
      if (cats.count() > MAX_CATEGORIES) problems.push("≤ 3 categories");
      if (desc.value.length > DESC_MAX) problems.push("a description ≤ 4000 chars");
      return problems;
    }

    // Surface validation hints when the user heads to KDP.
    $("#kdp-open", view).addEventListener("click", () => {
      const problems = validate();
      if (problems.length) {
        const note = $("#kdp-form-note", view);
        note.textContent = "Before you publish, add: " + problems.join(", ") + ".";
        note.classList.remove("is-error");
        toast("Some KDP fields still need attention.", { type: "info" });
      }
    });
  };

  // --------------------------------------------------- client-side cover PNG
  // Render the procedural cover SVG into an <img>, draw it onto a 1600×2560
  // canvas, and export a PNG via toBlob — entirely client-side. KDP wants a
  // raster ebook cover ~1.6:1 with the longest side at 2560px.
  function downloadCoverPng(meta, view) {
    const svg = coverSvgFor(meta);
    if (!svg) { toast("Cover unavailable.", { type: "error" }); return; }
    const btn = $("#kdp-cover-dl", view);
    btn.classList.add("is-busy"); btn.disabled = true;

    const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
      try {
        const canvas = document.createElement("canvas");
        canvas.width = COVER_W; canvas.height = COVER_H;
        const ctx = canvas.getContext("2d");
        // Paper-cream backstop so any transparent margins aren't black.
        ctx.fillStyle = "#f4ece0";
        ctx.fillRect(0, 0, COVER_W, COVER_H);
        ctx.drawImage(img, 0, 0, COVER_W, COVER_H);
        canvas.toBlob((png) => {
          URL.revokeObjectURL(url);
          if (!png) { toast("Couldn't render the cover.", { type: "error" }); resetBtn(); return; }
          const a = document.createElement("a");
          const pngUrl = URL.createObjectURL(png);
          a.href = pngUrl;
          a.download = `${(meta.title || "cover").replace(/[^a-z0-9]+/gi, "-").toLowerCase()}-kdp-cover.png`;
          document.body.appendChild(a); a.click(); a.remove();
          setTimeout(() => URL.revokeObjectURL(pngUrl), 1000);
          toast("Cover saved (2560px PNG).", { title: "Downloaded", type: "good" });
          resetBtn();
        }, "image/png");
      } catch (e) {
        URL.revokeObjectURL(url);
        toast("Couldn't render the cover.", { type: "error" });
        resetBtn();
      }
    };
    img.onerror = () => { URL.revokeObjectURL(url); toast("Couldn't load the cover image.", { type: "error" }); resetBtn(); };
    img.src = url;

    function resetBtn() { btn.classList.remove("is-busy"); btn.disabled = false; }
  }

  // ------------------------------------------------------- copy KDP listing
  async function copyListing(id) {
    try {
      const res = await fetch(`/api/books/${id}/kdp/listing`);
      if (!res.ok) throw new Error(`Listing not ready (${res.status})`);
      const text = await res.text();
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        // Fallback for environments without the async clipboard API.
        const ta = document.createElement("textarea");
        ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
        document.body.appendChild(ta); ta.select();
        document.execCommand("copy"); ta.remove();
      }
      toast("KDP listing copied to your clipboard.", { title: "Copied", type: "good" });
    } catch (err) {
      toast(err.message || "Couldn't copy the listing — try Auto-fill first.", { title: "Copy failed", type: "error" });
    }
  }
})();
