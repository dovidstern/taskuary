// Taskuary updates underneath an open tab - a git pull and a rebuild, `pip install -U`, the
// coding agent shipping its own fix - and the tab goes on running the JavaScript it loaded at
// breakfast. Every symptom of that looks exactly like a bug that was already fixed, and from
// inside the page there is no way to tell the difference. (It cost this project an afternoon:
// three rounds of "still broken" against a build that was not being loaded.)
//
// So: what bundle did THIS page load, and what is on disk now. Nothing reloads itself - the
// owner may be mid-sentence in a terminal - it just says so.
export const loadedAsset = (doc = document) => {
  const src = [...doc.querySelectorAll("script[src]")].map((s) => s.getAttribute("src") || "")
    .find((s) => /assets\/index-[^/]+\.js$/.test(s)) || "";
  return src.split("/").pop() || "";
};

/** Is the served bundle a DIFFERENT one from the one running? Unknown answers are never stale. */
export const isStale = (loaded, served) => !!loaded && !!served && loaded !== served;
