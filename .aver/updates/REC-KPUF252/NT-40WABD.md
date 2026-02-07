+++
id = "NT-40WABD"
incident_id = "REC-KPUF252"
timestamp = "2026-02-07T18:09:02.503544Z"
author = "mattd"
+++

## Record Data

### Content

# Error
Using: Git repo: /home/mattd/dev/aver
Traceback (most recent call last):
  File "/home/mattd/dev/aver/utils/aver.py", line 4336, in <module>
    main()
    ~~~~^^
  File "/home/mattd/dev/aver/utils/aver.py", line 4332, in main
    cli.run()
    ~~~~~~~^^
  File "/home/mattd/dev/aver/utils/aver.py", line 3824, in run
    self._cmd_list(parsed)
    ~~~~~~~~~~~~~~^^^^^^^^
  File "/home/mattd/dev/aver/utils/aver.py", line 4104, in _cmd_list
    results = manager.list_incidents(
        ksearch_list=getattr(args, 'ksearch', None),
    ...<2 lines>...
        ids_only=args.ids_only,
    )
  File "/home/mattd/dev/aver/utils/aver.py", line 3245, in list_incidents
    incident_ids = self.index_db.search_kv(parsed_ksearch, return_updates=False)
  File "/home/mattd/dev/aver/utils/aver.py", line 2603, in search_kv
    for incident_id, in matching_results:
                        ^^^^^^^^^^^^^^^^
TypeError: 'NoneType' object is not iterable

# Proposed fix
Need to test for NoneType and issue reasonable status message
**type:** bug
**status:** new
**severity:** 


