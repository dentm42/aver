---
created_at__string: '2026-02-07T20:10:28.580113Z'
created_by__string: mattd
updated_at__string: '2026-02-13T16:06:18.229858Z'
title: 'FEATURE: ''record report'' - run math functions on updates'
type: feature
status: new
---

Add the ability to do some basic math ops on integer key/values in update fields.

sum, avg, stddev, median, and others that might make sense.

aver record report REC-XXXXXX --field-group author --field created_at --field time_worked__sum


=======
REC-XXXXXX
=======
Update Title | Author | Created_at |Time Worked
-------------+--------+------------+--------------
Update 1 | fred | 2026-02-07T20:10:28.580113Z | 5
Update 3 | fred | 2026-02-09T20:10:28.580113Z | 2
Update 5 | fred | 2026-02-12T20:10:28.580113Z | 3
-----------------------
SUM      |      |                             | 10
--------
Update 2 | sue | 2026-02-08T20:10:28.580113Z | 1
Update 4 | sue | 2026-02-10T20:10:28.580113Z | 2
Update 6 | sue | 2026-02-13T20:10:28.580113Z | 3
Update 7 | sue | 2026-02-14T20:10:28.580113Z | 2
-----------------------
SUM      |     |                             | 8


