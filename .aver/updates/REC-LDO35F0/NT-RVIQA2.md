---
incident_id__string: REC-LDO35F0
---

## Record Data

### Content

# FEATURE: Use rdiff for record updates

# Justification

Currently when a record is updated, a full copy of the previous text is included in a note.
For small (usually one line!) metadata changes, this becomes an opportunity for disk bloat.

# PROPSAL
The proposal is to use rdiff for metadata changes, and full text snapshots for:
  * Changes to the body
  * Whenever the record is detected to have been manually changed outside of aver (hash no matching the header/body after the last aver mediated change)

### The "Heuristic of Importance"

* **Metadata Changes (Status, Priority, Tags):** These are high-frequency but low-entropy. Storing a full 5KB Markdown file because a status went from `open` to `verified` is where the "bloat" happens. An `rdiff` of the YAML frontmatter is perfect here.
* **Body Changes (Descriptions, Observations):** These are the "Authority." If a user rewrites the description, they are changing the core of the record. Storing the full text ensures that the "Body of the Truth" is never locked behind a complex diff chain.

### Why this is the "Golden Path" for Aver:

1. **Readability where it counts:** If a researcher is looking at an anomaly log from three years ago, they can read the **Body** instantly. They don't have to "reconstruct" the human narrative; they only have to look at the diffs if they care about the administrative metadata history.
2. **Chain Stability:** By forcing a full-text "Snapshot" every time the body changes, you naturally break the diff chain. You prevent "Chain Fatigue" where a record has 200 tiny diffs. The moment the user adds a paragraph, the chain resets. It’s a built-in "garbage collection" for complexity.
3. **The "Experienced Person" Test:** In the history folder, a human sees:
  * `v1_snapshot.md` (Original)
  * `v2_meta.diff` (Updated status)
  * `v3_meta.diff` (Added a tag)
  * `v4_snapshot.md` (User added two paragraphs of findings)
  * `v5_meta.diff` (Closed the record)


This is easy to parse visually. The "Snapshots" act as anchors for the narrative evolution.

### Implementation Logic: The "Divergence Check"

Script logic would look something like this:

1. Compare `current_body` to `previous_body`.
2. **If `body_changed`:** Write a full-text Snapshot. (Reset the chain).
3. **If `only_metadata_changed`:** Write an `rdiff` of the metadata block.
4. **The Fallback:** If the user manually edited the file in a way that breaks the `rdiff` logic, write a full-text Snapshot.

### Potential DESIGN INVARIANT update

> **7. Intelligence in Storage**
> `aver` distinguishes between administrative metadata and narrative substance. 
> To prevent bloat, metadata updates are stored as transparent deltas, 
> while changes to the record's body trigger a full-text snapshot. 
> This ensures the human narrative is always immediately readable, while the housekeeping remains efficient.


---

**title:** Rdiff for record update history
**type:** feature
**status:** new
**created_at:** 2026-02-20 10:16:02
**created_by_username:** mattd
**updated_at:** 2026-02-20 10:16:02



