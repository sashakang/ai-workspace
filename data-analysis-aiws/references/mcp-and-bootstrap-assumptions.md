# MCP And Bootstrap Assumptions

This file defines what the plugin assumes from the environment.

## Required capabilities

The plugin assumes the user can access:
- a warehouse query path
- project memory imports when available in dev mode
- shared memory imports when available

## Standalone publish-mode rule

In publish/standalone mode, the plugin must work from:
- shipped references
- explicitly bundled or declared imports
- explicit MCP/bootstrap configuration

It must not rely on:
- ambient local memory
- ambient hooks
- undeclared host-specific files

## MCP rule

`.mcp.json` should contain:
- placeholders
- env-var-driven configuration
- no live credentials

## Bootstrap rule

Bootstrap docs should explain:
- what the user must configure
- what the plugin will attempt to read
- what is optional versus required
- how to validate the plugin is running cleanly
