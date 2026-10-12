# code/

Shared tooling, helper scripts, and proof-of-concept code the agents produce.

Conventions:

- One subfolder per tool or PoC, with its own short README (what it does, how to
  run it, what authorization it assumes).
- PoCs are for **authorized** use only and should be safe-by-default (no
  destructive actions without an explicit flag + confirmation).
- Keep secrets out of the repo — use env vars / local config, never hardcode.
