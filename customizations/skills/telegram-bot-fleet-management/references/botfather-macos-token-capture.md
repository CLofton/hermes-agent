# BotFather token capture on macOS

Use only after the bot owner explicitly asks to connect or manage their BotFather-owned bots.

## Why clipboard copy beats OCR

Telegram renders bot buttons and token code blocks in a custom UI. Accessibility enumeration may return no useful buttons. Vision OCR is reliable for locating usernames and button geometry but can misread credential characters (`I/l/1`, `O/0`, `_`, `-`) or split a token across lines. Never trust an OCR-derived token even if it matches the expected length.

Validated sequence:

1. Open `tg://resolve?domain=BotFather` in Telegram Desktop.
2. Raise Telegram with `AXRaise`; ensure it is frontmost.
3. Clear any draft before sending `/token` (`Cmd+A`, type command, Return).
4. Screenshot locally and OCR username button boxes with macOS Vision.
5. Choose the bottom-most exact username match because older BotFather pickers remain visible in chat history.
6. Convert OCR screenshot coordinates for Retina displays before clicking (commonly divide x/y by 2; verify against the actual screenshot dimensions and window bounds).
7. After BotFather displays the token, use OCR only to find the first line of the token code block.
8. Right-click the code block. In Telegram's context menu, navigate to **Copy Code** (validated menu order: Quote, Reply, Copy Code) and copy the exact code block.
9. Parse the clipboard locally, call `getMe`, and require `result.username == selected_username` before writing anything.
10. Store the token in an owner-only file or profile `.env`; `chmod 600`.
11. Clear the clipboard immediately.
12. Remove every temporary screenshot and OCR text file that may contain the token.

## Verification

- BotFather enumeration count equals stored inventory count.
- Every token returns `ok=true` from `getMe`.
- Every returned username matches the selected button.
- Token fingerprints are unique unless intentionally sharing one bot (never run concurrent polling consumers in that case).
- Credential inventory mode is `0600`.
- No temporary secret artifacts remain.

## Common UI pitfalls

- Existing draft text can turn `/mybots` into `h/mybots`; always clear the composer first.
- Telegram may close or hide the window under Stage Manager. Re-open the deep link, wait for a window, then `AXRaise`.
- Starting another terminal/UI action can dismiss a context menu. Right-click, keyboard-select Copy Code, read clipboard, and clear it inside one local automation step.
- Old bot pickers and old token messages stay in the scrollback. Always select the most recent/bottom-most matching OCR result.
- Do not rotate/revoke a token merely to make capture easier; that can break a live gateway. Rotation is a separate approved migration with config update and read-back verification.
