+++
created_at__string = "2026-02-09T02:09:36.838101Z"
created_by__string = "mattd"
updated_at__string = "2026-02-09T02:09:36.838101Z"
title = "Use TOML file when using editor"
type = "feature"
status = "new"
severity = ""
tag = []
+++

Instead of just a text block - create the TOML header prior to dumping into the text editor allowing the user to update field.

SYSTEM fields should be excluded.
REQUIRED fields should be marked with __required

Also - remove the #comments - since this is MD, the # is a heading delimiter not a comment.


