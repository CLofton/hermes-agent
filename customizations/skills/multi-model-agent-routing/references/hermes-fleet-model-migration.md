# Hermes fleet model migration

Use this recipe when the user wants every Hermes profile moved to one provider/model. This is a fleet configuration change, not a single-session `/model` switch.

## Scope decision

Interpret “all agents” as every profile’s primary model plus delegated subagents unless the user explicitly includes every auxiliary model call. Decide and state whether the migration also covers:

- auxiliary slots such as vision, compression, title generation, and curation;
- MoA reference models and aggregator;
- fallback chains and automatic routers;
- cron jobs with explicit per-job model overrides;
- speech, image generation, and search-specific models, which are capabilities rather than general agents.

Do not silently overwrite capability-specific models when the target model lacks the required modality or API behavior. If the user requests one model for every call, verify modality, tool, structured-output, and context support first and surface the cost trade-off.

## Procedure

### 1. Load current Hermes guidance and inventory the fleet

Load the protected `hermes-agent` skill and current provider documentation before editing. Enumerate both the profile registry and every directory under `~/.hermes/profiles/`; a profile directory with no `config.yaml` or `.env` is still part of the requested fleet and must not disappear from the count.

Record for each profile:

- config path and whether `model` is a scalar overlay or a mapping;
- current primary model/provider;
- delegation, auxiliary, MoA, fallback, and routing overrides;
- whether its gateway is active;
- whether its credential file exists and is owner-only.

Use programmatic counts. The configured total must equal the discovered profile total plus the default profile.

### 2. Validate the exact provider model ID

Query the provider’s live model catalog with the intended credential and match the exact canonical ID. For OpenRouter:

```bash
python3 - <<'PY'
import json, os, urllib.request
req = urllib.request.Request(
    'https://openrouter.ai/api/v1/models',
    headers={'Authorization': 'Bearer ' + os.environ['OPENROUTER_API_KEY']},
)
with urllib.request.urlopen(req, timeout=30) as response:
    models = json.load(response)['data']
for model in models:
    if 'astra' in (model.get('id', '') + ' ' + model.get('name', '')).lower():
        print(model['id'], model.get('context_length'), model.get('supported_parameters'))
PY
```

Never infer a slug from a display name. Validate tool calling and required modalities from live metadata rather than marketing copy.

### 3. Back up before the write

Create one owner-only backup directory containing the files in the mutation scope, grouped by profile. Include scheduled-job configuration when changing a default inherited by cron, and copy credential files only if credentials will change. Include a short rollback note; never print secret values.

Before changing the default, inspect enabled agent jobs for explicit pins and persisted `model_snapshot`/`provider_snapshot`. An unpinned snapshot can conflict with the new default and stop the next run. Preserve unrelated job routes by explicitly pinning their existing model/provider pair with `hermes cron edit <job_id> --model <model> --provider <provider>`, then read back every affected job. Treat `no_agent` scripts separately: their model field does not indicate inference spend. Do not silently move restricted-data jobs to another provider while optimizing engineering cost.

### 4. Update every profile independently

Profiles do not inherit live changes from the default profile. Write the provider key to each profile’s protected `.env`, preserving unrelated lines, replacing `OPENROUTER_API_KEY` exactly once, and setting mode `0600`.

Handle both supported config shapes:

- mapping: set `model.default`, `model.provider`, provider endpoint when required, and the verified context length;
- scalar overlay: set `model` to the canonical provider/model slug, or normalize through Hermes’ config command if the installed version supports that migration.

Set `delegation.model` and `delegation.provider` explicitly in every profile so child agents cannot retain the former fleet model. Apply the scope decision from step 1 to auxiliary, MoA, fallback, router, and cron overrides.

Do not treat a successful `hermes config set` as runtime proof. If the CLI warns that a key is unrecognized, search the installed runtime for a consumer before claiming the feature is enabled or disabled.

For a profile with no config, use profile-scoped config commands to create a valid mapping rather than omitting it:

```bash
hermes --profile <name> config set model.default <provider/model>
hermes --profile <name> config set model.provider openrouter
hermes --profile <name> config set delegation.model <provider/model>
hermes --profile <name> config set delegation.provider openrouter
```

### 5. Verify structure before spending on smoke tests

Programmatically assert for every discovered profile:

- the resolved primary model equals the requested canonical ID;
- delegation resolves to the same model/provider;
- the provider key appears exactly once;
- `.env` mode is `0600`;
- every explicitly included auxiliary, MoA, fallback, router, or cron slot was updated;
- no profile is missing from the result.

Run `hermes config check` for the default and every named profile. Re-run `hermes profile list` and reconcile its count and displayed models against the programmatic inventory.

### 6. Prove the real default route

Run two bounded exact-marker smokes:

1. a plain response through the default profile with no `--provider` or `--model` override;
2. a named profile, also unforced, that must execute a harmless terminal command and return its exact marker.

An explicit-provider smoke proves model access but not saved default routing. A text-only pass proves generation but not tool reliability. Require both.

### 7. Restart and read back active gateways

Inventory active work before restarting any gateway. Apply configuration for new sessions without interrupting active conversations; restart only when authorized and safe, covering each affected active gateway rather than only the default. Verify fresh supervised PIDs for gateways actually restarted. Report retained windows separately: saved defaults do not migrate their loaded model. Use the supported `/model <canonical-model-id>` command in an idle window or start a fresh session; never claim all windows switched from config readback alone.

### 8. Report concisely

Report:

- canonical provider/model;
- verified profile count;
- primary/delegation scope and any excluded capability-specific slots;
- exact-marker text and tool-call results;
- restarted gateway names and status;
- rollback directory;
- material cost, privacy, or long-context pricing risk.

Never include the API key in the final response.