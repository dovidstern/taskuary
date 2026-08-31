// A meeting stops being "upcoming" at its start time. It remains a calendar row, but from then
// on it belongs at that timestamp among the Timeline's messages instead of staying pinned above
// newer activity. All-day events remain in the upcoming band because they have no useful time.
export const meetingHasStarted = (event, nowMs = Date.now(), timestamp = Date.parse) => {
  if (!event || event.all_day || !event.start) return false;
  const startMs = timestamp(event.start);
  return Number.isFinite(startMs) && startMs > 0 && startMs <= nowMs;
};

export const splitTimelineMeetings = (events, nowMs = Date.now(), timestamp = Date.parse) => {
  const started = [];
  const upcoming = [];
  for (const event of events || []) {
    (meetingHasStarted(event, nowMs, timestamp) ? started : upcoming).push(event);
  }
  return { started, upcoming };
};
