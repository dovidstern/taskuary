// How much a Timeline row dims with age (Settings > Display > Fade older Timeline items). Kept out
// of the React tree so the curve itself is testable: the whole point of the setting is that each
// mode reaches a visibly different place at the same age, and only a table of numbers proves that.
//
// {grace hours before it starts, span hours from there to the floor, floor}. On the cream palette a
// gentle fade is nearly invisible; normal is the default so the live part stays distinct without
// rows becoming quiet as abruptly as the sharper option.
export const FADE = { off: null, gentle: [2, 20, 0.7], normal: [0.5, 5, 0.5], sharp: [0.33, 2, 0.35] };

export const FADE_MODES = Object.keys(FADE);

// Purely visual, and a resting state rather than a filter: FeedView restores any row to full while
// the list is being scrolled or a row is hovered, so nothing is ever hidden from someone reading.
export const ageOpacity = (hours, mode = "normal") => {
  const c = FADE[mode];
  if (!c || !(hours > 0)) return 1;                 // unknown mode, 'off', a future or unparsed time
  const [grace, span, floor] = c;
  return hours <= grace ? 1 : Math.max(floor, 1 - (1 - floor) * (hours - grace) / span);
};

// A deliberate filter is already doing the visual prioritization. Dimming its matches again can
// make the whole result set look disabled when every match happens to be old.
export const timelineOpacity = (hours, mode = "normal", filtered = false) =>
  filtered ? 1 : ageOpacity(hours, mode);

// The bottom dissolve is a scroll affordance, not decoration. A short list ends above the
// viewport; drawing the 190px gradient there covers the very rows it is meant to frame.
// Keep the small cushion so a fractional layout pixel at the fold cannot make it flicker.
export const bottomDissolveVisible = (listBottom, viewportHeight, cushion = 16) =>
  Number.isFinite(listBottom) && Number.isFinite(viewportHeight)
    && listBottom > viewportHeight + cushion;
