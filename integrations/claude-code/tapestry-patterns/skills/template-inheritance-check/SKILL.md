---
name: template-inheritance-check
description: After forking a WORKING instance (not a blank template) to start a new one, find the domain assumptions the source's data made that the new instance's data breaks. Use when a repo was copied from last term's app, the last client's site, or a sibling service, and the new instance's shape differs - different number of users, roles, tenants, instructors, regions, stages. Catches what a string grep cannot: conditionals that encode the old instance's shape.
---

# Template inheritance check

A blank template gives you structure. A **fork of a working instance** gives you structure
plus every assumption that instance's data happened to satisfy. Those assumptions live in
conditionals, defaults, and hardcoded labels - invisible to `grep`, because there is no
distinctive string to search for.

The tell: the code is correct, the strings are updated, and the UI is still wrong.

## When this applies

**Apply when the new instance's data has a different SHAPE than the source's**, e.g.:

| Source instance | New instance | Assumption that breaks |
|---|---|---|
| One team-taught course (two instructors) | Six single-instructor courses | per-instructor "track" chrome renders for everyone |
| One tenant | Many tenants | ids unscoped; caches collide |
| One region / currency / locale | Several | formatting and defaults hardcoded |
| Two pipeline stages | Five | stage enum, switch statements, column layouts |
| One admin user | Roles | permission checks assume "if logged in, allowed" |

**Skip when** the fork's data has the same shape as the source's - then
`seed-leftover-audit` alone is enough.

## Procedure

### 1. Characterize both shapes, in one line each

Write down what the source instance's data looked like and what the new one's looks like.
Be concrete and countable. "One course, two instructors, 15 weeks" vs "six courses, one
instructor each, schedules not yet known."

### 2. Derive the assumption list from the DIFFERENCE

For each dimension that changed, ask what the code could plausibly have assumed when that
dimension had the source's value. This is the step that cannot be automated - it is
generating hypotheses, not searching.

### 3. Test each assumption against the code

Grep for the *mechanism*, not the string. Useful patterns:

    # Conditionals keyed on a domain value - the classic inherited assumption
    grep -rnE 'side ===|role ===|type ===|stage ===' src/

    # Defaults and fallbacks that silently pick the source instance's value
    grep -rnE 'default:|fallback' src/

    # Counts, indexes, and slices tuned to the source's cardinality
    grep -rnE 'slice\(0,|length === 1|length === 2' src/

Read each hit and ask: **is this condition true for the new data, and does it still mean
what it meant before?** An inverted assumption is the dangerous case - a flag that was a
rare special case in the source becomes the universal case in the fork, so the branch that
almost never fired now always fires.

### 4. Fix by naming the real predicate

Do not special-case the new instance. Replace the inherited proxy with the condition it was
always standing in for, and derive it from data:

    // inherited: "both" meant "a joint session" when there were two instructors
    {day.side === "both" && <TrackHeading/>}

    // real predicate: this chrome belongs to team-teaching
    const teamTaught = Boolean(instructors.a?.name && instructors.b?.name)
    {teamTaught && day.side === "both" && <TrackHeading/>}

Now both shapes render correctly and the next fork inherits a *stated* assumption instead of
an implicit one.

### 5. Verify against the new shape

Run the app with the new instance's real data and look at it. These bugs are visual or
behavioral, not test failures - the source's tests still pass, because they encode the
source's assumptions too.

## Output

A list of inherited assumptions: where it lives (`file:line`), what it assumed, why the new
data breaks it, and the real predicate that replaced it.

## Why this exists

Forking a working instance is the fastest way to start and the easiest way to ship something
subtly wrong. The strings get updated because they are visible. The assumptions do not,
because nothing points at them.

Related: `seed-leftover-audit` (inherited strings - run that first, it is cheaper).
