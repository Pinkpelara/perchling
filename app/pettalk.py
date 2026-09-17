"""What the pets say to each other at the table, built from what the household knows.

facts(): everything worth talking about, pulled from every pet's file (notebooks, birthday, arrival times,
reminders, touches, picks). conversation(): a list of (seat, line) exchanges, each a few lines that follow on
from one another. The pet that calls the gossip builds it once and puts it in the plan, so everyone at the
table follows the same script. No filler: with nothing written down, they talk about the routine they've seen.
"""
import re, json, statistics, time
from datetime import datetime, date, timedelta
from pathlib import Path
from petnotes import PEOPLE, FEELINGS, EVENTS, age_days, an, person_named, matched

try:                                                                              # trick names, for "asked me for a backflip"
    TRICK_NAMES = {t["id"]: t["name"] for t in json.loads((Path(__file__).resolve().parent / "species" / "antenna.json").read_text(encoding="utf-8"))["catalog"]["tricks"]}
except (OSError, ValueError, KeyError):
    TRICK_NAMES = {}

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
PICK_NAMES = {"bounce": "Bounce", "peekaboo": "Peekaboo", "zoomies": "Zoomies", "nap": "Nap anywhere", "sit": "Sit", "lie": "Lie down", "spin": "Spin", "wave": "Wave",
              "calm": "Calm", "sleepy": "Sleepy", "clingy": "Clingy", "showoff": "Show-off", "study": "Study with me", "work": "Work with me", "game": "Game with me", "eat": "Eat with me"}


def _days_until_weekday(name, from_day):
    try:
        target = WEEKDAYS.index(name.lower())
    except ValueError:
        return None
    return (target - from_day.weekday()) % 7


def facts(states, owner):
    """states: {pid: state dict} for the whole household. owner: petnotes.Owner."""
    now = datetime.now()
    f = {"owner": owner, "people": [], "likes": [], "dislikes": [], "favorites": [], "feelings": [], "events": [], "plans": [],
         "about_pet": {}, "picks": {}, "adopted_days": {}, "hours_since_touch": {}, "birthday_in": None, "birthday": None,
         "usual": None, "today_login": None, "reminders": [], "names": {}, "raw": [], "places": [], "jobs": [], "wants": [], "things": [], "today": {}}
    all_logins, touches = [], {}
    for pid, st in states.items():
        f["names"][pid] = st.get("name", pid)
        f["picks"][pid] = [PICK_NAMES.get(p, p) for p in st.get("picks", [])]
        try:
            f["adopted_days"][pid] = (now.date() - datetime.fromisoformat(st.get("adopted", now.date().isoformat())).date()).days
        except ValueError:
            pass
        if st.get("last_touch"):
            f["hours_since_touch"][pid] = (time.time() - st["last_touch"]) / 3600
        if st.get("birthday") and not f["birthday"]:
            f["birthday"] = st["birthday"]
            try:
                mm, dd = int(st["birthday"][:2]), int(st["birthday"][3:5])
                bd = date(now.year, mm, dd)
                if bd < now.date(): bd = date(now.year + 1, mm, dd)
                f["birthday_in"] = (bd - now.date()).days
            except ValueError:
                pass
        log = st.get("logins", {}).get(str(now.weekday()), [])
        all_logins += [int(x[:2]) * 60 + int(x[3:]) for x in log]
        for r in st.get("reminders", []):
            f["reminders"].append(r)
        t = st.get("today") or {}
        if t.get("day") == now.date().isoformat():
            f["today"][pid] = t
        for note in st.get("notes", []):
            text = note.get("text", ""); age = age_days(note)
            m = re.search(r"\bi (?:live in|'m from|am from|moved to)\s+([A-Z][\w' -]{1,30}?)(?=[.,!?;]|$)", text, re.I)
            if m: f["places"].append((m.group(1).strip(), age))
            m = re.search(r"\bi work (?:at|for|in)\s+([^.,!?;]{2,40}?)(?=\s+(?:and|but|because|so)\b|[.,!?;]|$)", text, re.I)
            if m: f["jobs"].append((m.group(1).strip(), age))
            m = re.search(r"\bi (?:want|wish i had|need)\s+([^.,!?;]{2,40}?)(?=\s+(?:and|but|because|so)\b|[.,!?;]|$)", text, re.I)
            if m: f["wants"].append((m.group(1).strip(), age))
            m = re.search(r"\bmy (\w{3,})(?: is| was| are)\s+([^.,!?;]{2,40}?)(?=\s+(?:and|but|because|so)\b|[.,!?;]|$)", text, re.I)
            if m and not re.search(r"\bmy " + PEOPLE, text, re.I) and not re.search(r"\bmy (?:favorite|favourite|name)\b", text, re.I):
                f["things"].append((m.group(1).lower(), m.group(2).strip(), age))
            if not matched(text) and not re.search(r"\bmy name\b|\bi(?:'m|’m|m| am) (?:a )?(?:she|he|they|girl|boy|woman|man)\b|\bcall me\b", text, re.I):
                f["raw"].append((pid, text.strip(), age))
            who = person_named(text)
            if who: f["people"].append((who[0], who[1], age))
            for m in re.finditer(r"\bi (?:really |just )?(?:like|love|enjoy)\s+([^.,!?;]{2,40}?)(?=\s+(?:and|but|because|so)\b|[.,!?;]|$)", text, re.I):
                f["likes"].append((m.group(1).strip(), age))
            for m in re.finditer(r"\bi (?:hate|can't stand|don't like|dislike)\s+([^.,!?;]{2,40}?)(?=\s+(?:and|but|because|so)\b|[.,!?;]|$)", text, re.I):
                f["dislikes"].append((m.group(1).strip(), age))
            m = re.search(r"\bmy (?:favorite|favourite) (\w+) (?:is|are) ([^.,!?;]{2,40}?)(?=\s+(?:and|but|because|so)\b|[.,!?;]|$)", text, re.I)
            if m: f["favorites"].append((m.group(1), m.group(2).strip(), age))
            m = re.search(r"\bi(?:'m|’m|m| am| feel| felt| was| have been)\s+(?:so |very |really |a bit |a little )?" + FEELINGS + r"\b", text, re.I)
            if m: f["feelings"].append((m.group(1).lower(), age))
            m = re.search(EVENTS, text, re.I)
            if m:
                wd = re.search(r"\bon (monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", text, re.I)
                until = _days_until_weekday(wd.group(1), now.date()) if wd else None
                f["events"].append((m.group(1).lower(), age, until))
            m = re.search(r"\bi(?:'m| am) ((?:going to|learning(?: to)?|trying to|starting to|planning to)\s+[^.,!?;]{2,40})", text, re.I)
            if m: f["plans"].append((m.group(1).strip(), age))
            m = re.search(r"\byou(?:'re| are)\s+(?:a bit |a little |kind of |pretty |a |so |very |really )*(\w{3,})\b", text, re.I)
            if m: f["about_pet"][pid] = m.group(1).lower()
    if len(all_logins) >= 2:
        f["usual"] = int(statistics.median(sorted(all_logins)))
        f["today_login"] = max(all_logins)            # the latest arrival logged today
    f["reminders"].sort(key=lambda r: r["when"])
    return f


def _when(age):
    return "today" if age == 0 else ("yesterday" if age == 1 else (f"{age} days ago" if age < 14 else "a while ago"))


def conversation(f, group, rnd):
    """A list of [seat, line]. group = the pets at the table in seat order (pids). rnd = random.Random(seed).
    A line may be pinned to a pet's seat ((pid, line)) when it is about that pet."""
    seats = len(group); seat_of = {pid: i for i, pid in enumerate(group)}
    o = f["owner"]
    S = o.Subj; s = o.subj; obj = o.obj; P = o.Poss; p = o.poss
    V = o.v
    exchanges = []      # about the owner: what they wrote, what happened today; seats are assigned when we assemble
    filler = []         # the routine and the pets themselves: only when there's little else to say

    names = f["names"]
    today = f["today"]
    if today:
        most = max(today, key=lambda k: today[k].get("tickles", 0)); n = today[most].get("tickles", 0)
        if n >= 2:
            exchanges.append([(most, f"{S} tickled me {n} times today."), rnd.choice(["Lucky.", "Only once for me.", "I counted too."]), (most, rnd.choice(["Hehe.", "I allowed it.", "It's a lot."]))])
        asked = [(pid, tid, k) for pid, t in today.items() for tid, k in (t.get("tricks") or {}).items()]
        if asked:
            pid, tid, k = max(asked, key=lambda x: x[2]); tname = TRICK_NAMES.get(tid, tid)
            first = f"{S} asked me for {tname} {k} times today." if k > 1 else f"{S} asked me for {tname} today."
            exchanges.append([(pid, first), rnd.choice(["Again?", f"{S} {V('loves', 'love')} that one.", "Show me later."]), (pid, rnd.choice(["I nailed it.", "Every time.", "My knees."]))])
        if any(t.get("cheers", 0) >= 1 for t in today.values()):
            exchanges.append([f"{S} typed like crazy today.", rnd.choice(["I cheered.", "I saw.", "Deadline, probably."]), rnd.choice(["Go easy on the keys.", "Fast fingers.", "Hope it went well."])])
        mins = max(t.get("away", 0) for t in today.values())
        if mins >= 5:
            gone = f"{mins} minutes" if mins < 60 else (f"{round(mins / 60)} hour" + ("s" if round(mins / 60) != 1 else ""))
            exchanges.append([f"{S} {V('was', 'were')} gone {gone} today.", rnd.choice(["I sat by the door.", "I napped.", "I noticed."]), rnd.choice(["Then back like nothing happened.", "I said hi anyway.", "Long lunch."])])
    for pid, text, age in f["raw"][-4:]:
        short = text if len(text) <= 60 else text[:57].rstrip() + "..."
        exchanges.append([(pid, f"{S} told me: {short}"), rnd.choice(["When?", "Really.", "Huh."]), (pid, rnd.choice([f"{_when(age).capitalize()}.", "I wrote it down.", "That's what it says."]))])
    for place, age in f["places"][-1:]:
        exchanges.append([f"{S} {V('lives', 'live')} in {place}.", rnd.choice([f"What's {place} like?", "Is it far?", "I'd like to see it."]), rnd.choice(["No idea. We live on a taskbar.", "Ask " + obj + ".", "Someday."])])
    for job, age in f["jobs"][-1:]:
        exchanges.append([f"{S} {V('works', 'work')} at {job}.", rnd.choice(["Busy place?", "Do they know about us?", "Every day?"]), rnd.choice([f"{S} {V('doesn\'t', 'don\'t')} say.", "Probably.", "Most days."])])
    for want, age in f["wants"][-1:]:
        exchanges.append([f"{S} {V('wants', 'want')} {want}.", rnd.choice(["Fair.", "Who doesn't.", f"{S} said that {_when(age)}."]), rnd.choice(["We'll see.", "Fingers crossed.", "I hope so."])])
    for thing, value, age in f["things"][-2:]:
        exchanges.append([f"{P} {thing} is {value}.", rnd.choice(["Is it.", "Good to know.", "Since when?"]), rnd.choice([f"Since {_when(age)}.", "That's what I heard.", "Hm."])])

    for rel, name, age in f["people"][-3:]:
        exchanges.append([f"{P} {rel} is called {name}.",
                          rnd.choice([f"{name}. Does {name} know about us?", f"I'd like to meet {name}.", f"Has {o.pro} mentioned {name} since?"]),
                          rnd.choice(["Probably not.", f"{S} wrote it down {_when(age)}.", "Someday."])])
    if f["likes"]:
        x, age = f["likes"][-1]
        ex = [f"{S} {V('likes', 'like')} {x}.", rnd.choice([f"{x.capitalize()} again?", "That explains a lot.", "Good to know."])]
        if f["dislikes"]:
            ex.append(f"And {s} can't stand {f['dislikes'][-1][0]}.")
            ex.append(rnd.choice(["Noted.", "Same, honestly.", "I'll remember that."]))
        exchanges.append(ex)
    elif f["dislikes"]:
        x, age = f["dislikes"][-1]
        exchanges.append([f"{S} can't stand {x}.", rnd.choice(["Who can.", "Good to know.", "I'll remember that."])])
    for what, value, age in f["favorites"][-2:]:
        ex = [f"{P} favorite {what} is {value}."]
        ex.append(f"Good to know for {p} birthday." if f["birthday"] else rnd.choice(["Noted.", "Really.", f"{value.capitalize()}. Okay."]))
        exchanges.append(ex)
    if f["birthday"]:
        d = f["birthday_in"]
        ex = [f"{P} birthday is on {f['birthday'].replace('-', '/')}."]
        if d is not None:
            ex.append("That's today." if d == 0 else ("That's tomorrow." if d == 1 else f"That's in {d} days."))
            ex.append(rnd.choice(["We should do something.", "A dance, maybe.", "Everyone in hats."]))
            ex.append(rnd.choice(["Don't let me forget.", "I'll remind you.", "Deal."]))
        exchanges.append(ex)
    if f["usual"] is not None:
        u = f["usual"]; ex = [f"{S} usually {V('shows', 'show')} up at {u // 60}:{u % 60:02d}."]
        filler.append(ex); ex = filler[-1]
        if f["today_login"] is not None:
            diff = f["today_login"] - u
            ex.append("Right on time today." if abs(diff) <= 10 else (f"{abs(diff)} minutes late today." if diff > 0 else f"{abs(diff)} minutes early today."))
            ex.append(rnd.choice(["I noticed.", "I was watching.", "I keep track."]))
    hours = f["hours_since_touch"]
    if hours:
        names = f["names"]
        most = max(hours, key=hours.get); least = min(hours, key=hours.get)
        if hours[most] >= 1:
            ex = [(most, f"{S} {V('hasn\'t', 'haven\'t')} touched me in {int(hours[most])} hour{'s' if hours[most] >= 2 else ''}.")]
            if least != most and hours[least] < 1:
                ex.append((least, f"{S} played with me just now.")); ex.append((most, "Lucky you.")); ex.append((least, rnd.choice(["I know.", f"Come sit closer to {obj} next time.", "Hehe."])))
            else:
                ex.append("Me neither."); ex.append(rnd.choice(["Busy day.", "We could stand somewhere obvious.", f"{S} will come around."]))
            filler.append(ex)
    for feeling, age in f["feelings"][-2:]:
        ex = [f"{S} said {o.pro} {o.pv('was', 'were')} {feeling} {_when(age)}."]
        if feeling in ("happy", "excited", "proud", "great", "fine", "okay"):
            ex.append(rnd.choice(["Good. Let's keep it that way.", "Then today's a good day for a dance.", "I like those days."]))
        else:
            ex.append(rnd.choice([f"Then let's go easy on {obj} today.", "No zoomies near the cursor, then.", "We should sit with " + obj + "."]))
            ex.append(rnd.choice(["Agreed.", "Okay.", "I'll be gentle."]))
        exchanges.append(ex)
    for event, age, until in f["events"][-2:]:
        ex = [f"{S} {V('has', 'have')} {an(event)} coming up." if (until is not None and until > 0) or age < 2 else f"{S} had {an(event)} {_when(age)}."]
        if until is not None and until > 0:
            ex.append("Tomorrow." if until == 1 else f"In {until} days."); ex.append(rnd.choice([f"Let's be quiet that morning.", f"I hope it goes well for {obj}.", "We should wish " + obj + " luck."]))
        elif age >= 2:
            ex.append(rnd.choice(["How did it go?", f"Did {o.pro} say how it went?", "Should we ask?"])); ex.append(rnd.choice([f"Ask {obj}.", "No idea.", f"{S} didn't say."]))
        else:
            ex.append(rnd.choice([f"I hope it goes well for {obj}.", "Fingers crossed.", "We'll hear about it."]))
        exchanges.append(ex)
    for plan_text, age in f["plans"][-2:]:
        exchanges.append([f"{S} {V('is', 'are')} {plan_text}.", rnd.choice(["Any good yet?", "How's that going?", "Since when?"]), rnd.choice([f"No idea. Ask {obj}.", f"{S} wrote it down {_when(age)}.", "We'll see."])])
    for pid, adj in list(f["about_pet"].items())[:2]:
        exchanges.append([(pid, f"{S} {V('says', 'say')} I'm {adj}."), rnd.choice(["You are.", "Not from where I sit.", "A little."]), (pid, rnd.choice(["Hmph.", "Thanks.", "I'll take it."]))])
    if f["reminders"]:
        r = f["reminders"][0]
        try:
            days = (datetime.fromisoformat(r["when"]).date() - date.today()).days
        except ValueError:
            days = None
        ex = [f"{S} {V('has', 'have')} something on {r['when'][5:10].replace('-', '/')}."]
        if days is not None:
            ex.append("That's today." if days == 0 else ("Tomorrow." if days == 1 else f"{days} days from now."))
        ex.append(rnd.choice([f"I'll remind {obj}.", "I'm not supposed to say what.", f"{S} asked me to remember."]))
        exchanges.append(ex)
    if len(f["picks"]) >= 2:
        pids = list(f["picks"])
        a_, b_ = pids[0], pids[1]
        if f["picks"][a_] and f["picks"][b_]:
            filler.append([(a_, f"{S} picked {rnd.choice(f['picks'][a_])} for me."), (b_, f"{rnd.choice(f['picks'][b_])} for me."), (a_, rnd.choice(["Fair.", "Suits you.", "Hehe."]))])
    if len(f["adopted_days"]) >= 2:
        pids = sorted(f["adopted_days"], key=f["adopted_days"].get, reverse=True)
        d1, d2 = f["adopted_days"][pids[0]], f["adopted_days"][pids[1]]
        first = "I got here today." if d1 == 0 else f"I've been here {d1} day{'s' if d1 != 1 else ''}."
        second = "Same." if d2 == d1 else ("Just today for me." if d2 == 0 else f"{d2} for me.")
        filler.append([(pids[0], first), (pids[1], second), (pids[0], rnd.choice(["You'll like it.", "Time flies.", "Welcome."]) if d1 > d2 else "Hehe.")])
    if not o.name:
        filler.append([f"We still don't know {p} name.", rnd.choice(["Someone should ask.", "There's a notebook for that.", "Maybe tomorrow."])])

    # up to six exchanges, the ones about the owner first; the routine and the pets themselves only fill the gaps.
    # Seats rotate, except lines that are about a particular pet, which that pet says.
    rnd.shuffle(exchanges); rnd.shuffle(filler)
    want = 6 if seats > 2 else 5
    chosen = exchanges[:want]
    if len(chosen) < want:
        chosen += filler[:want - len(chosen)]
    talk = []
    last = rnd.randrange(seats)
    for ex in chosen:
        for item in ex:
            if isinstance(item, tuple):
                pid, line = item
                who = seat_of.get(pid, (last + 1) % seats)
            else:
                line = item
                who = (last + 1) % seats
            talk.append([who, line]); last = who
    return talk
