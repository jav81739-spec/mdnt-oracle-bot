# Verified command-menu repair plan

Required public menu/help behavior:
- Include only commands with registered working handlers.
- Preserve old and new working commands together.
- Keep `/announce`, `/broadcast`, and `/midnightmap` owner-only and hidden from normal users.
- DM and group menus must be populated from the same verified command registry.
- Do not remove or rewrite existing feature implementations.

This file is a safety checkpoint while the handler registry is being verified; it contains no runtime code.
