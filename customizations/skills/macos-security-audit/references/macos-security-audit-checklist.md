# macOS security audit checklist

## Evidence collection

- Date/time, `sw_vers`, kernel/build
- SIP, Gatekeeper, FileVault
- Firewall + stealth mode
- Pending OS/security updates
- XProtect/MRT versions and last updates
- Profiles/MDM
- Local users/admins; recent/current logins
- SSH authorized keys and remote-service listeners
- Full process tree and command lines
- Listening ports: wildcard vs loopback
- Established connections mapped to process and owner/domain
- LaunchAgents/LaunchDaemons, cron, shell startup, login items
- Privileged helper signatures
- Recent installers/apps: `spctl` + `codesign`
- Browser extension permissions and recognition
- XProtectRemediator/MRT confirmed outcomes
- VPN/Tailscale peer inventory

## Interpretation cautions

- Many local pseudo-terminals from agent sessions are not remote logins.
- `ControlCenter` on ports 5000/7000 is commonly Apple AirPlay/AirPlay Receiver; identify it before disabling.
- Localhost listeners are not remotely reachable by default; wildcard listeners need firewall or rebinding review.
- Developer binaries from Homebrew, virtual environments, npm, or uv may lack Apple Team IDs but can still be expected; validate path, parent process, package provenance, and network behavior together.
- Browser remote-debugging on `127.0.0.1` is not externally exposed, but raises local-process risk because a malicious local process could control browser sessions.
- No XProtect remediation log plus clean persistence/process/account checks supports “no evidence found,” not a forensic guarantee.

## Checklist execution commands

Use these as readback primitives; tolerate absent preference keys because macOS does not materialize every default until it changes:

```bash
sw_vers
uname -m
fdesetup status
/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate
/usr/libexec/ApplicationFirewall/socketfilterfw --getstealthmode
spctl --status
csrutil status
softwareupdate --schedule
softwareupdate -l
profiles status -type enrollment
sysadminctl -autologin status
tmutil destinationinfo
pmset -g custom
lsof -nP -iTCP -sTCP:LISTEN
```

Known user-scoped preference changes, each followed by the corresponding `defaults read`:

```bash
defaults write com.apple.sharingd DiscoverableMode -string 'Contacts Only'
defaults write com.apple.finder AppleShowAllExtensions -bool true
defaults -currentHost write com.apple.screensaver idleTime -int 300
defaults write com.apple.screensaver askForPassword -int 1
defaults write com.apple.screensaver askForPasswordDelay -int 0
killall Finder 2>/dev/null || true
killall sharingd 2>/dev/null || true
```

Privileged settings require native user authorization and must be verified afterward:

```bash
/usr/libexec/ApplicationFirewall/socketfilterfw --setstealthmode on
pmset -b displaysleep 5
pmset -c displaysleep 5
```

For Objective-See tools, inspect provenance before installation (`brew info --cask lulu blockblock oversight`), verify the installed app signature with `codesign -dv`, and verify protection separately with `systemextensionsctl list`, expected helper paths, and login/background-item state. A running GUI process alone is not evidence that filtering or alerts are active.

For Chrome extension review, resolve the active profile from `profile.last_used` in `~/Library/Application Support/Google/Chrome/Local State`, but inventory every profile when the task is account-wide. Resolve localized manifest names before labeling an extension unknown, then review sensitive permissions and recognition; never remove solely because the manifest name is a localization token.

## Post-change verification

After firewall/server hardening:
- read back firewall global state and stealth mode;
- re-list listeners;
- confirm intended wildcard development ports disappeared;
- confirm required localhost services remain;
- do not count an administrator prompt as success—verify state.

After a broad checklist:
- distinguish application copied, privileged helper installed, system extension enabled, privacy grants approved, start-at-login enabled, and behavior verified;
- separate current-train security updates from major-version upgrades and identify whether a restart is required;
- list recovery decisions, physical backup media, and interactive browser/privacy review as separate unresolved categories rather than a generic manual-work bucket.