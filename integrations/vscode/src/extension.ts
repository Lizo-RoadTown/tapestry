/**
 * Tapestry VS Code extension entry point.
 *
 * Registers Tapestry's MCP servers (memory + docs) with VS Code's Language
 * Model API so they're available to Copilot Chat and other MCP-aware
 * consumers. Uses `vscode.lm.registerMcpServerDefinitionProvider` per the
 * MCP-server-provider extension guide.
 *
 * v0.1.0 scope: register the two servers; honor settings for the memory
 * URL + docs command; skip a server cleanly when not configured. No UI,
 * no command palette ops — those land in v0.2.
 */
import * as vscode from "vscode";

const PROVIDER_ID = "tapestry.mcpServers";

export function activate(context: vscode.ExtensionContext): void {
  const didChangeEmitter =
    new vscode.EventEmitter<void>();

  const provider: vscode.McpServerDefinitionProvider = {
    onDidChangeMcpServerDefinitions: didChangeEmitter.event,

    provideMcpServerDefinitions: async () => {
      const config = vscode.workspace.getConfiguration("tapestry");
      const memoryUrl = (config.get<string>("memoryMcpUrl") ?? "").trim();
      const docsCommand = (
        config.get<string>("docsMcpCommand") ?? "python"
      ).trim();
      const docsEnabled = config.get<boolean>("docsMcpEnabled") ?? true;

      const defs: vscode.McpServerDefinition[] = [];

      // tapestry-docs — stdio MCP. Requires `pip install tapestry-docs-mcp`
      // on the same Python the user names here.
      if (docsEnabled) {
        defs.push(
          new vscode.McpStdioServerDefinition(
            "tapestry-docs",
            docsCommand,
            ["-m", "docs_mcp"],
          ),
        );
      }

      // loom-memory — HTTP MCP at the user's deployment URL. Skip cleanly
      // if unset (don't break the extension on fresh install).
      if (memoryUrl !== "") {
        try {
          defs.push(
            new vscode.McpHttpServerDefinition(
              "loom-memory",
              vscode.Uri.parse(memoryUrl),
            ),
          );
        } catch (err) {
          // Bad URL in settings — surface once, don't crash.
          void vscode.window.showWarningMessage(
            `Tapestry: tapestry.memoryMcpUrl is set but invalid: ${memoryUrl}`,
          );
        }
      }

      return defs;
    },

    resolveMcpServerDefinition: async (server) => server,
  };

  context.subscriptions.push(
    vscode.lm.registerMcpServerDefinitionProvider(PROVIDER_ID, provider),
  );

  // Re-emit when the user changes settings so the providers update without
  // reloading the window.
  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (
        e.affectsConfiguration("tapestry.memoryMcpUrl") ||
        e.affectsConfiguration("tapestry.docsMcpCommand") ||
        e.affectsConfiguration("tapestry.docsMcpEnabled")
      ) {
        didChangeEmitter.fire();
      }
    }),
  );
}

export function deactivate(): void {
  // No teardown needed — subscriptions handle disposal via context.
}
