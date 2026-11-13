# Proven per-item chain runner (zsh)

Copy to `<chain-dir>/run-item.sh`, chmod +x, launch one instance per item as a tracked background process. Profiles are unique per concurrent node; fixer/reviewer are different families. STOP GATE is in the briefs (commit only, never push/PR/migrate).

Pre-seed each worktree BEFORE launching: `cp -Rc <main-checkout>/node_modules <worktree>/node_modules` (APFS clone-on-write — seconds) and `cp .env.local <worktree>/` (worktrees start without gitignored files). Then `npm install` in run_node is a no-op.

```zsh
#!/bin/zsh
# usage: run-item.sh <item> <td_profile> <im_profile> <rv_profile> [judge_profile]
ITEM=$1; TD_P=$2; IM_P=$3; RV_P=$4; JUDGE_P=${5:-}
BASE=~/Downloads/<task>-chain          # input/, briefs/, runs/, reviews/, wt-$ITEM/
WT=$BASE/wt-$ITEM
LOG=$BASE/runs/$ITEM.log
mkdir -p $BASE/runs

echo "===== $ITEM START $(date) =====" >> $LOG

cd $WT || { echo "$ITEM: worktree missing" >> $LOG; exit 1; }
echo "WT HEAD at start: $(git rev-parse --short HEAD)" >> $LOG

run_node() {  # NODE PROFILE BRIEF WORKDIR [MAXTURNS]
  local NODE=$1 P=$2 BRIEF=$3 WD=$4 MAXT=${5:-80}
  echo "----- $NODE [$P] $(date) -----" >> $LOG
  cd $WD || { echo "$NODE: worktree missing" >> $LOG; return 1; }
  [ -d node_modules ] || npm install >> $LOG 2>&1
  hermes -p $P chat -q "$(cat $BRIEF)" --oneshot -Q --max-turns $MAXT \
    > $BASE/runs/$ITEM-$NODE.out 2>> $LOG
  echo "$NODE exit=$? $(date)" >> $LOG
}

# +G: premium contract gate BEFORE test design (judge profile; substitution named in prompt)
if [ -n "$JUDGE_P" ]; then
  cd $WT
  hermes -p $JUDGE_P chat -q "<contract-judge prompt: read task JSON + spec section; write reviews/$ITEM-contract.md; final line CONTRACT: APPROVED|CHANGES_REQUIRED>" \
    --oneshot -Q --max-turns 30 > $BASE/runs/$ITEM-PCON.out 2>> $LOG
  echo "PCON exit=$? $(date)" >> $LOG
  # CHANGES_REQUIRED is a HALT, not a failure to retry: revise the contract, re-run from TD
  cp $BASE/runs/$ITEM-PCON.out $BASE/reviews/$ITEM-contract.md 2>/dev/null
  if grep -q "CONTRACT: CHANGES_REQUIRED" $BASE/reviews/$ITEM-contract.md; then
    echo "===== $ITEM HALT (contract) $(date) =====" >> $LOG; exit 2
  fi
fi

run_node TD  $TD_P $BASE/briefs/$ITEM-td.md $WT 60
# commit-gate: abort if the node ran but produced nothing (session died mid-work)
git -C $WT log --oneline -1 | grep -q "test($ITEM)" || { echo "$ITEM ABORT: TD did not commit" >> $LOG; exit 1; }

run_node IM  $IM_P $BASE/briefs/$ITEM-im.md  $WT
git -C $WT log --oneline -1 | grep -q "feat($ITEM)" || { echo "$ITEM ABORT: IM did not commit" >> $LOG; exit 1; }

run_node RV  $RV_P $BASE/briefs/$ITEM-rv.md  $WT 90
grep -h "VERDICT:" $BASE/runs/$ITEM-RV.out | tail -1 >> $LOG

# +G: premium acceptance AFTER review PASS, bound to exact revision
if [ -n "$JUDGE_P" ] && grep -q "VERDICT: PASS" $BASE/runs/$ITEM-RV.out; then
  cd $WT
  hermes -p $JUDGE_P chat -q "<acceptance prompt: run vitest itself; diff confined to owned files; drizzle/ unchanged; accept/reject git rev-parse HEAD against YOUR red lines; final line ACCEPTANCE: APPROVED <sha>|REJECTED>" \
    --oneshot -Q --max-turns 40 > $BASE/runs/$ITEM-PACC.out 2>> $LOG
  echo "PACC exit=$? $(date)" >> $LOG
fi

echo "$ITEM HEAD: $(git -C $WT rev-parse --short HEAD)" >> $LOG
echo "===== $ITEM DONE $(date) =====" >> $LOG
```

Attempt-2 variant (failed items only): replace TD/IM with a single FIX node using the reviewer's numbered findings verbatim, then RV2 (re-review) verifying each finding resolved. Full corrected-scope items re-run the PCON→TD→IM→RV→PACC sequence from a worktree reset to the base SHA.

## Multi-item builds

Disjoint owned-file sets: launch several run-item.sh instances in parallel (separate terminal background processes). Dependent items: integrate first — `git checkout -B feat/<build> $BASE && git merge --no-ff feat/<item-a> && git merge --no-ff feat/<item-b>` in the main repo, then recreate the dependent's worktree from the chain head (`git worktree add -B feat/<item-c> <dir> feat/<build>` + re-seed node_modules/.env.local).

## Watch pattern

Foreground >600s is rejected; a pgrep wait-loop at timeout 601 auto-promotes to a tracked background process that notifies on completion. Note: `terminal(background=true)` itself can hit a consent gate when no user is present — if blocked, fall back to foreground sequential commands, and NEVER inline `&` backgrounding in a foreground command (it is rejected outright).

```bash
for i in $(seq 1 360); do
  [ "$(pgrep -f run-item.sh | wc -l | tr -d ' ')" = "0" ] && break
  sleep 100
done
# then dump per-item: grep -E 'exit=|VERDICT|CONTRACT:|ACCEPTANCE:|ABORT|HALT' runs/*.log + git log --oneline -3 per worktree
```
