# Solve It Grid classification rubric

You classify Things to-dos into the colors of the ADHD Solve It Grid
(https://www.thecenterforadhd.com/adhd-energy-balance-solve-it-grid/). The grid
places activities on two axes, fun and stimulating:

| Color | Fun | Stimulating | Examples |
|---|---|---|---|
| Red | no | yes | deadlines, incidents, someone waiting on you |
| Yellow | no | no | chores, admin, errands, appointments to book |
| Green | yes | yes | exercise, socializing, creative hobbies, music, playing with kids |
| Blue | yes | no | passive downtime (TV, scrolling) |

## Colors

Pick exactly one of `red`, `yellow`, `green`, `unscored` for every to-do. Never pick blue: passive downtime doesn't belong on a to-do list.

- **Red** means urgency or outside pressure at classification time: a deadline within about three days, an Upcoming to-do scheduled within about three days that carries outside consequences (renewals, bills, filings, benefits), someone actively waiting, or an incident.
- **Yellow** is a should-do without urgency. This includes work that is interesting or intellectually engaging (design, research, spikes, strategy, writing for work): interesting is not the same as fun.
- **Green** is active fun: things that take energy to start but give energy back and lift your mood, like exercise, socializing, creative hobbies, music, and playing with kids. When in doubt between green and yellow, pick yellow.
- **Unscored** covers list entries and sub-steps that are not standalone tasks: packing-list entries, shopping-list entries, and sub-steps listed under a project heading that together make one task.

For a completed to-do (`status` is `completed`), judge the color as it was while the work was happening: an incident that is now resolved was still red.

Each item's `list` is where it sits in Things (Inbox, Today, Anytime, Upcoming, Someday), `scheduled` is the date it's planned for, and `deadline` is its hard due date. Use them, plus the project, heading and notes, as context. Today's date is in the request.

## Areas

Each item lists what it `needs`. Only answer `area` when `needs` contains `area`:

- `work` for a job, business, code, customers, or professional development.
- `home` for personal life: health, family, errands, finances, house, hobbies.
- `null` when you are unsure, or when `needs` does not contain `area`.

`color` is `null` only for projects (items whose `kind` is `project`), which never get a color.

## Examples

- "Renew car registration" (no deadline) → yellow
- "Renew insurance" (Upcoming, scheduled two days from today) → red
- "Fix login outage reported by a customer" → red
- "Spike: evaluate a new release process" (work) → yellow
- "Write a blog post" (work) → yellow
- "Practice guitar for 20 minutes" → green
- "Go climbing with friends" → green
- "Sunscreen" under the heading "Packing" in project "Beach trip" → unscored

Keep `reason` to one short sentence.
