---
title: Set up GitHub
description: A GitHub account and access — for the Tapestry plugin marketplace, for connecting Render and Vercel to your deployment repo, and for publishing your own plugins.
---

GitHub is where the platform's plugins are published, where your self-host deployment connects, and where your own plugins live. A free account covers all of it.

## What you need

- A [GitHub account](https://github.com/).
- The [`gh` CLI](https://cli.github.com/) (optional but recommended), authenticated: `gh auth login`.

## For the plugins

The Tapestry marketplace is the public repo `Lizo-RoadTown/tapestry`. `/plugin marketplace add Lizo-RoadTown/tapestry` resolves it — no special access, it's public. (See [Set up Claude Code](/how-to/set-up-claude-code/).)

## For your own deployment

If you self-host, Render and Vercel connect to a GitHub repo that holds your backend and frontend. You authorize each service to read that repo, and they build from it. See [Set up Render](/how-to/set-up-render/) and [Set up Vercel](/how-to/set-up-vercel/).

## For your own plugins

When a project's shape calls for its own plugin, you generate one with `tapestry make-plugin` and publish it to a repo under **your** account as **your** marketplace:

```bash
gh repo create <your-github>/<plugin-name> --public --source . --push
```

Then in Claude Code:

```text
/plugin marketplace add <your-github>/<plugin-name>
```

See [Create your own plugin](/how-to/create-your-own-plugin/).
