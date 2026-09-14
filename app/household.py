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
GROUP_KINDS = ["dance", "race", "nap", "peekaboo", "parade"]     # for three or more, everyone joins
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
    if n > 2:                                    # a line, everyone facing you
        my_spot = int(meet + (slot - (n - 1) / 2) * size * 1.15)
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
        toward = 1 if role == "a" else -1
        say.append((300, rnd.choice(["Rawr.", "Grr.", "Hey."])))
        for i in range(6):
            steps += [("surprised", "squash", face_other, 6 * toward, 0, 90), ("surprised", "stretch", face_other, -6 * toward, -4, 90), ("happy", "idle", face_other, 0, 4, 60)]
        winner = "a" if rnd.random() < 0.5 else "b"
        if role == winner:
            steps += [("happy", "stretch", face_other, 0, -8, 200), ("happy", "idle", face_other, 0, 8, 200)] * 2
            say.append((2200, "I win."))
        else:
            steps += [("sulky", "idle", face_away, 0, 0, 900), ("happy", "idle", face_other, 0, 0, 200)]
            say.append((2200, "Okay, you win."))
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
        steps += [("happy", "idle", face_other, 8 * toward, 0, 120), ("surprised", "squash", face_other, 0, 0, 260), ("happy", "idle", face_other, -8 * toward, 0, 120)]
        say.append((500, rnd.choice(["Mine now.", "Trade you.", "Hehe."])))
        steps += [("happy", "idle", face_away, 0, 0, 300)]
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
        rnd.shuffle(mine)
        for i in range(4):
            speaker = "a" if i % 2 == 0 else "b"
            if role == speaker:
                say.append((i * 2600 + 200, mine[i % len(mine)]))
                steps += [("happy", "squash", face_other, 0, 0, 200), ("happy", "idle", face_other, 0, 0, 2400)]
            else:
                steps += [("surprised", "idle", face_other, 0, 0, 1300), ("happy", "idle", face_other, 0, 0, 1300)]
        steps += [("happy", "squash", face_other, 0, 0, 150), ("happy", "idle", face_other, 0, 0, 300)]
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
    return lines
