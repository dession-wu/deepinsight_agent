# Local deployment snapshot

Dockerfiles and a sanitized Compose reference from the current Windows deployment. No credentials or runtime data are included. Paths are repository-relative; bind mounts under runtime/ are placeholders that must be configured for a fresh machine. Set all ${...} environment variables before using this reference. Existing docker-compose.yml remains the general project entry point. This snapshot is an archival reference, not a tested one-command migration.
