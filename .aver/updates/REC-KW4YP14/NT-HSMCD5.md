---
id: NT-HSMCD5
incident_id: REC-KW4YP14
timestamp: '2026-02-15T04:36:27.690700Z'
author: mattd
---

REPLY TO NT-ABKK57:

> ## Record Data
> 
> ### Content
> 
> So, "system" update k/v data (updated_at, author, etc) isn't getting indexed in the DB on initial write
> it problably does on reindex, though this is not confirmed.
> 

This should be fixed.

> We probably want to make this like the (future) incident special_fields logic - where config.toml has
> a list of special fields with a type that flags it as "system" and then inserts certain
> "system" available values.  Like the incident level special_fields - make an option so they are
> uneditable by the user.

This update should also be done.

> 
> ---
