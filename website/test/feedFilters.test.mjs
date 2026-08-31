import test from "node:test";
import assert from "node:assert/strict";
import { availablePickerChannels, channelsForCategory } from "../src/feedFilters.js";

test("the compact categories keep email, chats, code, and reports distinct", () => {
  assert.deepEqual(channelsForCategory("email"), ["email"]);
  assert.deepEqual(channelsForCategory("messages"), ["teams", "slack", "telegram", "whatsapp", "imessage", "discord"]);
  assert.deepEqual(channelsForCategory("code"), ["github", "gitlab"]);
  assert.deepEqual(channelsForCategory("reports"), ["report", "assistant"]);
});

test("other contains the secondary systems and any future connected channel", () => {
  const other = channelsForCategory("other", ["email", "github", "assistant", "caldav"]);
  assert.ok(other.includes("jira"));
  assert.ok(other.includes("sentry"));
  assert.ok(other.includes("aws"));
  assert.ok(other.includes("caldav"));
  assert.ok(!other.includes("email"));
  assert.ok(!other.includes("github"));
  assert.ok(!other.includes("assistant"));
});

test("the detailed picker offers only channels that are actually available", () => {
  const available = ["email", "github", "assistant", "jira", "caldav"];
  assert.deepEqual(availablePickerChannels("reports", available), ["assistant"]);
  assert.deepEqual(availablePickerChannels("other", available), ["jira", "caldav"]);
  assert.deepEqual(availablePickerChannels("", available), available);
});

