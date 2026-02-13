---
created_at__string: '2026-02-10T03:10:30.128771Z'
created_by__string: mattd
updated_at__string: '2026-02-12T00:54:57.747808Z'
title: Not equal search fails on null value
type: bug
status: closed
---

--ksearch {key}!={value} 

Fails if no value at all is set for {key}.

Example:
If "status" is not set on a record, "--ksearch status!=closed" does NOT list the record.  It should


