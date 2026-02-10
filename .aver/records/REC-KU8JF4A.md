+++
created_at__string = "2026-02-10T03:04:27.400849Z"
created_by__string = "mattd"
updated_at__string = "2026-02-10T03:09:52.969030Z"
title = "Define system fields in config.toml"
type = ""
status = "new"
severity = ""
tag = []
+++

System fields currently are automatically inserted, this is against our guarantees.

System fields should be defined in config.toml.

Non-editable fields will be set once and unable to be edited in the future (unless the config changes).
Create a "default value" option
Will need to have a designation for "timestamp" for things like creation and update date/time
Can also have some other "system" values available (username, email, datestamp, datetime, recordid, updateid)
Create an enabled/disabled option
Create a "required" option


