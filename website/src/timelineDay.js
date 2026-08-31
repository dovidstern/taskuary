// A filter changes before its replacement request lands, so one render can have no current day.
// Bad source timestamps also belong in an explicit undated group—not JavaScript's literal
// "Invalid Date" string.
export const timelineDayLabel = (day, now = new Date()) => {
  if (!day) return "";
  if (day === "undated" || day === "Invalid Date") return "undated";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return "undated";
  const at = new Date(`${day}T00:00:00`);
  if (!Number.isFinite(at.getTime())) return "undated";
  const nice = at.toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" });
  const today = now.toLocaleDateString("sv-SE");
  const yest = new Date(now.getTime() - 864e5).toLocaleDateString("sv-SE");
  if (day === today) return `Today · ${nice}`;
  if (day === yest) return `Yesterday · ${nice}`;
  return nice;
};
