# AIWS for Cowork — Setup and User Guide

A practical guide for Cowork users who want to use team-shared skill libraries.

You already know Cowork. You've used it for a while. You know what a "skill" is in Cowork — a packaged way for Claude to do a specific task, available either as a slash command or by natural-language trigger.

This guide adds one new idea on top of what you already know:

> A **skill library** is a folder on Google Drive your team shares. It holds a set of skills your whole team can install, use, and improve together. AIWS is the tooling that connects that Drive folder to your Cowork.

That's it. No new accounts, no scripts to run by hand. Once AIWS is set up, you work mostly by typing in chat.

---

## What AIWS is

**AIWS** stands for **AI Workspace**. It's two things glued together:

- A **convention** for how a team-shared skill library looks on Google Drive — a specific folder shape that any AIWS-aware tool can read and write.
- A small set of **Cowork skills** that act on libraries in that shape — `install`, `refresh`, `validate`, and `propose`. They live inside a Cowork plugin called `core-aiws`.

You don't learn a new app. AIWS adds a few extra prompts you can type in Cowork, and a few extra files (kept on Drive) that the prompts read from and write to. Everything else — running skills, plugins, chat — is the Cowork you already know.

If you've used a shared Google Drive folder for team documents, the mental model is similar: a folder one team owns, with a known layout, and tools that know how to read and write that layout. AIWS does the same for skill libraries.

## How it works (the 30-second version)

1. **Drive is the source of truth.** Your team keeps the canonical skills in a Drive folder. Whoever can see the folder can install the library.
2. **Cowork pulls a copy.** AIWS reads the Drive folder, packages it, and installs it as a plugin in your Cowork. From that point on, every skill in the library is callable from chat — `Use <skill-id>` or `/<plugin-id>:<skill-id>`.
3. **You propose changes.** When you want to share a new skill or improve an existing one, you author the change in your own Cowork first, test it, then run a single propose prompt. AIWS drops your version into a `Proposals/Submitted/` folder on the team's Drive. A maintainer reviews the diff and either accepts it (it becomes the new canonical), edits it, or rejects it.
4. **Everyone refreshes.** A `Refresh <Library Name>` prompt pulls the latest canonical content into each teammate's Cowork. Your library stays in sync with the team without anyone re-installing anything.

No hidden state, no separate accounts, no command-line work. Just Cowork prompts and a shared Drive folder you can open in your browser to inspect at any time.

The rest of this guide is the concrete recipe — what to type, what to click, and what to do when something looks off.

---

## Part 1 — Setup (one-time, ~5 minutes)

### What you need before you start

- Cowork installed and signed in. (You have this.)
- A Google account that can read the team's Drive folder.
- The URL of the team's shared Drive folder. Someone on your team — your skill library maintainer — sends you this. It looks like `https://drive.google.com/drive/folders/1Ab…`.

### Steps

1. **Add the AIWS marketplace, then install the plugin.**
   AIWS isn't in Cowork's default plugin list — you add the marketplace it lives in first, then install the plugin from it.

   - **Customize** → **Browse Plugins** → **Personal** → **+** → **Add marketplace**
   - Type: `sashakang/ai-workspace`
   - Click **Sync**.

   After Sync, the marketplace's plugins appear in the same Browse Plugins view. Find **core-aiws** (or **AIWS**) → click the **+** sign next to it.

   You only do this once per machine. After install, AIWS-managed skills appear in your skill list with names starting with `aiws-` (for example `aiws-install-drive-skill-library`, `aiws-refresh-skill-library`).

2. **Connect Google Drive.**
   In Cowork's connectors / integrations panel, find Google Drive and sign in. Grant Cowork permission to read your Drive files. (AIWS uses Cowork's existing Drive connection — there's no separate AIWS-to-Drive login.)

3. **Install your team's skill library.**

   First, get the Drive folder's shared URL:

   - Open Google Drive in a browser.
   - Navigate into the team's skill library folder so you can see its contents.
   - **Easiest path**: copy the URL straight from your browser's address bar. It looks like `https://drive.google.com/drive/folders/1AbC…`.
   - **If you need to be granted access first**: right-click the folder in Drive → **Share** → make sure the sharing settings include your account (or "Anyone at <your company>"), then click **Copy link**. The URL you copy is the same form.

   Then in a new Cowork chat, type:

   ```
   Install <Library Name> from this Drive folder: <paste the URL here>
   ```

   `<Library Name>` must be the exact name of the Drive folder — not a free-text label. For example, if the folder on Drive is called `Marketing Skills`, the prompt is `Install Marketing Skills from this Drive folder: <url>`. Cowork uses the folder name to derive the plugin id (e.g. `marketing-skills`), so it has to match.

   Cowork will read the folder, build a plugin from it, and show you a card with a **Save plugin** button. Click it.

   After clicking Save plugin, the library's skills appear in your Cowork skills list, prefixed with the library's plugin id (e.g. `marketing-skills:weekly-report`).

That's setup. You're now sharing skills with your team.

### Sanity check

In a new chat, type:

```
Validate the <Library Name> Drive library and include installed plugin status
```

Cowork should respond with a checklist that ends in `PASS` and confirm the library is installed.

---

## Part 2 — Daily use

### Run a team skill

Same as any other Cowork skill:

```
Use weekly-report
```

or with the slash command:

```
/marketing-skills:weekly-report
```

Cowork routes to the team-shared version. If your teammate ships an improvement to `weekly-report`, you'll get the new version after a refresh (see below).

### See what's in the library

Ask Cowork in plain language:

```
What skills are in <Library Name>?
```

Or list everything installed:

```
List my installed skills
```

### Pick up new versions or new skills the team added

Skills the team adds or improves only land in your Cowork after you refresh. In a chat:

```
Refresh <Library Name>
```

Cowork compares what's on Drive with what you have installed, and if something changed it'll show a **Save plugin** card with the new version. Click Save plugin. You now have the team's latest.

If nothing changed since the last refresh, Cowork tells you "no rebuild required" — your library is already up to date.

> **When to refresh:** start of the day, after a teammate tells you they shipped something, or when a skill seems out of date. There's no auto-refresh.

---

## Part 3 — Contributing a new skill (or improving one)

This is the part most users don't realize they can do. It's a three-step rhythm: **author locally → try it → propose it**. AIWS only enters at the propose step.

### Step 1. Author a local skill

You write the skill body — a short Markdown file that tells Claude what to do, when to trigger, and how to format the output. The simplest skill is just a single SKILL.md file like:

```
---
name: weekly-report
description: Draft my weekly status report based on this week's calendar and notes.
---

# Weekly report

Use this skill when the user asks for a weekly status, weekly recap, or "what did I get done this week".

Pull this week's calendar events and any meeting notes I share. Produce a short report with:
- Key meetings (3–5 bullets)
- Wins (what shipped, what was decided)
- Open items (waiting on, blocked on)
- Next week focus (1–2 sentences)

Keep it under 200 words. Plain prose, no tables.
```

Tell Cowork:

```
Create a local user skill named weekly-report with the SKILL.md content above
```

Cowork packages it and shows a **Save skill** card. Click Save skill.

### Step 2. Try the skill

Run it like any other:

```
Use weekly-report
```

Tweak the SKILL.md body until you're happy. Each time you change it, repeat the Save skill step.

### Step 3. Propose it to the team

When you're ready to share:

```
Propose this new skill for <Library Name>: weekly-report. Use my local weekly-report SKILL.md as the proposed content.
```

Cowork drops your skill into a `Proposals/Submitted/` folder on the team's Drive. The library maintainer reviews it, and either accepts (your skill becomes canonical and everyone gets it on their next refresh) or sends comments back.

You'll know it landed when:

- A `Refresh <Library Name>` after the maintainer accepts shows the new skill in the library
- Cowork can route `Use weekly-report` to `marketing-skills:weekly-report` (the team-canonical version) instead of just your local `anthropic-skills:weekly-report`

### Improving an existing skill

Same three-step rhythm, but:

- For Step 1, start by copying the existing canonical SKILL.md and editing it. You can ask Cowork: "give me the canonical content of `weekly-report` from `<Library Name>` so I can edit a copy locally."
- For Step 3, the proposal command looks like:

  ```
  Propose this weekly-report change for <Library Name>: use my current local weekly-report SKILL.md as the proposed content.
  ```

  Cowork puts your version alongside the existing canonical in a Drive diff that the maintainer reviews.

### After your proposal lands

Run a refresh to pull the team-canonical version into your Cowork:

```
Refresh <Library Name>
```

Once the team version matches what you proposed, you can remove your local copy via Cowork's skill panel. Your local edits are no longer needed — the team owns the canonical.

> **If you've already started v.2 locally**, keep your local copy. It will keep overriding the team version until you propose v.2 and the team accepts that too.

---

## Part 4 — If you're a library maintainer

You'll be asked when someone on your team is set up to do this — typically the person who created the library or a small group with edit access to the Drive folder.

### Where pending proposals live

Inside your team's Drive library folder:

```
<Library Name>/Proposals/Submitted/<skill-id>/<proposal-id>/
   SKILL.md             ← the proposed content
   aiws.proposal.json   ← who, when, why
```

A new proposal puts a folder here. Accepted proposals move to `Proposals/Approved/`, and the canonical `SKILL.md` they replaced is kept under `<Library Name>/Archive/` (see Accept below).

### Review a proposal

Use **Meld** — a free, cross-platform visual diff tool — to compare the proposed SKILL.md against the current canonical side by side.

#### Install Meld (one-time)

- **macOS** (recommended path, via Homebrew):

  ```bash
  brew install --cask meld
  ```

  If you don't have Homebrew yet, install it first from <https://brew.sh>. After installing Meld, open it once from **Applications** so macOS Gatekeeper marks it as trusted.

- **Ubuntu / Debian Linux**: `sudo apt install meld`
- **Fedora / RHEL Linux**: `sudo dnf install meld`
- **Windows**: download the installer from <https://meldmerge.org> and run it.

#### Open a side-by-side diff

You need both files available locally. Google Drive's desktop client should be syncing your team's library folder to your machine. On macOS the local path typically looks like:

```text
~/Library/CloudStorage/GoogleDrive-<your-email>/My Drive/<Library Name>/
```

Launch Meld → choose **File Comparison** → pick the two files:

- **Left pane**: `<local Drive path>/<Library Name>/skills/<skill-id>/SKILL.md` — the current canonical.
- **Right pane**: `<local Drive path>/<Library Name>/Proposals/Submitted/<skill-id>/<proposal-id>/SKILL.md` — the proposed change.

Meld highlights additions, deletions, and modifications in color. Read both panes and decide what you accept. You can edit either pane directly in Meld and save — useful if you want to do a partial accept (see below).

Shortcut from the terminal once you know the paths:

```bash
meld "/path/to/canonical/SKILL.md" "/path/to/proposed/SKILL.md"
```

For a **brand-new skill**, there's no canonical to diff against. Just open the proposed `SKILL.md` in any text editor or Meld's single-file view and read it standalone.

### Accept

Don't copy the proposed `SKILL.md` into the skill folder by hand. Drive doesn't replace a file with the same name; it puts a second `SKILL.md` next to the first, and validation then fails.

For a full accept (you're fine with the proposed content as-is):

1. In Drive, move the whole `Proposals/Submitted/<skill-id>/<proposal-id>/` folder to `Proposals/Approved/<skill-id>/` (create that folder if it doesn't exist yet). This move is your approval; Cowork never does it for you.
2. In Cowork, type:

   ```text
   Accept proposal <proposal-id> for <Library Name>
   ```

   If the same proposal id exists for two skills, Cowork asks you to use `Accept proposal <proposal-id> for <skill-id> in <Library Name>`.

Cowork then:

- moves the current canonical to `<Library Name>/Archive/<skill-id>/<YYYY-MM-DD>-<proposal-id>/SKILL.md`,
- puts the proposed file in its place, leaving exactly one `SKILL.md` in the skill folder (for a brand-new skill it creates the skill folder),
- raises the library's plugin version in `<Library Name>/aiws.library.json` (creating the file if it doesn't exist), so teammates' Cowork picks up the change on refresh,
- validates the library and refreshes it, which ends with a **Save plugin** button for you to click.

Only `SKILL.md` is replaced; other files in the skill folder are untouched. The canonical becomes a new Drive file, so Drive's version history for the previous text lives with the archived copy.

Cowork stops and asks before replacing anything if the canonical changed after the proposal was written, or if it can't tell when the proposal was written. The report shows both times. This check can't see a proposal written from an outdated copy of the skill: if the proposer worked from an old local copy, newer canonical edits are overwritten. The archived copy keeps them, so you can restore them by hand. Anyone with write access to `Proposals/Approved/` can approve, so keep that access to maintainers.

If you already accepted this proposal, running the command again reports that the canonical is already in sync and only refreshes.

For a partial accept (you take some of it, edit some, reject some):

1. Edit `<Library Name>/skills/<skill-id>/SKILL.md` directly to reflect what you accept. Drive's own version history keeps the diff.
2. Move the `Proposals/Submitted/<skill-id>/<proposal-id>/` folder to `Proposals/Approved/<skill-id>/` as the record. Don't run `Accept proposal` on it afterwards: that would replace your edited version with the full proposal.
3. Run `Bump plugin version for <Library Name>`, then `Refresh <Library Name>`.

To reject, move the proposal folder to `Proposals/Rejected/<skill-id>/`.

### Files besides SKILL.md

A skill folder can hold reference files next to `SKILL.md`, for example `references/metrics.md`, `REFERENCE.md`, PNG/JPG/GIF images, or PDFs. Install and refresh package these with the skill, so a skill that points at them keeps working in Cowork. Editing one of them on Drive and running `Refresh <Library Name>` picks up the change.

Scripts (anything in a `scripts/` folder, or files like `.py` and `.sh`) are not installed. Neither are README files, dotfiles, or other file types such as `.html` or `.docx`. The install report lists every skipped file by name, so you can see what was left out. Files that would change how Cowork behaves (hooks, `.mcp.json`, settings files) make the install fail instead of being skipped. Google Docs, Sheets, and Drive shortcuts can't be packaged either; save the content as a Markdown or PDF file in the skill folder instead.

Changes to these files don't go through the proposal flow: proposals carry only `SKILL.md`. Anyone who can edit the Drive library can change them directly.

### Plugin version

Cowork installs a library as a plugin with a version number, and it may ignore a refreshed plugin whose version didn't change. The version lives in `<Library Name>/aiws.library.json` as `plugin_version`. Install and refresh only read it; `Accept proposal` raises it for you. After any edit you make directly in Drive (a partial accept, a changed reference file, a removed file), run:

```text
Bump plugin version for <Library Name>
```

If you forget, a teammate's refresh stops with `NEEDS MANUAL ACTION`, names the files changed since the last bump, and asks them to message you. Removing a file leaves nothing newer behind, so refresh can't notice a removal: bump after removals yourself. Copying the library folder in Drive can also make refresh stop this way; one bump fixes it.

If a teammate's refresh says their installed version is already at or above the library's (common for libraries installed before AIWS tracked versions), run:

```text
Bump plugin version for <Library Name> past <version>
```

with the installed version from their report. The library then jumps past it.

### Telling your team

Just message them — your team's normal channel, e.g. Slack — that the library has a new version. They run `Refresh <Library Name>` on their side and pick it up.

---

## Part 5 — Troubleshooting

### "I clicked Save skill but the new skill doesn't appear"

The skill is registered — restart Cowork to make it appear in the in-memory skill list, or refresh whichever panel you're looking at. Once it's there, it survives restarts.

### "After uninstalling a local skill from Cowork's UI, it came back"

Cowork remembers your local skills in memory and writes them back to disk on quit. To truly remove a local skill, use Cowork's **skill panel** (not file-side deletion) — that goes through the proper uninstall path.

### "Refresh says no rebuild required, but I expected an update"

You're already up to date with what's on Drive. If you were expecting your teammate's change, they may not have accepted the proposal into canonical yet, or Drive sync is still catching up (usually seconds, sometimes a minute or two). Wait a beat and try again.

### "Validation says there are two SKILL.md files in one folder"

Someone copied a `SKILL.md` into a folder that already had one, and Drive kept both. The validation report lists each copy with its modified time and size. Keep the one you want and move the other out of the folder (for example into `<Library Name>/Archive/`). To accept a proposal next time, use `Accept proposal <proposal-id> for <Library Name>` instead of copying by hand.

### "Accept proposal says the proposal is still in Submitted"

Move the proposal folder to `Proposals/Approved/<skill-id>/` in Drive first, then run the command again. Cowork doesn't move it for you, because that move is the maintainer's approval.

### "Accept proposal stopped and says the skill folder has no SKILL.md"

Accept was interrupted between moving the old file out and putting the new one in. Open `<Library Name>/skills/<skill-id>/` in Drive and rename `SKILL.md.incoming` to `SKILL.md`, or move the archived `SKILL.md` from the `Archive/` path in the report back into the skill folder and trash `SKILL.md.incoming`. Then run `Refresh <Library Name>`.

If the report says validation failed after the accept, the new `SKILL.md` is in place but broken. Fix it in Drive, or trash it and move the archived copy back, so the folder again holds exactly one `SKILL.md`. Then refresh.

If Cowork can't copy, move, or rename files in Drive, it changes nothing and gives you the exact steps to do by hand (report status `NEEDS MANUAL ACTION`).

### "I see a 'Save skill' button but I'm trying to install a library"

That's wrong — for a library you need **Save plugin** (a multi-skill install). Tell Cowork to repackage as a `.plugin` artifact:

```
Install <Library Name> from this Drive folder: <url>
```

If it still shows Save skill, capture the error and report it — this is a regression of a guard in AIWS.

### "I see a 'Save plugin' button but I'm trying to register one local skill"

Mirror image of the above. Tell Cowork:

```
Create a local user skill named <skill-id> with the following SKILL.md body: ...
```

It should produce a `.skill` artifact with **Save skill**.

### "AIWS commands don't seem to do anything"

Check that the AIWS plugin (core-aiws) is installed and enabled in Cowork's plugin panel. If it's missing or disabled, install/enable it.

### "I can read the Drive library but I can't propose"

Google Drive is connected in read-only mode. Open Cowork's connectors panel, reconnect Google Drive, and grant write permission. (Most read-only connectors don't make this obvious — if propose fails with a permission error, this is almost always the cause.)

### "I want to test something without affecting the team"

Author it locally only. Don't propose. Your local skill overrides the team's same-name skill on your Cowork only — teammates see nothing. When you're done experimenting, remove the local skill via Cowork's skill panel.

---

## Cheat sheet — every prompt you'll use

Replace `<Library Name>` with your team's library name (e.g. "Marketing Skills") and `<url>` with the Drive folder URL.

| Goal | Prompt |
|---|---|
| Install the library | `Install <Library Name> from this Drive folder: <url>` |
| Verify state | `Validate the <Library Name> Drive library and include installed plugin status` |
| Pick up team changes | `Refresh <Library Name>` |
| List your skills | `List my installed skills` |
| Run a skill | `Use <skill-id>` or `/<plugin-id>:<skill-id>` |
| Author a local skill | `Create a local user skill named <skill-id> with the following SKILL.md body: ...` |
| Propose a new skill | `Propose this new skill for <Library Name>: <skill-id>. Use my local <skill-id> SKILL.md as the proposed content.` |
| Propose a change | `Propose this <skill-id> change for <Library Name>: use my current local <skill-id> SKILL.md as the proposed content.` |
| Read a canonical skill | `Show me the canonical <skill-id> SKILL.md from <Library Name>` |
| Bump the version after a direct Drive edit (maintainer) | `Bump plugin version for <Library Name>` |

That's the whole user-facing surface for skill-library work.

---

## Where to go for more

- Library maintainers: keep an eye on `<Library Name>/Proposals/Submitted/` once a week or whenever someone messages you about a new submission.
- Teammates getting started: ask your library maintainer for the library's Drive URL and run the install command in Part 1.
- Stuck or something looks wrong: check Part 5 first; if it's not there, message your library maintainer or whoever set up AIWS for your team.
