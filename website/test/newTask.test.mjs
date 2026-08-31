// "New task for the agent" has one question that decides everything under it: which repository.
// It opened in a terminal whatever you answered - including "General - no repository, just a
// question to answer", which has no checkout for a CLI to stand in and belongs in the chat.
import assert from "node:assert/strict";
import test from "node:test";
import { NO_REPO, planTask, repoOf } from "../src/newTask.js";

test("a repository means a coding task for a CLI in that checkout", () => {
  const p = planTask("acme/fanapp", "live");
  assert.equal(p.kind, "coding");
  assert.equal(p.chat, false);
  assert.equal(p.repo, "acme/fanapp");
  assert.equal(p.tags, "repo:acme/fanapp");
});

test("General means a general task, worked in the assistant's chat", () => {
  const p = planTask(NO_REPO, "live");
  assert.equal(p.kind, "general");
  assert.equal(p.chat, true);
  assert.equal(p.repo, null);
});

test("no repository is never written as a repo tag", () => {
  assert.equal(planTask(NO_REPO, "live").tags, null);   // 'repo:none' was a tag pointing at nothing
  assert.equal(planTask("", "live").tags, null);
});

test("an empty picker - no repositories connected at all - is the chat, not a terminal", () => {
  assert.equal(planTask("", "live").chat, true);
  assert.equal(planTask(undefined, "live").kind, "general");
});

test("'just file it' starts nobody, on either kind", () => {
  assert.equal(planTask("acme/fanapp", "file").start, false);
  assert.equal(planTask(NO_REPO, "file").start, false);
  assert.equal(planTask(NO_REPO, "live").start, true);
});

test("repoOf is what the API is given", () => {
  assert.equal(repoOf("acme/fanapp"), "acme/fanapp");
  assert.equal(repoOf(NO_REPO), null);
  assert.equal(repoOf(""), null);
});
