// SPDX-License-Identifier: Apache-2.0
// Copyright (c) The CivicSuite Authors

import { spawnSync } from "node:child_process";
import path from "node:path";
import process from "node:process";

const gates = [
  ["vitest", path.resolve("node_modules", "vitest", "vitest.mjs"), ["run", "src", "tests"]],
  [
    "playwright",
    path.resolve("node_modules", "@playwright", "test", "cli.js"),
    ["test", "e2e/skip-link-no-occlude.spec.ts"]
  ]
];

// Some historical audit instructions invoke `npm test -- --run`. Vitest is
// already pinned to run mode above; accepting and intentionally ignoring that
// redundant argument prevents npm from forwarding it to Playwright, where it
// is not a valid option.
const unsupported = process.argv.slice(2).filter((argument) => argument !== "--run");
if (unsupported.length > 0) {
  console.error(`Unsupported test-gate arguments: ${unsupported.join(" ")}`);
  process.exit(2);
}

for (const [name, entryPoint, args] of gates) {
  const result = spawnSync(process.execPath, [entryPoint, ...args], {
    cwd: process.cwd(),
    env: process.env,
    stdio: "inherit"
  });
  if (result.error) {
    console.error(`Could not start ${name}: ${result.error.message}`);
    process.exit(1);
  }
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}
