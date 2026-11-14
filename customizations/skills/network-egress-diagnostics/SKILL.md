---
name: network-egress-diagnostics
description: Use when this Mac's outbound API calls fail or get altered.
version: 1.0.0
---

# Network Egress Diagnostics (macOS)

Ordered triage for "my outbound API request is failing or being altered" from a Mac.
Goal: attribute the alteration to a layer — client code → local host → network path →
server — with evidence, so the fix is aimed at the right layer.

## Procedure (in order; each step gates the next)

1. **Prove client-independence.** Reproduce the failing request with three independent
   clients: `curl`, a Python `urllib` script, and a real in-page browser `fetch`
   (CDP Chrome — see `browser-daemon-recovery` for a quick no-login Chrome). Identical
   failure AND identical corruption pattern across all three ⇒ not a code bug; stop
   debugging the code.
2. **Split by request class.** Test GETs, plain-JSON POSTs, and the failing shape
   (multipart body, uploads, specific query params) against the same host.
   "JSON works, multipart is mangled" is a content-based rewrite signature, not
   flakiness.
3. **Read the server's echo.** A 4xx parse error that echoes the body shows exactly
   what arrived. Diff it against what was sent: which values were stripped or rewritten
   (header-like lines inside the body? a query param removed?) is the rewriter's
   fingerprint.
   For auth failures specifically, separate *credential rejected* from *credential
   removed* with a header-echo endpoint before chasing token rotation:
   `curl -s -H 'Authorization: Bearer <your-token>' https://httpbin.org/headers` (or
   `postman-echo.com/headers`). If the header survives to a neutral host, the path is
   not stripping it. Then note that many APIs return one generic message for any bad
   bearer — HubSpot answers "Authentication credentials not found" identically for a
   real token and for `garbage-token-xyz` — so response text alone proves nothing about
   revocation; you need a credential known to be live, or a different host, to decide.
4. **Rule out the local host.**
   - `env | grep -i proxy` AND `scutil --proxy` (a system PAC/WPAD config exists even
     when no env proxy is set; a dead PAC still tells you the network expects one)
   - `systemextensionsctl list` — content filters register here; a VPN NE (e.g.
     Tailscale) tunnels but does not rewrite TLS bodies, so it is usually not the
     rewriter
   - `profiles list` (MDM), non-system process list, listening ports
   - Client-flag battery: HTTP/1.1 vs 2 (`curl --http1.1`), IPv6 (`curl -6`),
     `--noproxy '*'`, browser User-Agent + Sec-Fetch headers, URL-encoding the suspect
     param. If every flag fails identically, the alteration is beyond client-flag
     control — it is on the path.
5. **Characterize the physical path.** `route -n get default` (interface + gateway),
   `networksetup -getairportnetwork en0` ("not associated" + a 192.168.1.x gateway =
   wired residential), the IPv6 prefix (carrier attribution), Tailscale state
   (`tailscale status`; eligible exit nodes appear in the `tailscale set --exit-node=`
   error listing — nodes that don't advertise exit-node are not options).
6. **Attribute and route around.**
   - ISP/office TLS-inspection appliance ⇒ route around: Tailscale exit node on a node
     with a clean uplink (must advertise it + admin approval), move the machine to
     another network, or run the operation from another machine.
   - Only specific request shapes are altered ⇒ redesign to avoid the shape where the
     API allows (plain-JSON equivalents of upload endpoints), or reference/share the
     remote objects instead of re-transferring them.

## Rules

- Never declare a root cause without the step-1 client-independence proof; "works in
  my script" is not evidence.
- Only present as a workflow what was executed end-to-end. If a route-around was never
  run (no eligible exit node, user absent, consent not given), report "blocked; resume
  path is X" — never dress an unexecuted path up as the fix.
- Capture baseline state (current exit node, default route, active network) before any
  network change, so the revert is exact; network-state commands (`tailscale
  set/down`) need explicit user consent.
- If consent prompts time out (user away), stop queuing consent-gated commands: finish
  everything ungated, persist a resume note in the project folder, and hand back a
  one-line resume instruction.
