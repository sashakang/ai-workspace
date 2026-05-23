# AIWS Cowork First-Class Drive Plugins Plan

**Status:** Slice 2 bridge publication complete; Cowork native visibility blocked
**Date:** 2026-05-22  
**Owner:** AIWS development

## Summary

Make AIWS-compatible Google Drive marketplace domain plugins visible through a Cowork-native plugin path without weakening the current source-of-truth boundary:

- `core-aiws` remains infrastructure distributed from the original GitHub `ai-workspace` marketplace.
- `Checkout Main` remains the Google Drive authoring, review, and release backend for the demo domain plugin `productivity:meeting-followup`.
- Cowork remains the owner of native plugin catalog visibility, install, update, and activation.

AIWS cannot make a Google Drive marketplace row appear in Cowork's native plugin Directory only by materializing a skill or copying an adapter package. Cowork currently documents native plugin distribution through its marketplace/catalog surfaces, Git repository marketplaces, organization-managed manual marketplaces, and file upload. The first AIWS-controlled implementation should therefore be a **bridge publication path** from a published Drive release into a Cowork-native marketplace shape. A true Cowork-native Drive marketplace provider is a separate Cowork product integration dependency.

## First-Class Definition

An AIWS-compatible domain plugin is first-class in Cowork only when a normal Cowork user can:

1. See the plugin in a Cowork-native plugin marketplace/catalog surface.
2. Install it through Cowork without AIWS hostloop temp paths, direct `~/.cowork` writes, or a chat-driven ZIP workaround.
3. See its skills under the installed Cowork plugin.
4. Receive updates through Cowork's marketplace/update path.
5. Use AIWS provenance to understand that the published domain content came from a governed AIWS backend.

The following do **not** satisfy first-class Cowork plugin status by themselves:

- `aiws.marketplaces.drive_workflow` rows.
- AIWS materialization into `~/.aiws/hosts/.../shared-cache`.
- Cowork adapter package output or package-upload handoff.
- A skill being callable from an AIWS-controlled cache while absent from Cowork's plugin UI.

## Current Evidence And Constraints

### Working AIWS path

- `checkout-main` Drive releases resolve and materialize as `(marketplace_id=checkout-main, plugin_id=productivity)`.
- Draft, validate, stage, Drive review, publish, pull, guarded old-artifact cleanup preview, and workflow next-action surfaces are proven in Cowork.
- The Drive workflow now reports selected marketplace skill state without exposing legacy scopes by default.

### Cowork boundary

- Cowork owns native plugin install, update, and activation.
- AIWS must not write into Cowork installed plugin directories or claim activation from package handoff alone.
- Cowork's documented native distribution paths include plugin marketplaces, Git repository marketplaces, organization-managed manual marketplaces, and uploaded plugin files.
- Google Drive is an AIWS marketplace backend today, not a Cowork-native marketplace backend.
- Cowork's current native plugin MCP tools expose only fixed-backend installed/search/suggest flows; they do not expose custom marketplace register, browse, sync, repository, branch, path, or source parameters.

### Product constraints to preserve

- Do not use ZIP upload as the normal user path.
- Do not revive RPM or `cowork-upload` as the Drive domain plugin provenance.
- Keep `AIWS` naming for infrastructure. The demo domain plugin is `Productivity`.
- Do not mutate `checkout-main-real` or old `aiws-productivity` state.
- Scope removal remains a separate compatibility migration after explicit `marketplace_id` paths are stable.
- Existing marketplace registry repair and guarded Drive artifact deletion remain maintenance tools, not the first-class path itself.

## Design Decision

Use a **bridge-first Cowork distribution track**:

1. Drive remains the authoritative release backend for governed domain plugin content.
2. AIWS derives a Cowork-native marketplace artifact from a published Drive release.
3. Cowork consumes that derived artifact through a native path it already supports.
4. Provenance in the derived artifact and AIWS state pins the source Drive marketplace, plugin id, release version, package identity, and publication target.

The first bridge target is a **generated Cowork bridge Git marketplace subtree** in the existing `sashakang/ai-workspace` repository at `generated/cowork-drive-bridge/`. Git marketplace shape is the only non-upload Cowork-native path currently available to AIWS development in this repository, and the generated subtree keeps the Drive domain distribution separate from the authored infrastructure marketplace at the repository root. Organization-managed manual marketplaces remain a fallback/enterprise operator path. A direct Cowork-native Drive marketplace provider should be tracked as a later external integration request, not simulated locally.

AIWS may separately expose install-readiness state or a package-handoff action in Drive workflow payloads, but that is not the first-class proof. Existing Cowork host capability is `plugin-package`, `aiws.host.install` can prepare a guarded package handoff, and the current contract already says handoff is not activation. This can support diagnosis and bridge validation; it must not replace Cowork-native catalog/install/update acceptance.

The bridge does not change the one-backend-of-record contract for the Drive variant:

- Drive remains the only AIWS backend-of-record for `checkout-main/productivity`.
- The Git bridge is a released Cowork distribution projection, not a second AIWS authoring backend, review backend, or live GitHub mirror of the Drive marketplace.
- AIWS Drive resolution and catalog logic continue to resolve `checkout-main/productivity` from Drive. The generated Git marketplace is consumed by Cowork as a native distribution surface and must not be registered as a peer AIWS backend for the Drive variant.

## Architecture

### Source-of-truth layers

| Layer | Owner | Role |
|---|---|---|
| Drive marketplace `checkout-main` | AIWS | Authoring, Drive review, explicit publish, release provenance |
| Cowork bridge marketplace artifact | AIWS generated distribution output | Cowork-compatible plugin manifest and plugin folder derived from one Drive release |
| Cowork Directory / organization marketplace | Cowork | Catalog visibility, install, update, activation |

### Bridge artifact contract

For one Drive published release, AIWS should be able to produce a Cowork-native bundle with:

- a plugin folder named by the clean `plugin_id`, for example `productivity`
- `.claude-plugin/plugin.json` preserving Cowork plugin identity and release version
- Drive-published skill files for that release only
- marketplace metadata suitable for the selected Cowork-native marketplace target
- provenance metadata outside Cowork-owned identity fields that records:
  - `source_marketplace_id`
  - `source_backend_kind=google_drive`
  - `source_plugin_id`
  - `source_version`
  - Drive package/release identity and integrity evidence
  - bridge publication target and generated-at time

The bridge must be release-driven. It must not export an editable draft, a proposal under review, or an arbitrary materialized cache revision as a first-class Cowork release.

### Update semantics

- A new Drive release is the trigger for a new bridge artifact candidate.
- Cowork update remains Cowork-owned after the bridge artifact reaches a Cowork-native marketplace.
- AIWS should report the Drive source version and bridge publication state separately so "Drive released" does not falsely mean "Cowork updated".
- The normal user should not choose between Drive and Cowork versions manually once the native Cowork plugin is installed; the bridge must preserve one clean Cowork plugin identity.

## Implementation Plan

### Slice 1: Bridge One Published Drive Release

Build the smallest AIWS projection path that can prove native Cowork visibility for one released Drive plugin:

- require explicit `marketplace_id`, `plugin_id`, and published Drive version/release identity
- consume the existing published Drive package and release metadata as the bridge input
- project that package into the generated Git marketplace subtree at `sashakang/ai-workspace:generated/cowork-drive-bridge`
- write bridge provenance outside Cowork identity fields
- reuse existing plugin/skill/marketplace validation where applicable
- produce maintainer publication instructions for the generated bridge marketplace tree
- update the Drive backend architecture rule narrowly enough to preserve "no dual-write" and "no live mirroring" while allowing this release-driven Cowork distribution projection until Cowork has a Drive-native provider

The first projection path must not:

- rebuild the published Drive release package
- use an editable draft, proposal folder, adapter package, or materialized skill cache as source of truth
- create a second Drive materializer or parallel package validator when existing released-package and validator paths already cover the input
- call projection or package handoff installed, updated, Cowork-visible, or first-class before Cowork native proof passes

The Slice 1 export response must include maintainer publication instructions:

- sync the generated `bridge_repo_root` tree to `generated/cowork-drive-bridge/` in `sashakang/ai-workspace`
- commit and push the generated projection with maintainer or bot credentials
- treat that publication as Git marketplace artifact delivery only
- verify Cowork Directory visibility, install, skill use, and update separately

### Slice 2: Publish And Prove The Dedicated Bridge

Publish the generated bridge marketplace tree to `generated/cowork-drive-bridge/` in `sashakang/ai-workspace` through an explicit maintainer/bot flow, then run the clean Cowork native proof:

- write or update only the derived Cowork marketplace plugin folder/manifest for Cowork sync and runtime validation
- keeps Drive source provenance inspectable
- uses bot/maintainer GitHub publication rather than end-user ZIP upload
- validate the generated Cowork marketplace shape before publish
- add the dedicated bridge marketplace in Cowork Directory and install `Productivity`
- use `Meeting Follow-up`
- publish one later Drive release through the same bridge and prove Cowork update

#### Slice 2 Result, 2026-05-23

Bridge publication passed:

- generated bridge artifact was published to `sashakang/ai-workspace@generated/cowork-drive-bridge`
- bridge marketplace validates as `aiws-cowork-drive-bridge`
- plugin `productivity` version `0.2.4` and skill `meeting-followup` are present in the generated artifact
- provenance pins the Drive release `checkout-main/productivity@0.2.4`

Cowork native visibility failed:

- `mcp__plugins__list_plugins` can list installed plugins only
- `mcp__plugins__search_plugins` searches a fixed Cowork marketplace backend only
- `mcp__plugins__suggest_plugin_install` can suggest installs only from search results
- none of the native Cowork plugin tools accepts `repository`, `branch`, `path`, `source`, `ref`, or custom marketplace registration parameters
- `aiws-cowork-drive-bridge`, `productivity@0.2.4`, and `meeting-followup` are not visible through the native Cowork plugin tools
- registering `sashakang/ai-workspace@master:generated/cowork-drive-bridge` through AIWS succeeds as an AIWS registry operation but does not make the bridge visible through Cowork native plugin tools
- Cowork native search currently returns the official `productivity@knowledge-work-plugins`, which is a separate plugin with different skills and must not be confused with the bridge-exported `productivity@aiws-cowork-drive-bridge`

Therefore Slice 2 is complete for AIWS publication but blocked for first-class Cowork proof. The next work item is a Cowork-side native marketplace source/sync capability, specified in `docs/cowork-native-custom-marketplace-source-request-2026-05-23.md`.

### Slice 3: Document The Contract And Statuses

After the native bridge proof, correct and extend repository docs/contracts:

- define the first-class Cowork acceptance criteria above
- define the bridge artifact identity/provenance contract
- explain the difference between Cowork as a first-class AIWS host and Drive marketplaces as not-yet-native Cowork plugin entries
- add explicit status terms only where runtime or maintainer workflow surfaces need them:
  - `drive_released`
  - `bridge_ready`
  - `published_to_cowork_marketplace`
  - `cowork_update_pending`
  - `cowork_visible`
- revise GitHub-only shared-distribution assumptions in target architecture docs so Google Drive is represented as a peer AIWS marketplace backend
- qualify older Cowork marketplace docs that still say Cowork runtime evidence is static-only where canonical runtime proof now exists
- keep GitHub staging/release wording scoped to GitHub-backed marketplaces where Drive already uses backend-specific staging and publish flows

### Slice 4: Workflow Readiness And Lifecycle Polish

After the bridge proof is stable, decide which AIWS status and action surfaces reduce user confusion:

- optionally expose bridge-readiness status from a released Drive skill
- optionally expose `aiws.host.install` as a non-terminal package-boundary diagnostic for maintainers
- keep Drive release, bridge publication, and Cowork install/update status distinct

These surfaces must not make package handoff the normal Cowork user path or report installation before Cowork confirms native visibility.

### Slice 5: External Cowork Native Marketplace Source Track

Open and maintain the external integration request for Cowork to support custom marketplace sources, including the current generated Git bridge subtree and eventually AIWS Drive marketplaces directly as native plugin marketplace providers or through an equivalent provider API.

That request should include:

- current native plugin MCP tool limitation: installed/search/suggest only, no custom source registration
- generated Git bridge source: `sashakang/ai-workspace@generated/cowork-drive-bridge`
- current Drive marketplace layout
- release integrity/provenance model
- expected native Cowork catalog/install/update behavior
- why package handoff is not enough
- which bridge behavior would become obsolete if Cowork supports Drive directly

## Tests

### Automated

- Bridge export rejects non-Drive, non-released, proposal, draft, and identity-mismatched inputs.
- Bridge export preserves clean `productivity` plugin identity and published version.
- Exported Cowork plugin manifest and skill folder pass existing plugin/skill validation.
- Bridge provenance pins source Drive release identity and integrity evidence.
- Re-export of the same release is idempotent or reports an unchanged artifact.
- A later Drive release creates a distinct update candidate without overwriting provenance for the previous release.
- Existing Drive lifecycle tests remain green.
- Existing GitHub marketplace distribution for `core-aiws` remains unchanged.

### Runtime

- Cowork native Directory/catalog shows the bridge-published `Productivity` plugin.
- Cowork native install exposes `Meeting Follow-up` under the plugin UI.
- Cowork native update pulls the next bridge-published release.
- AIWS Drive workflow still reports Drive publication and bridge publication as distinct states.

## Success Criteria

The first delivery track succeeds when:

- a Drive-published `Productivity` release reaches Cowork through a native Cowork marketplace path
- a clean user can see, install, use, and later update it in Cowork without AIWS cache inspection or ZIP upload
- AIWS can prove which Drive release created the Cowork-visible plugin artifact
- the implementation does not imply that Cowork natively understands AIWS Drive marketplaces before that product support exists

## Risks And Open Decisions

### Risks

- A GitHub bridge can look like a second source of truth unless derived-state/provenance boundaries are explicit.
- The existing `ai-workspace` GitHub marketplace already contains infrastructure and historical domain plugins; adding generated Drive mirrors there may confuse ownership.
- Cowork marketplace sync/update timing and organization installation policies may delay runtime validation.
- Manual marketplace upload is native to Cowork but violates the desired normal user path if used as the primary bridge.

### Decisions to make before Slice 2

1. Choose the bridge projection artifact format and location under AIWS-owned state.
2. Decide whether bridge publication is a maintainer CLI/workflow first or a `core-aiws` tool surfaced to Cowork maintainers.
3. Decide which Cowork-visible provenance text is useful without exposing backend ids to normal users.

## Deferred Follow-Ups

- Remove/retire legacy scope storage after explicit `marketplace_id` resolution is stable.
- Improve maintenance UX around existing marketplace registry repair and guarded Drive artifact deletion only where runtime use still shows a gap.
- Make a true Cowork-native AIWS Drive marketplace provider once Cowork exposes the needed integration surface.
