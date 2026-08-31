const FIXED = {
  email: ["email"],
  messages: ["teams", "slack", "telegram", "whatsapp", "imessage", "discord"],
  code: ["github", "gitlab"],
  reports: ["report", "assistant"],
  other: ["jira", "asana", "monday", "clickup", "todoist", "linear", "trello", "notion", "azdo",
    "sentry", "pagerduty", "aws", "azure"],
};

const PRIMARY = new Set([...FIXED.email, ...FIXED.messages, ...FIXED.code, ...FIXED.reports]);
const unique = (xs) => [...new Set(xs.filter(Boolean))];

// "Other" is intentionally open-ended: a newly connected channel must not require another pill
// before it can be found. The broad pills stay stable while the source picker remains exact.
export const channelsForCategory = (category, discovered = []) => {
  if (!category) return null;
  if (category !== "other") return FIXED[category] ? [...FIXED[category]] : [];
  return unique([...FIXED.other, ...discovered.filter((channel) => !PRIMARY.has(channel))]);
};

export const availablePickerChannels = (category, discovered = []) => {
  const available = unique(discovered);
  const scoped = channelsForCategory(category, available);
  return (scoped || available).filter((channel) => available.includes(channel));
};

