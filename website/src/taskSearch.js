// Search the complete Tasks list client-side: /api/tasks already returns the full history, so a
// query can reveal old completed work immediately without another request or the "today" cutoff.
const FIELDS = [
  "ref", "TaskId", "Title", "Summary", "Kind", "Status", "Priority", "Assignee", "Source",
  "SourceRef", "Tags", "SearchChannels", "SearchSources", "SearchSubjects", "SearchPeople",
  "SearchEmails", "SearchExternalIds", "SearchLinks",
];

const folded = (value) => String(value ?? "").toLocaleLowerCase();

export const taskMatchesQuery = (task, query) => {
  const terms = folded(query).trim().split(/\s+/).filter(Boolean);
  if (!terms.length) return true;
  const haystack = folded(FIELDS.map((field) => task?.[field]).join(" "));
  return terms.every((term) => haystack.includes(term));
};
