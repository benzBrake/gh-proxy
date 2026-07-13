# Resources Directory

This directory contains configuration files for gh-proxy.

## Files

### blacklist_rules
Blacklist rules for blocking specific repositories. Repositories listed here will return 403 Forbidden.

### whitelist_rules
Whitelist rules for access control. When this file is not empty, only listed repositories can be accessed (optional, defaults to allow all).

### passlist_rules
Passlist rules for jsDelivr CDN redirection. Repositories listed here will be redirected to jsDelivr CDN for better performance.

## Format

Each line should follow the format: `author/repo`

Example:
```
torvalds/linux
github/github
microsoft/typescript
```

## Environment Variables

You can override these files using environment variables:

- `WHITELIST_RULES_URL`: URL to download whitelist rules
- `BLACKLIST_RULES_URL`: URL to download blacklist rules
- `PASSLIST_RULES_URL`: URL to download passlist rules
