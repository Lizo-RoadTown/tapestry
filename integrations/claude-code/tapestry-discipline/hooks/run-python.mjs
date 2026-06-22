#!/usr/bin/env node
/**
 * run-python.mjs — Node launcher for the Python hook scripts.
 *
 * Why this exists: Claude Code guarantees Node on PATH (it runs on Node).
 * It does NOT guarantee Python on PATH — confirmed against anthropics/
 * claude-code #16131, #15908, #46449, all closed without an official fix.
 *
 * This launcher finds Python intelligently across platforms and invokes the
 * named hook script. Each hook in hooks.json calls:
 *
 *    node "${CLAUDE_PLUGIN_ROOT}/hooks/run-python.mjs" <script_basename>
 *
 * where <script_basename> is one of: user_prompt_submit, pre_tool_use,
 * stop_audit, session_start.
 *
 * stdin is piped through to the Python script unchanged. stdout from the
 * Python script is echoed to stdout so Claude Code's hook plumbing sees it.
 * The launcher exits 0 except when the Python script explicitly exits 2
 * (the "block" exit code documented in Claude Code's hook protocol).
 */
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const pluginRoot = process.env.CLAUDE_PLUGIN_ROOT || dirname(__dirname);

const scriptName = process.argv[2];
if (!scriptName) {
  console.error("run-python.mjs: missing script name argument");
  process.exit(0); // never block on launcher misconfiguration
}

const pythonScript = join(pluginRoot, "scripts", `${scriptName}.py`);
if (!existsSync(pythonScript)) {
  console.error(`run-python.mjs: script not found: ${pythonScript}`);
  process.exit(0);
}

// Candidate Python invocations in priority order.
//   Windows: `py -3` (Python Launcher, always installed with python.org Python)
//   Unix:    `python3` then `python`
//   Fallback for unusual installs: `python`
const isWindows = process.platform === "win32";
const candidates = isWindows
  ? [
      ["py", ["-3", pythonScript]],
      ["python", [pythonScript]],
      ["python3", [pythonScript]],
    ]
  : [
      ["python3", [pythonScript]],
      ["python", [pythonScript]],
    ];

// Read all of stdin once so we can replay it for each retry.
let stdinBuf = Buffer.alloc(0);
try {
  // Synchronous stdin read — hooks are short-lived.
  const fs = await import("node:fs");
  stdinBuf = fs.readFileSync(0);
} catch {
  // stdin closed or empty — proceed with no input.
}

let lastExitCode = 0;
let invoked = false;
for (const [cmd, args] of candidates) {
  try {
    const result = spawnSync(cmd, args, {
      input: stdinBuf,
      stdio: ["pipe", "inherit", "inherit"],
    });
    if (result.error && result.error.code === "ENOENT") {
      // This Python candidate isn't on PATH — try the next.
      continue;
    }
    invoked = true;
    lastExitCode = result.status ?? 0;
    break;
  } catch {
    continue;
  }
}

if (!invoked) {
  // No Python found. Hook can't run; emit a one-line diagnostic to stderr
  // for /doctor to surface but DO NOT block the session.
  console.error(
    "run-python.mjs: no Python on PATH (tried py -3, python3, python). " +
      "Install Python or add it to PATH. Hook skipped, not blocking.",
  );
  process.exit(0);
}

// Pass through the Python exit code so block-decisions propagate.
process.exit(lastExitCode);
