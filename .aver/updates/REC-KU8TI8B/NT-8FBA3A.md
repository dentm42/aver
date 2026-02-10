+++
id = "NT-8FBA3A"
incident_id = "REC-KU8TI8B"
timestamp = "2026-02-10T03:10:30.128771Z"
author = "mattd"
+++

## Record Data

### Content

--ksearch {key}!={value} 

Fails if no value at all is set for {key}.

Example:
If "status" is not set on a record, "--ksearch status!=closed" does NOT list the record.  It should

---

**created_at:** 2026-02-10T03:10:30.128771Z
**created_by:** mattd
**updated_at:** 2026-02-10T03:10:30.128771Z
**title:** Not equal search fails on null value
**type:** 
**status:** new
**severity:** 





