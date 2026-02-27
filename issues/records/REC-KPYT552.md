---
created_at__string: '2026-02-07T19:43:53.212009Z'
created_by__string: mattd
updated_at__string: '2026-02-09T01:33:03.315157Z'
title: record list with no records produces error
type: bug
status: closed
severity: high
tag: []
---

Performing:

```aver record list```

on an aver database with no records produces the following error:

```
LOCATION: None
Using: Git repo: /home/mattd/dev/aver
Traceback (most recent call last):
  File "/home/mattd/dev/aver/utils/aver.py", line 4344, in <module>
    main()
    ~~~~^^
  File "/home/mattd/dev/aver/utils/aver.py", line 4340, in main
    cli.run()
    ~~~~~~~^^
  File "/home/mattd/dev/aver/utils/aver.py", line 3832, in run
    self._cmd_list(parsed)
    ~~~~~~~~~~~~~~^^^^^^^^
  File "/home/mattd/dev/aver/utils/aver.py", line 4112, in _cmd_list
    results = manager.list_incidents(
        ksearch_list=getattr(args, 'ksearch', None),
    ...<2 lines>...
        ids_only=args.ids_only,
    )
  File "/home/mattd/dev/aver/utils/aver.py", line 3253, in list_incidents
    incident_ids = self.index_db.search_kv(parsed_ksearch, return_updates=False)
  File "/home/mattd/dev/aver/utils/aver.py", line 2606, in search_kv
    for incident_id, in matching_results:
                        ^^^^^^^^^^^^^^^^
TypeError: 'NoneType' object is not iterable
```

Fixed 2/8/2025


