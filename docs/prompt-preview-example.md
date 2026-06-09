# Prompt Preview Example

This is a sanitized example of what `novel-engine` injects into a chapter prompt.

Do not publish full prompt previews from real projects. They often contain:

- unpublished plot twists
- full character state
- relationship history
- foreshadowing tables
- future chapter plans
- private style rules

## Structure

```text
SYSTEM
  Writing rules
  Output constraints
  Current character state
  Active relationships
  Open foreshadowings

USER
  World setting
  Main cast
  Current chapter outline
  Prior chapter summaries
  Nearby chapter facts
  Cross-reference summaries
  Activated lorebook entries
```

## Sanitized Fragment

```text
SYSTEM

You are a careful long-form novel writing engine.

Rules:
1. Follow the given world, cast, and chapter outline.
2. Do not rewrite previous events.
3. Output prose only.
4. Do not include word count notes, chapter labels, or editor comments.
5. Refer to past events by concrete scenes, not chapter numbers.

Current Character State:

### Protagonist
- identity: high school student
- ability: can read structured character cards
- current_state: has learned a partial truth about the world

### Character A
- role: main ally
- current_state: knows the world is being written
- relationship: secret alliance with the protagonist

Open Foreshadowings:
- [F001|high] mysterious guide in the convenience store
- [F002|medium] old manuscript with familiar handwriting

USER

World:
An ordinary city where a few people notice inconsistencies in reality.

Current Chapter:
The protagonist meets the mysterious guide again. The guide no longer hides
behind a mask and offers one missing piece of the truth.

Nearby Facts:
- Previous chapter: the group found an old manuscript.
- Next chapter: the guide's identity will be explored.

Write the chapter as continuous prose.
```

## Recommended Public Demo

For README or social posts, show:

- token / character counts
- block names and ordering
- a short sanitized fragment
- screenshots with spoilers blurred

Avoid showing:

- full real prompts
- future chapter outlines
- complete profiles
- hidden endings
- platform-bound manuscript text
