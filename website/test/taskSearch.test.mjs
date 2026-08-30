import test from "node:test";
import assert from "node:assert/strict";
import { taskMatchesQuery } from "../src/taskSearch.js";

const task = {
  TaskId: 412,
  ref: "TQ-0412",
  Title: "Fix validation",
  Summary: "Contributor updated the branch",
  Kind: "coding",
  Status: "done",
  Source: "github",
  SourceRef: "https://github.com/org/app/pull/31",
  Tags: "repo:org/app",
  SearchChannels: "github",
  SearchSources: "org/app",
  SearchSubjects: "org/app#31 Fix validation",
  SearchPeople: "Octo Cat",
  SearchEmails: "octocat@users.noreply.github.com",
  SearchExternalIds: "gh:org/app#31",
  SearchLinks: "https://github.com/org/app/pull/31",
};

test("task search covers references, titles, summaries, systems, people, and linked PR data", () => {
  for (const query of ["TQ-0412", "validation", "updated branch", "github", "org/app", "octo cat", "pull/31", "#31"]) {
    assert.equal(taskMatchesQuery(task, query), true, query);
  }
});

test("multiple terms are ANDed across fields and matching is case-insensitive", () => {
  assert.equal(taskMatchesQuery(task, "GITHUB contributor 31"), true);
  assert.equal(taskMatchesQuery(task, "github contributor 99"), false);
});

test("an empty query leaves every task visible", () => {
  assert.equal(taskMatchesQuery(task, "   "), true);
});
