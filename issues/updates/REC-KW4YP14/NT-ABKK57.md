---
id: NT-ABKK57
incident_id: REC-KW4YP14
timestamp: '2026-02-11T03:42:25.372309Z'
author: mattd
---

## Record Data

### Content

So, "system" update k/v data (updated_at, author, etc) isn't getting indexed in the DB on initial write
it problably does on reindex, though this is not confirmed.

We probably want to make this like the (future) incident special_fields logic - where config.toml has
a list of special fields with a type that flags it as "system" and then inserts certain
"system" available values.  Like the incident level special_fields - make an option so they are
uneditable by the user.

---

**created_at:** 2026-02-11T03:42:25.372309Z
**created_by:** mattd
**updated_at:** 2026-02-11T03:42:25.372309Z
**title:** FEATURE: Update K/V sanity fix
**type:** feature
**status:** new





