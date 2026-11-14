# Permission-coverage release controls

## 1. Establish scope and evidence

Inventory covered and omitted file classes before interpreting a zero finding count; a scanner and enforcer sharing an allow-list share its blind spots. Match environment-file names independently of suffixes. Separate credential-shaped material from provider-verified credentials; entropy cannot establish validity.

Broaden discovery independently from enforcement. Keep tracked/public/error candidates visible with explicit classifications rather than declaring a zero-enforcement result clean. Exclude newly added roots, other profiles, and unrelated file classes unless authorized. Measure the read-only target census and preserve a protected rollback manifest containing paths, modes, and inode/device identity—not file contents.

## 2. Build and test the isolated candidate

Freeze live source/test hashes and use the scheduled service's actual interpreter. With disposable fixtures, verify:

- file and parent-directory symlinks cannot redirect mutation;
- directories, nonregular files, nonowner files, and hardlinks are rejected;
- no-follow directory descriptors and file descriptors bind enforcement to the validated inode;
- failed Git discovery produces a reported skip, not an untracked classification;
- public PEM exemption checks complete bounded content, rejects private-key markers anywhere and unexplained trailing material, and never exempts a certificate prefix alone;
- permission changes remove group/world bits without adding owner rights or destroying existing owner execute/read constraints;
- skipped candidates remain observable to the detector.

Git tracks executable-bit state, not every POSIX permission bit; do not claim every chmod creates a repository diff. Skipping tracked secrets avoids unauthorized mutation but does not remediate their history exposure.

Recover missing test sources only from a copy matching a previously recorded checksum. Never reconstruct tests and present them as original evidence; a reviewer's attribution of a deletion does not prove who deleted it. Convert only fixed-defect characterization assertions to corrected behavior and retain unrelated expected-failure pins. Report passes and expected failures separately.

## 3. Review and publish without losing concurrent fixes

Require independent candidate review. Immediately before installation, acquire the shared writer lock and compare current live hashes with the reviewed baseline. If live code advanced, apply only the approved hunks onto it, verify unrelated functions remain unchanged, and rerun combined tests—including concurrent-publication tests. Never replace a newer live repair with a stale candidate.

Keep protected source backups and atomic per-file publication. Record and preserve required destination modes explicitly; generic file writers and temporary files may discard executable bits even when source bytes are correct. Set the intended mode before `os.replace`, and verify both installed hash and mode. Publish the safe guard before expanding its discovery input so newly spawned jobs cannot consume the broader list using the old guard.

If the shared writer lock is busy, inspect its holder with `lsof -nP <lock-path>` and inspect that PID with `ps -p <pid> -o pid=,ppid=,etime=,stat=,comm=`; inspect descendants without exposing private argv. A sleeping process or elapsed timeout alone does not establish staleness. Leave an active owner untouched. After any later successful acquisition, repeat the live-baseline comparison before writing; do not assume the baseline survived the wait.

## 4. Exercise and report the real result

Run the installed code against the inventoried inode/device-bound target set; changed targets must be reclassified or skipped. Independently stat every affected path, record exceptions privately, and verify the recurring service points to the installed code and uses the tested interpreter. Do not equate configured scheduling with an observed successful unattended run.

Separate installed coverage, verified containment, recurring prevention, and incident closure. A deployed guard does not fix permissive creation modes, revoke credentials exposed in history, or justify automatic reconciliation after the collector has already clamped the evidence.
