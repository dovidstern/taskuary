import test from "node:test";
import assert from "node:assert/strict";
import { readNdjson, toolTarget } from "../src/assistantStream.js";

test("assistant events survive arbitrary network chunk boundaries", async () => {
  const encoder = new TextEncoder();
  const body = new ReadableStream({ start(controller) {
    controller.enqueue(encoder.encode('{"type":"tool_call","name":"B'));
    controller.enqueue(encoder.encode('ash"}\n{"type":"done","reply":"ok"}\n'));
    controller.close();
  } });
  const got = [];
  for await (const event of readNdjson(body)) got.push(event);
  assert.deepEqual(got, [{ type: "tool_call", name: "Bash" }, { type: "done", reply: "ok" }]);
});

test("tool cards lead with the useful argument", () => {
  assert.equal(toolTarget({ command: "rg hospitals" }), "rg hospitals");
  assert.equal(toolTarget({ query: "medical facilities news" }), "medical facilities news");
});
