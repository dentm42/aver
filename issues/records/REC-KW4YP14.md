---
created_by__string: mattd
title: 'FEATURE: Update K/V sanity fix'
type: feature
status: closed
created_at: '2026-02-11T03:42:25.372309Z'
created_by_username: mattd
updated_at: '2026-02-20 10:28:37'
---

So, "system" update k/v data (updated_at, author, etc) isn't getting indexed in the DB on initial write
it problably does on reindex, though this is not confirmed.

We probably want to make this like the (future) incident special_fields logic - where config.toml has
a list of special fields with a type that flags it as "system" and then inserts certain
"system" available values.  Like the incident level special_fields - make an option so they are
uneditable by the user.

Need to re-evaluate now that we have system special fields all in config.toml and code changes
may have changed this status.


