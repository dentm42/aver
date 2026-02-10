+++
created_at__string = "2026-02-10T03:10:30.128771Z"
created_by__string = "mattd"
updated_at__string = "2026-02-10T03:12:00.068480Z"
title = "Not equal search fails on null value"
type = "bug"
status = "new"
severity = ""
tag = []
+++

--ksearch {key}!={value} 

Fails if no value at all is set for {key}.

Example:
If "status" is not set on a record, "--ksearch status!=closed" does NOT list the record.  It should


