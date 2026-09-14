"""Pets on the same desktop noticing each other.

Every pet is its own program, so they talk through small files in %APPDATA%\\Perchlings\\household:
  here/<pet>.json    where I am right now, rewritten a few times a second, gone when I quit
  plans/<a>-<b>.json a plays with b: what, when, where. b picks it up within half a second.
Everything is timed from a shared start moment, so both pets follow the same script on their own.
Routines here are the same shape as the pet's own: (mood, pose, yaw, dx, dy, ms).
"""
import json, os, random, time
from pathlib import Path

KINDS = ["dance", "chase", "wrestle", "race", "nap", "copycat", "hatswap", "peekaboo", "gossip"]
NAMES = {"dance": "Dance", "chase": "Chase", "wrestle": "Wrestle", "race": "Race", "nap": "Nap together", "copycat": "Copycat",
         "hatswap": "Swap hats", "peekaboo": "Peekaboo", "gossip": "Gossip", "parade": "Parade"}
GROUP_KINDS = ["dance", "race", "nap", "peekaboo", "parade", "gossip"]     # for three or more, everyone joins
RIGHT, LEFT = 60, 300      # yaws that face right and left


def base_dir():
    d = Path(os.environ.get("APPDATA", str(Path.home()))) / "Perchlings" / "household"
    (d / "here").mkdir(parents=True, exist_ok=True)
    (d / "plans").mkdir(parents=True, exist_ok=True)
    return d


def announce(pid, info):
    """Say where I am. info: name, x, y, size, facing, state, area, wearing."""
    info = dict(info, pid=pid, ts=time.time())
    p = base_dir() / "here" / f"{pid}.json"
    tmp = p.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(info), encoding="utf-8"); tmp.replace(p)
    except OSError:
        pass


def leave(pid):
    for f in (base_dir() / "here" / f"{pid}.json",):
        try:
            f.unlink()
        except OSError:
            pass


def others(pid, area=None, max_age=2.0):
    """Every other pet that is out right now, on the same screen if area is given."""
    out = []
    now = time.time()
    for f in (base_dir() / "here").glob("*.json"):
        if f.stem == pid:
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if now - d.get("ts", 0) > max_age:
            continue
        if area is not None and list(d.get("area", [])) != list(area):
            continue
        out.append(d)
    return out


def propose(kind, me, partner, meet_x, seed=None, lead=1.5, group=None):
    """A plan with one partner, or with everyone in group (a list of pids including me; slots follow that order)."""
    members = list(group) if group else [me, partner]
    plan = {"kind": kind, "a": me, "b": partner, "t0": time.time() + lead, "meet_x": int(meet_x),
            "seed": seed if seed is not None else random.randint(0, 10 ** 6), "group": members}
    try:
        for pid in members:
            if pid != me:
                (base_dir() / "plans" / f"{me}-{pid}.json").write_text(json.dumps(dict(plan, b=pid)), encoding="utf-8")
    except OSError:
        return None
    return plan


def take_plan(me):
    """A plan someone made with me, if any. Taking it removes it."""
    for f in (base_dir() / "plans").glob(f"*-{me}.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8")); f.unlink()
        except (OSError, ValueError):
            continue
        if time.time() - d.get("t0", 0) < 8:      # not stale
            return d
    return None


def clear_plans(me):
    for f in (base_dir() / "plans").glob(f"{me}-*.json"):
        try:
            f.unlink()
        except OSError:
            pass


# ------------------------------------------------------------------ scripts
def walk_to(x, target, size, speed=6, ms=45):
    """Walk frames from x to target (window left edges). Returns (steps, facing)."""
    steps = []
    dx = target - x
    facing = 1 if dx >= 0 else -1
    yaw = RIGHT if facing > 0 else LEFT
    n = int(abs(dx) // speed)
    for i in range(n):
        steps.append(("happy", "walk1" if i % 2 == 0 else "walk2", yaw, speed * facing, 0, ms))
    rem = abs(dx) - n * speed
    if rem:
        steps.append(("happy", "idle", yaw, rem * facing, 0, ms))
    return steps, facing


def script(kind, role, me, other, plan, picks=None, lines=None):
    """The steps for my side of a play. role is "a" (who asked) or "b". me/other are presence dicts."""
    rnd = random.Random(plan["seed"])
    size = me["size"]; gap = int(size * 0.55)
    meet = plan["meet_x"]
    group = plan.get("group") or [plan["a"], plan["b"]]
    n = len(group); slot = group.index(me["pid"]) if me.get("pid") in group else (0 if role == "a" else 1)
    mid = (n - 1) / 2
    if kind == "gossip":                         # a half circle: everyone faces the middle, the middle ones sit a little further back
        spread = size * (1.0 if n <= 3 else 0.9)
        my_spot = int(meet + (slot - mid) * spread)
        face_other = RIGHT if slot < mid else (LEFT if slot > mid else 0)
        face_away = LEFT if slot < mid else (RIGHT if slot > mid else 180)
    elif n > 2:                                  # a line, everyone facing you
        my_spot = int(meet + (slot - mid) * size * 1.15)
        face_other, face_away = 0, 180
    else:                                        # a on the left, b on the right, facing each other
        my_spot = meet - gap if role == "a" else meet + gap
        face_other = RIGHT if role == "a" else LEFT
        face_away = LEFT if role == "a" else RIGHT
    # everyone's walk-in takes the same 3.5 s (faster steps for the ones further away), so the choreography starts together
    INTRO_MS = 3500; n_steps = INTRO_MS // 45 - 6
    dist = abs(my_spot - me["x"])
    steps, _ = walk_to(me["x"], my_spot, size, speed=max(4, -(-dist // n_steps)))
    used = sum(s[5] for s in steps)
    steps.append(("happy", "idle", face_other, 0, 0, max(120, INTRO_MS - used)))
    intro = sum(s[5] for s in steps)            # how long my walk-in takes; says are timed from after it
    say = []                                    # (at_ms_from_choreo_start, text)

    if kind == "dance":
        for beat in range(8):
            yaw = face_other if beat % 4 < 2 else face_away
            steps += [("happy", "squash", yaw, 0, 0, 170), ("happy", "stretch", yaw, 0, -10, 170), ("happy", "idle", yaw, 0, 10, 110)]
        steps += [("happy", "idle", y, 0, 0, 70) for y in (0, 60, 120, 180, 240, 300)]
        steps += [("surprised", "idle", face_other, 0, 0, 300), ("happy", "squash", face_other, 0, 0, 120)]
    elif kind == "chase":
        runner_first = "b"
        for leg in range(2):
            i_run = (role == runner_first) if leg == 0 else (role != runner_first)
            direction = 1 if role == "b" else -1                 # b runs right, a runs left, then they come back
            if leg == 1: direction = -direction
            yaw = RIGHT if direction > 0 else LEFT
            if i_run:
                for i in range(22): steps.append(("surprised", "walk1" if i % 2 == 0 else "walk2", yaw, 16 * direction, 0, 45))
            else:
                steps.append(("happy", "idle", yaw, 0, 0, 260))     # a head start for the runner
                for i in range(22): steps.append(("happy", "walk1" if i % 2 == 0 else "walk2", yaw, 16 * direction, 0, 45))
        steps += [("happy", "squash", face_other, 0, 0, 150), ("happy", "idle", face_other, 0, 0, 400)]
    elif kind == "wrestle":
        toward = 1 if role == "a" else -1                  # toward the other one
        back = int(size * 0.7)
        # back off, glare, charge, collide, and one goes flying; twice, then the loser stays down for a bit
        steps += [("sulky", "idle", face_other, -6 * toward, 0, 60)] * 8 + [("sulky", "idle", face_other, 0, 0, 500)]
        say.append((700, rnd.choice(["Rawr.", "Grr.", "You and me."])))
        first_loser = "a" if rnd.random() < 0.5 else "b"
        t_ms = 8 * 60 + 500
        for rnd_no, loser in enumerate((first_loser, "b" if first_loser == "a" else "a", first_loser)):
            # charge: 9 fast steps toward each other
            steps += [("surprised", "walk1" if i % 2 == 0 else "walk2", face_other, 9 * toward, 0, 45) for i in range(9)]
            # collide: both squash and shake
            steps += [("surprised", "squash", face_other, 4 * toward, 0, 70), ("surprised", "squash", face_other, -4 * toward, 0, 70)] * 3
            t_ms += 9 * 45 + 6 * 70
            if role == loser:                               # knocked back and flat
                steps += [("surprised", "stretch", face_other, -14 * toward, -6, 40)] * 5 + [("surprised", "idle", face_other, -6 * toward, 6, 40)] * 5
                steps += [("sulky", "lie", 0, 0, 0, 1100 if rnd_no < 2 else 2600)]
                steps += [("happy", "squash", face_other, 0, 0, 200), ("happy", "idle", face_other, 0, 0, 200)]
                if rnd_no == 2: say.append((t_ms + 900, rnd.choice(["Okay, you win.", "Ow.", "Rematch tomorrow."])))
            else:                                           # stands tall, then struts
                steps += [("happy", "stretch", face_other, 0, -8, 200), ("happy", "idle", face_other, 0, 8, 200)] * 2 + [("happy", "idle", face_other, 0, 0, 200)]
                if rnd_no == 2:
                    steps += [("happy", "idle", y, 0, 0, 70) for y in (0, 60, 120, 180, 240, 300)] + [("happy", "stretch", 0, 0, -10, 150), ("happy", "idle", 0, 0, 10, 150)]
                    say.append((t_ms + 900, rnd.choice(["I win.", "Too easy.", "Hehe."])))
                else:
                    steps += [("happy", "idle", face_other, 0, 0, 1100 - 200)]
            t_ms += 10 * 40 + (1100 if rnd_no < 2 else 2600) + 400
            # walk back to your corner before the next round
            if rnd_no < 2:
                steps += [("happy", "walk1" if i % 2 == 0 else "walk2", face_away, -5 * toward, 0, 50) for i in range(6)] + [("sulky", "idle", face_other, 0, 0, 300)]
                t_ms += 6 * 50 + 300
        steps += [("happy", "squash", face_other, 0, 0, 120), ("happy", "idle", face_other, 0, 0, 300)]
    elif kind == "race":
        left = max(me["area"][0], meet - 700)                      # a run of about 1,200 px, not the whole wide screen
        right = min(me["area"][2] - size, left + 1200 + int(size * 1.4))
        start = left + int(slot * size * 1.1)
        s2, _ = walk_to(my_spot, start, size, speed=8); steps += s2
        steps += [("surprised", "idle", RIGHT, 0, 0, 900)]              # on your marks
        i_win = slot == rnd.randrange(n)
        speed = 24 if i_win else rnd.choice((19, 20, 21, 22))
        dist = (right - int(size * 1.4)) - start
        m = max(1, dist // speed)
        for i in range(m): steps.append(("happy", "walk1" if i % 2 == 0 else "walk2", RIGHT, speed, 0, 40))
        if i_win:
            steps += [("happy", "stretch", 0, 0, -10, 150), ("happy", "idle", 0, 0, 10, 150)] * 3
            say.append((900 + m * 40 + 100, "Won."))
        else:
            steps += [("sulky", "idle", 180, 0, 0, 1200), ("happy", "idle", 0, 0, 0, 300)]
    elif kind == "nap":
        steps += [("sleepy", "squash", face_other, 0, 0, 900), ("sleepy", "idle", face_other, 0, 0, 900)] * 10
        steps += [("happy", "stretch", face_other, 0, 0, 500), ("happy", "idle", face_other, 0, 0, 200)]
    elif kind == "copycat":
        trick = rnd.choice([t for t in (picks or []) if t in ("bounce", "spin", "wave", "sit")] or ["bounce"])
        do = {"bounce": [("happy", "stretch", 0, 0, -12, 110), ("happy", "idle", 0, 0, 12, 110)] * 4,
              "spin": [("happy", "idle", y, 0, 0, 80) for y in (0, 60, 120, 180, 240, 300)] * 2,
              "wave": [("happy", "wave1", face_other, 0, 0, 170), ("happy", "wave2", face_other, 0, 0, 170)] * 4,
              "sit": [("happy", "sit", 0, 0, 0, 1400)]}[trick]
        watch = [("surprised", "idle", face_other, 0, 0, sum(s[5] for s in do))]
        steps += (do + watch) if role == "a" else (watch + do)
        steps += [("happy", "squash", face_other, 0, 0, 120), ("happy", "idle", face_other, 0, 0, 300)]
    elif kind == "hatswap":
        toward = 1 if role == "a" else -1
        # step in close, look each other over, both hats off with a hop, a beat bare-headed, then each puts on the other's
        steps += [("happy", "walk1" if i % 2 == 0 else "walk2", face_other, 5 * toward, 0, 50) for i in range(4)]
        steps += [("surprised", "idle", face_other, 0, 0, 700)]
        say.append((250, rnd.choice(["Nice hat.", "Ooh.", "I like yours."])))
        steps += [("happy", "stretch", face_other, 0, -14, 160), ("happy", "idle", face_other, 0, 14, 160)]       # hop: hats off at the top (900 ms)
        steps += [("surprised", "idle", face_other, 0, 0, 900)]                                                  # bare heads
        steps += [("happy", "squash", face_other, 0, 0, 200), ("happy", "stretch", face_other, 0, -10, 160), ("happy", "idle", face_other, 0, 10, 160)]   # hats on (2,300 ms)
        say.append((2500, rnd.choice(["Mine now.", "Trade you.", "How do I look?"])))
        steps += [("happy", "idle", face_other, 0, 0, 900), ("happy", "idle", face_away, 0, 0, 300)]
    elif kind == "peekaboo":
        down = [("happy", "idle", face_other, 0, 12, 30)] * 10
        up = [("surprised", "idle", face_other, 0, -12, 30)] * 10
        mine = down + [("happy", "idle", face_other, 0, 0, 700)] + up + [("happy", "stretch", face_other, 0, 0, 200)]
        wait = [("happy", "idle", face_other, 0, 0, sum(s[5] for s in mine))]
        for k in range(n):                       # taking turns down the line
            steps += mine if k == slot else wait
        steps += [("happy", "squash", face_other, 0, 0, 120), ("happy", "idle", face_other, 0, 0, 300)]
    elif kind == "parade":                       # follow the leader, there and back
        for direction in (1, -1):
            yaw = RIGHT if direction > 0 else LEFT
            steps += [("happy", "idle", yaw, 0, 0, 220)] * (slot if direction > 0 else n - 1 - slot)   # the line stretches out
            for i in range(28): steps.append(("happy", "walk1" if i % 2 == 0 else "walk2", yaw, 9 * direction, 0, 55))
            steps += [("happy", "squash", yaw, 0, 0, 150)]
        steps += [("happy", "stretch", 0, 0, -10, 150), ("happy", "idle", 0, 0, 10, 300)]
    elif kind == "gossip":
        mine = list(lines or ["Psst.", "..."])
        random.shuffle(mine)                            # each pet's own facts, in its own order
        back = -int(size * 0.14) if (n > 2 and abs(slot - mid) < 0.6) else 0        # the middle of the circle sits further back
        steps += [("happy", "squash", face_other, 0, back, 200), ("happy", "sit", face_other, 0, 0, 600)]   # everyone sits down
        turns = 12 if n > 2 else 10; beat = 3000
        my_turn = 0
        for i in range(turns):
            speaker_slot = i % n
            funny = rnd.random() < 0.35
            if slot == speaker_slot:
                say.append((800 + i * beat + 200, mine[my_turn % len(mine)])); my_turn += 1
                steps += [("happy", "sit", face_other, 0, -4, 200), ("happy", "sit", face_other, 0, 4, 200), ("happy", "sit", face_other, 0, 0, beat - 400)]   # talking: a little bob
            else:                                          # listening: a look up, a nod, sometimes a laugh
                if funny:
                    steps += [("surprised", "sit", face_other, 0, 0, 900), ("happy", "sit", face_other, 0, -6, 150), ("happy", "sit", face_other, 0, 6, 150),
                              ("happy", "sit", face_other, 0, -6, 150), ("happy", "sit", face_other, 0, 6, 150), ("happy", "sit", face_other, 0, 0, beat - 1500)]
                else:
                    steps += [("surprised", "sit", face_other, 0, 0, 1200), ("happy", "sit", face_other, 0, 0, beat - 1200)]
        steps += [("happy", "sit", face_other, 0, 0, 300), ("happy", "squash", face_other, 0, -back, 200), ("happy", "idle", face_other, 0, 0, 300)]   # up again
        say.append((800 + turns * beat + 300, rnd.choice(["Don't tell them.", "Anyway.", "Same time tomorrow."])))
    # then everyone goes their own way, so they don't end up standing in a clump
    if kind not in ("nap",):
        away = -1 if (slot < n / 2) else 1
        dist = int(size * (1.2 + 0.8 * rnd.random()) + abs(slot - (n - 1) / 2) * size * 0.6)
        target = max(me["area"][0], min(me["area"][2] - size, my_spot + away * dist))
        part, _ = walk_to(my_spot, target, size, speed=5)
        steps += part + [("happy", "idle", 0, 0, 0, 200)]
    return steps, [(intro + at, text) for at, text in say], intro


def gossip_lines(st, other):
    """What this pet could say about the owner, from what it knows. Kept kind."""
    import statistics
    from datetime import datetime
    lines = ["Psst.", "Hehe.", "Don't tell them I said that."]
    now = datetime.now()
    log = st.get("logins", {}).get(str(now.weekday()), [])
    if len(log) >= 2:
        mins = sorted(int(t[:2]) * 60 + int(t[3:]) for t in log)
        m = int(statistics.median(mins))
        lines.append(f"They usually show up at {m // 60}:{m % 60:02d}.")
    last = st.get("last_touch")
    if last:
        h = (time.time() - last) / 3600
        if h >= 1: lines.append(f"Haven't been touched in {int(h)} hour{'s' if h >= 2 else ''}.")
        else: lines.append("They played with me just now.")
    if st.get("birthday"):
        lines.append("Their birthday is on " + st["birthday"].replace("-", "/") + ".")
    hat = (other or {}).get("wearing", {}).get("hat")
    if hat: lines.append("Nice hat, by the way.")
    if st.get("attention", 70) < 40: lines.append("I'm a little bored, honestly.")
    try:
        days = (now.date() - datetime.fromisoformat(st.get("adopted", now.date().isoformat())).date()).days
        lines.append("I've been here " + ("since today." if days == 0 else f"{days} day{'s' if days != 1 else ''}."))
    except ValueError:
        pass
    picks = st.get("picks", [])
    if picks:
        lines.append("They picked " + rnd_name(picks) + " for me.")
    rems = st.get("reminders", [])
    if rems:
        lines.append("They've got something on " + rems[0]["when"][5:10].replace("-", "/") + ". I'm not supposed to say.")
    lines.append(f"It's {now.strftime('%I:%M').lstrip('0')} already." if now.hour >= 18 else f"It's only {now.strftime('%I:%M').lstrip('0')}.")
    lines.append(rnd_pick(["They talk to their screen sometimes.", "They forgot to say hi this morning.", "I saw what they had for lunch.", "They think I'm not watching.", "They like you better, I think."]))
    hatw = (st.get("wearing") or {}).get("hat")
    if hatw: lines.append("They put this hat on me. I didn't ask.")
    return lines


def rnd_name(picks):
    nice = {"bounce": "Bounce", "peekaboo": "Peekaboo", "zoomies": "Zoomies", "nap": "Nap anywhere", "sit": "Sit", "lie": "Lie down", "spin": "Spin", "wave": "Wave",
            "calm": "Calm", "sleepy": "Sleepy", "clingy": "Clingy", "showoff": "Show-off", "study": "Study with me", "work": "Work with me", "game": "Game with me", "eat": "Eat with me"}
    return nice.get(random.choice(picks), "things")


def rnd_pick(options):
    return random.choice(options)
