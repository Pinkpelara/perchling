"""Test run of everything a pet can do, on the real app code, in a scratch data folder (.testrun/appdata).

Part 1 drives one pet in this process: every trick, every together pick, hide, breaks, sulking and the nudge,
reminders, the notebook, signs, photos, parties, dancing, reactions, mischief, eggs and hatching, the house,
the hat maker, and every dialog. Every frame the pet asks for must exist in its sheet.
Part 2 starts real pets, the house and the stage as separate programs and drives them through the command
files, the way the stage does: plays with everyone, going inside, coming out.

    python tools/testrun.py            # everything
    python tools/testrun.py quick      # part 1 only, one pet
"""
import gc, json, os, random, re, shutil, subprocess, sys, time, traceback
import tkinter as tk
from datetime import datetime, timedelta, date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / ".testrun"
shutil.rmtree(DATA, ignore_errors=True)
(DATA / "appdata").mkdir(parents=True)
os.environ["APPDATA"] = str(DATA / "appdata")
os.environ["PERCH_FAST_PLAY"] = "1"
sys.path.insert(0, str(ROOT / "app"))
import perchling as P, household as H, fun as F, hatmaker as HM, eggs as E, petnotes as N, stage as S   # noqa: E402

PY = sys.executable
FAILS, PASSES = [], []
QUICK = "quick" in sys.argv[1:]


def ok(name, cond, detail=""):
    (PASSES if cond else FAILS).append(name + (f": {detail}" if detail and not cond else ""))
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else f"  <- {detail}"), flush=True)


class Driver:
    """Runs a pet's real loop (root.update) and records every frame it asked for and every error."""
    def __init__(self, species):
        self.errors = []
        self.pet = pet = P.Pet(P.load_species(species), selftest=True)
        pet.root.report_callback_exception = lambda *a: self.errors.append("".join(traceback.format_exception(*a)))
        self.misses = []
        fr = pet.frames
        orig = fr._fallback
        def fallback(mood, pose, yaw):
            self.misses.append((mood, pose, yaw)); return orig(mood, pose, yaw)
        fr._fallback = fallback
        pet.last_attention_tick = time.time()

    def run(self, seconds=None, until=None):
        pet = self.pet; t0 = time.time()
        while True:
            pet._selftest_ticks = 0
            try:
                pet.root.update()
            except Exception as e:                       # the root is gone
                self.errors.append(repr(e)); return False
            if until and until():
                return True
            if seconds is not None and time.time() - t0 > seconds:
                return until is None
            time.sleep(0.02)

    def settle(self, timeout=12):
        """Wait for the routine to finish and the pet to be idle again."""
        return self.run(timeout, lambda: self.pet.state in ("idle", "walk", "sit") and not self.pet.routine)


def part1(species="antenna"):
    print(f"\n== part 1: {species} in this process")
    d = Driver(species); pet = d.pet
    sp = pet.sp
    P.save_owner_file(reacts=False, music=False); pet.flags_read = 0     # the real keyboard and speakers stay out of it until their checks
    pet.st["reacts"] = False; pet.st["music"] = False
    real_idle, real_locked = F.idle_seconds, F.screen_locked              # the real ones, for the checks that need a person at the PC
    for ev_ in ("<ButtonPress-1>", "<B1-Motion>", "<ButtonRelease-1>", "<Button-3>", "<Enter>", "<Leave>"):
        pet.label.unbind(ev_)                                              # the owner's real mouse stays out of it: every touch here is a direct call
    pet.root.winfo_pointerxy = lambda: (-9999, -9999)                      # and so does the real cursor (a spin near the pet makes it dizzy)
    F.idle_seconds = lambda: 0.0; F.screen_locked = lambda: False         # nor the PC's idle clock and lock screen
    launched = []
    real_popen = subprocess.Popen
    subprocess.Popen = lambda *a, **k: launched.append(a) or type("Pp", (), {"pid": 0, "poll": lambda s: None})()   # nothing gets started for real
    d.run(0.5)
    ok("window up and drawing", pet.root.winfo_exists() and pet.last_frame is not None)

    # tricks: every one in the catalog, each must run its routine to the end
    for t in sp["catalog"]["tricks"]:
        tid = t["id"]
        before = len(d.misses)
        pet.routine = []; pet.state = "idle"; pet.until = time.time() + 30
        pet.do_trick(tid)
        if tid == "nap":
            ran = pet.state == "sleep"; pet.until = time.time() + 0.3; d.settle(3)
        elif tid == "rot":                                       # lies there for half a minute unless clicked
            d.run(1.0); ran = pet.state == "routine" and pet.bit == "rot" and pet.last_frame[1] == "lie"
            class E0: pass
            pet.drag = (0, 0, pet.x, pet.y, False); pet.on_release(E0())
            ran = ran and pet.saying is not None and d.settle(6)
        else:
            ran = pet.state in ("routine", "hide", "chase") and (len(pet.routine) > 0 or pet.state != "routine")
            pet.routine = [s[:5] + (min(s[5], 2500),) for s in pet.routine]      # long holds (loaf, stare, statue) cut short
            if pet.state == "chase": pet.chase_until = time.time() + 1.5
            done = d.settle(14)
            ran = ran and done
        ok(f"trick {tid}", ran and len(d.misses) == before and not d.errors, f"state {pet.state}, misses {d.misses[before:]}, errors {d.errors[-1:] if d.errors else ''}")

    # together: study/work/game/eat, ended by a click; eating for a while brings a bathroom break after
    for t in sp["catalog"].get("together", []):
        tid = t["id"]; before = len(d.misses)
        pet.do_together(tid); d.run(1.2)
        going = pet.state == "together" and pet.last_frame[1] in ("study", "work", "game", "eat1", "eat2", "stretch")
        if tid == "eat": pet.together_started = time.time() - 20
        class E_: pass
        pet.drag = (0, 0, pet.x, pet.y, False); pet.on_release(E_())
        ok(f"together {tid}", going and pet.state == "idle" and len(d.misses) == before, f"state {pet.state} frame {pet.last_frame}")
    ok("eating leads to a bathroom break", getattr(pet, "after_meal", False) and pet.next_break < time.time() + 100)
    pet.next_break = time.time() - 1; pet.until = 0; pet.state = "idle"; pet.routine = []
    d.run(3, lambda: pet.state == "break")
    ok("break after the meal starts", pet.state == "break" and pet.break_kind == "bath", f"state {pet.state}")
    pet.until = time.time() + 0.2; d.settle(4)
    ok("break ends, pet back", pet.state in ("idle", "walk", "sit") and pet.saying and pet.saying.get("text") in pet.sp.get("voice", {}).get("bath", ["Don't ask."]), f"say {pet.saying}")
    pet.take_break(); d.run(0.5); kind = getattr(pet, "break_kind", None)
    ok("a break on its own draws the curtain", pet.state == "break" and kind in ("bath", "shower"))
    pet.until = time.time() + 0.2; d.settle(4)

    # hide: a folder until clicked
    pet.hide(); d.run(0.6)
    ok("hide turns into a folder", pet.state == "hide")
    class E_: pass
    pet.drag = (0, 0, pet.x, pet.y, False); pet.on_release(E_()); d.run(0.3)
    ok("a click keeps it hidden (a peek)", pet.state == "hide")
    x0 = pet.x; ev = E_(); ev.x_root, ev.y_root = 100, 100; pet.on_press(ev); ev2 = E_(); ev2.x_root, ev2.y_root = 100 - 200, 100; pet.on_drag(ev2); pet.on_release(ev2); d.run(0.3)
    ok("a drag moves the folder, still hidden", pet.state == "hide" and pet.x - x0 <= -190, f"state {pet.state} dx {pet.x - x0}")
    pet.unhide(); d.run(0.3)
    ok("Come out from the menu finds it", pet.state == "routine" and pet.saying and pet.saying.get("text") in pet.sp.get("voice", {}).get("found", ["Found me."]), f"say {pet.saying}")
    d.settle(6)

    # ignored: 2 h without the cursor -> sulks; 1 h -> a nudge
    pet.st["last_touch"] = time.time() - P.IGNORED_AFTER - 5; pet.last_attention_tick = time.time() - 61; pet.state = "idle"; pet.routine = []
    d.run(2, lambda: pet.state == "sulk")
    ok("ignored for 2 h: sulks", pet.state == "sulk" and pet.mood == "sulky", f"state {pet.state}")
    pet.touched(10); pet.until = 0; pet.state = "idle"; pet.mood = "sulky"; d.run(1.5)
    ok("a touch ends the sulk", pet.mood != "sulky", f"mood {pet.mood}")
    pet.st["last_touch"] = time.time() - P.LONELY_AFTER - 5; pet.last_attention_tick = time.time() - 61; pet.next_nudge = 0
    pet.state = "idle"; pet.routine = []; pet.until = time.time() + 30; pet.mood = "happy"; pet.unsay()
    d.run(4, lambda: bool(pet.saying))
    voice = pet.sp.get("voice", {})
    def said_one(key, *fallback):
        """The pet said one of its lines for the moment (with or without the owner's name tacked on)."""
        if not pet.saying:
            return False
        text = pet.saying.get("text", ""); plain = re.sub(r", [A-Z][a-z]+([.?!])$", r"", text)
        return any(t.startswith(v.split("{")[0]) for v in voice.get(key, list(fallback)) + list(fallback) for t in (text, plain))
    ok("ignored for 1 h: a nudge", said_one("nudge", "Play with me?", "Psst.", "I'm bored."), f"say {pet.saying}")
    pet.touched(10); d.settle(6)

    # reminders
    pet.st["reminders"] = [{"when": (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M"), "text": "call mom"}]
    pet.deliver_reminders(); d.run(1.2)
    ok("a reminder hops and speaks", pet.saying and "call mom" in pet.saying.get("text", "") and not pet.st["reminders"], f"say {pet.saying}")
    pet.unsay(); d.settle(6)

    # notebook: notes shape what it says
    pet.st["notes"] = [{"when": datetime.now().isoformat(), "text": s} for s in ("My name is Polin and I'm a woman", "I love sushi", "My cat is called Pumpkin")]
    line = N.recall(pet.st["notes"]); pet.bring_up_a_note(); d.run(1)
    ok("notebook: recalls a note", bool(line) and pet.saying is not None, f"line {line!r}")
    owner = N.owner_from_notes(pet.st["notes"])
    ok("notebook: owner name and pronouns", owner == ("Polin", "she"), f"{owner}")
    low = N.owner_from_notes([{"when": "x", "text": "my name is polin. I am a she"}, {"when": "x", "text": "my cat is called pumpkin"}])
    ok("notebook: a lowercase name and 'I am a she' count too", low == ("Polin", "she") and N.person_named("my cat is called pumpkin") == ("cat", "Pumpkin"), f"{low}")
    d.settle(6)

    # a sign, a photo, a party
    pet.sign = "hello there"; pet.sign_until = time.time() + 2; pet.routine = []; pet.state = "sign"; d.run(0.8)
    ok("holds a sign", pet.state == "sign" and not d.errors, d.errors[-1:] if d.errors else "")
    pet.sign_until = 0; d.settle(4)
    path = F.photo(pet.frames.compose("happy", "idle", 0, pet.st["wearing"]), pet.st["name"], out_dir=DATA / "pictures")
    ok("photo saved", path.exists() and path.stat().st_size > 20000)
    pet.party("test"); d.run(2.5)
    ok("party: hat on and confetti", pet.st["wearing"].get("hat") == "party" and (H.base_dir() / "party.json").exists() and not d.errors)
    (H.base_dir() / "party.json").unlink()                     # a real party outlives its file; this one is cut short
    pet.party_until = time.time() - 1; d.run(0.3)
    ok("party over: hat back", pet.st["wearing"].get("hat") != "party")

    # dancing to music (forced, the same path the music takes)
    pet.dance_force_until = time.time() + 19; pet.state = "idle"; pet.until = 0; pet.routine = []
    d.run(2, lambda: pet.state == "dance"); before = len(d.misses)
    frames = set()                                                # the routine is 16 s by the wall clock, so watch a whole loop
    d.run(16.5, lambda: (frames.add(pet.last_frame[1]), pet.state != "dance")[1])
    ok("dances with real moves", {"walk1", "dab", "flex", "squash"} <= frames and len(d.misses) == before, f"frames {sorted(frames)}")
    # the household dances on one schedule: two and a half minutes on, thirty seconds off, by the wall clock, so nobody rests alone
    ok("the dance schedule is shared and by the clock", P.dance_slot(0) and P.dance_slot(149) and not P.dance_slot(151) and not P.dance_slot(179) and P.dance_slot(180))
    real_ear = pet.ear; pet.ear = type("Ear", (), {"music": True, "hearing": True, "ok": True})(); pet.st["music"] = True; P.save_owner_file(music=True); pet.flags_read = 0
    real_slot = P.dance_slot; P.dance_slot = lambda now: True
    pet.dance_force_until = 0; pet.state = "idle"; pet.until = 0; pet.routine = []; d.run(2, lambda: pet.state == "dance")
    was_dancing = pet.state == "dance"
    P.dance_slot = lambda now: False; d.run(1, lambda: pet.state != "dance"); rested = pet.state != "dance"
    P.dance_slot = lambda now: True; pet.until = 0; pet.routine = []; pet.state = "idle"; d.run(2, lambda: pet.state == "dance")
    ok("the shared breather stops the dance and the music pulls it back", was_dancing and rested and pet.state == "dance", f"{was_dancing} {rested} {pet.state}")
    pet.stop_dancing(); d.run(0.5); ok("Stop dancing on the panel stops it", pet.state != "dance" and pet.dance_rest_until > time.time())
    P.dance_slot = real_slot; pet.ear = real_ear; pet.st["music"] = False; P.save_owner_file(music=False); pet.flags_read = 0; pet.dance_rest_until = 0

    # reactions to typing and undo
    P.save_owner_file(reacts=True); pet.flags_read = 0; pet.st["reacts"] = True; pet.state = "idle"; pet.routine = []; pet.until = time.time() + 30
    pet.keys.presses = [time.time()] * 30; pet.keys.undo_times = []; pet.keys.save_times = []; pet.keys.clicks = []
    pet.last_cheer = 0; pet.unsay(); pet.reactions(time.time()); d.run(1)
    ok("reacts to fast typing", said_one("cheer", "Go go go.", "Look at you go.", "Fast fingers."), f"say {pet.saying}")
    d.settle(6); pet.keys.undo_times = [time.time()] * 3; pet.last_oops = 0; pet.reactions(time.time()); d.run(0.3)
    ok("reacts to undo x3", said_one("oops", "Oops.", "Undo, undo, undo.", "That bad?"), f"say {pet.saying}")
    # the burst is shared with the household: the file says what happened, and the cooldown per kind lives there too
    shared = P.load_react()
    ok("a reaction is written for the other pets", shared.get("kind") == "oops" and shared.get("by") == pet.pid and shared.get("last", {}).get("cheer", 0) > 0, str(shared)[:120])
    pet.unsay(); pet.keys.undo_times = [time.time()] * 3; pet.reactions(time.time()); d.run(0.3)
    ok("the shared cooldown holds", pet.saying is None, f"say {pet.saying}")
    P.react_file().write_text(json.dumps({"kind": "easy", "ts": time.time(), "by": "__other__", "last": {}}), encoding="utf-8")
    pet.react_seen = 0; pet.follow_reaction(time.time()); d.run(0.3)
    ok("follows another pet's reaction", said_one("easy", "Easy.", "It's not going anywhere.", "Breathe."), f"say {pet.saying}")
    pet.follow_reaction(time.time()); ok("but only once", pet.react_seen > 0)
    # the same burst seen by two pets: the second one's own detection comes first and hits the household cooldown; it must
    # join the first pet's reaction with the line, not just nod
    now_ = time.time(); pet.state = "idle"; pet.routine = []; pet.until = now_ + 30; pet.unsay(); pet.react_seen = 0; pet.next_notice = 0; pet.last_cheer = 0
    P.react_file().write_text(json.dumps({"kind": "cheer", "ts": now_ - 0.1, "by": "__other__", "last": {"cheer": now_ - 0.1}}), encoding="utf-8")
    pet.keys.presses = [now_] * 30; pet.reactions(now_); d.run(0.3); pet.follow_reaction(time.time()); d.run(0.3)
    ok("a burst another pet answered first still gets this pet's line", said_one("cheer", "Go go go.", "Look at you go.", "Fast fingers."), f"say {pet.saying}")
    d.settle(6)
    # while dancing it still answers, with the line alone (no hop that would break the dance)
    pet.dance_force_until = time.time() + 15; pet.state = "idle"; pet.until = 0; pet.routine = []; d.run(2, lambda: pet.state == "dance")
    pet.keys.presses = [time.time()] * 30; pet.last_cheer = 0; P.react_file().unlink(missing_ok=True); pet.unsay(); pet.reactions(time.time()); d.run(0.3)
    ok("reacts while dancing", pet.state == "dance" and said_one("cheer", "Go go go.", "Look at you go.", "Fast fingers."), f"state {pet.state} say {pet.saying}")
    pet.dance_force_until = 0; d.run(1, lambda: pet.state != "dance")
    # in the middle of a play it says the line but stays put; hidden or inside it can't
    pet.play_until = time.time() + 30; ok("mid-play: the line, not the hop", pet.reactive() == "say"); pet.play_until = 0
    pet.state = "hide"; ok("hidden: no reaction", pet.reactive() is None); pet.state = "idle"
    # a burst in the middle of a trick the owner asked for: the trick stops and the pet reacts, within a breath
    pet.do_trick("statue"); d.run(0.3); was = pet.state == "routine" and len(pet.routine) > 0
    pet.keys.presses = [time.time()] * 30; pet.last_cheer = 0; P.react_file().unlink(missing_ok=True); pet.unsay()
    t0 = time.time(); pet.reactions(time.time()); d.run(0.25, lambda: pet.saying is not None)
    ok("reacts mid-trick, and fast", was and said_one("cheer", "Go go go.", "Look at you go.", "Fast fingers.") and time.time() - t0 < 0.4 and pet.state == "routine" and len(pet.routine) <= 6,
       f"was {was} state {pet.state} say {pet.saying} routine {len(pet.routine)} dt {time.time() - t0:.2f}")
    d.settle(6)
    # a burst while cooling down still gets a nod: no line, a little squash
    pet.keys.presses = [time.time()] * 30; pet.unsay(); pet.next_notice = 0; pet.react_seen = 0; pet.state = "idle"; pet.routine = []
    pet.reactions(time.time()); d.run(0.2)
    ok("a burst during the cooldown gets a nod, no line", pet.saying is None and pet.state == "routine", f"say {pet.saying} state {pet.state}")
    d.settle(4)
    # asleep on its own: a burst wakes it
    pet.state = "sleep"; pet.mood = "sleepy"; pet.until = time.time() + 30; pet.keys.presses = [time.time()] * 30; pet.last_cheer = 0
    P.react_file().unlink(missing_ok=True); pet.unsay(); pet.reactions(time.time()); d.run(0.3)
    ok("a burst wakes a napping pet", pet.state == "routine" and pet.mood == "happy" and said_one("cheer", "Go go go.", "Look at you go.", "Fast fingers."), f"state {pet.state} say {pet.saying}")
    d.settle(6)
    # away and back: no keyboard or mouse for a while, the pet looks around and sits by the door; the first tap brings hello
    F.idle_seconds = lambda: P.AWAY_AFTER + 5; pet.anim_t = 0; pet.state = "idle"; pet.routine = []; pet.until = time.time() + 30
    d.run(4, lambda: pet.state == "sit" and pet.away == "idle")
    ok("away: it looks around and sits down to wait", pet.away == "idle" and pet.state == "sit", f"away {pet.away} state {pet.state}")
    d.run(1.5); ok("away: it stays sitting, no wandering", pet.state == "sit", f"state {pet.state}")
    F.idle_seconds = lambda: 0.0; pet.unsay(); P.react_file().unlink(missing_ok=True); pet.st["today"] = {"day": date.today().isoformat(), "away": 0}
    t0 = time.time(); d.run(1.5, lambda: pet.saying is not None)
    back = P.load_react()
    ok("back: hello within a second, and the household is told", pet.away is None and said_one("welcome", "Welcome back.") and time.time() - t0 < 1.2 and back.get("kind") == "back",
       f"away {pet.away} say {pet.saying} dt {time.time() - t0:.2f} shared {back.get('kind')}")
    d.settle(6)
    # the lock screen is being away too
    F.screen_locked = lambda: True; pet.anim_t = 0; d.run(1, lambda: pet.state == "sleep")
    ok("lock screen: it sleeps", pet.state == "sleep" and pet.away == "lock", f"state {pet.state} away {pet.away}")
    F.screen_locked = lambda: False; pet.unsay(); P.react_file().unlink(missing_ok=True); d.run(1.5, lambda: pet.saying is not None)
    ok("unlock: hello", pet.away is None and said_one("welcome", "Welcome back."), f"say {pet.saying}")
    d.settle(6)
    ok("it asks for attention after 20 minutes and sulks after an hour", P.LONELY_AFTER == 20 * 60 and P.IGNORED_AFTER == 60 * 60)
    # the cursor lands on it: a look up right away
    class Ev3: pass
    pet.state = "idle"; pet.routine = []; pet.until = time.time() + 5; pet.mood = "happy"; pet.on_hover(Ev3()); d.run(0.15)
    ok("the cursor on it: it looks up at once", pet.last_frame[0] == "surprised", f"frame {pet.last_frame}")
    d.run(0.6)
    # and mid-move too: the glance up during a walk, then back to the walk's own face
    pet.queue_routine([("happy", "walk1", 60, 4, 0, 45), ("happy", "walk2", 60, 4, 0, 45)] * 20); d.run(0.2)
    pet.on_hover(Ev3()); d.run(0.12); mid = pet.last_frame[0]; d.run(0.6); back = pet.last_frame[0]
    ok("the cursor on it mid-walk: a glance up, then on with the walk", mid == "surprised" and back == "happy" and pet.state == "routine", f"mid {mid} back {back} state {pet.state}")
    d.settle(4)
    # picked up: legs kick; lifted high: the parachute; let go: a slow float down and a soft landing with a word
    class EvL: pass
    def evl(x, y):
        e_ = EvL(); e_.x_root, e_.y_root = int(x), int(y); return e_
    pet.state = "idle"; pet.routine = []; pet.unsay(); x0, y0 = pet.x, pet.y
    pet.on_press(evl(x0 + 40, y0 + 40)); pet.on_drag(evl(x0 + 40, y0 + 10)); d.run(0.25)          # 30 px up: kicking, no chute
    kicking = pet.state == "held" and pet.last_frame[1].startswith("dangle") and pet.chute is None
    d.run(0.3)
    ok("in your hand its legs kick, and no chute yet this low and this soon", kicking, f"state {pet.state} frame {pet.last_frame} chute {pet.chute is not None} y0 {y0} floor {pet.floor}")
    d.run(1.1)
    ok("held for over a second: the parachute comes out", pet.chute is not None and pet.chute_imgs is not None, f"chute {pet.chute is not None}")
    pet.on_release(evl(x0 + 40, y0 + 10)); d.run(0.3)
    ok("let go low: it just drops, chute away", pet.state != "float" and pet.chute is None, f"state {pet.state} chute {pet.chute is not None}")
    d.settle(6); pet.unsay()
    pet.on_press(evl(pet.x + 40, pet.y + 40)); pet.on_drag(evl(pet.x + 40, pet.y - 260)); d.run(0.2)
    ok("lifted high: the parachute at once", pet.state == "held" and pet.chute is not None, f"state {pet.state} chute {pet.chute is not None}")
    pet.on_release(evl(pet.x + 40, pet.y)); d.run(0.3)
    floating = pet.state == "float" and pet.chute is not None and said_one("lifted", "Whee.", "Look at me.", "Higher.")
    y1 = pet.y; d.run(1.0); slow = 20 < pet.y - y1 < 80
    ok("let go high: a slow float down under the chute, with a word", floating and slow, f"state {pet.state} chute {pet.chute is not None} say {pet.saying} fell {pet.y - y1:.0f} px in a second")
    d.run(30, lambda: pet.state != "float"); d.run(0.4)
    ok("it lands soft and says so", pet.y == pet.floor and pet.chute is None and said_one("land", "Nailed it.", "Again.", "Ten out of ten."), f"y {pet.y} floor {pet.floor} chute {pet.chute} say {pet.saying}")
    d.settle(6); pet.unsay()
    # the cursor spun around it: dizzy; a slow circle: nothing
    import math as _m
    pointer = [0, 0]; real_pointerxy = pet.root.winfo_pointerxy; pet.root.winfo_pointerxy = lambda: tuple(pointer)
    def circle(turns_per_s, seconds):
        cx, cy = pet.x + pet.size / 2, pet.y + pet.size / 2; t0 = time.time()
        while time.time() - t0 < seconds:
            a = (time.time() - t0) * 2 * _m.pi * turns_per_s
            pointer[0], pointer[1] = cx + _m.cos(a) * pet.size, cy + _m.sin(a) * pet.size
            d.run(0.02)
            if pet.bit == "dizzy": return True
        return False
    pet.state = "idle"; pet.routine = []; pet.until = time.time() + 30; pet.next_dizzy = 0; pet.bit = None
    got = circle(2.2, 1.8)
    ok("the cursor spun around it fast: dizzy, spiral eyes, staggering", got and pet.last_frame[0] == "dizzy" and pet.state == "routine", f"got {got} frame {pet.last_frame} state {pet.state}")
    d.run(3.6); ok("dizzy passes with a word", pet.last_frame[0] != "dizzy" and said_one("dizzy", "Whoa.", "Room's spinning.", "Okay. Okay."), f"frame {pet.last_frame} say {pet.saying}")
    d.settle(6); pet.unsay(); pet.next_dizzy = 0; pet.bit = None; pet.state = "idle"; pet.routine = []; pet.until = time.time() + 30
    ok("a slow circle does nothing", not circle(0.6, 2.5) and pet.bit != "dizzy")
    pointer[0], pointer[1] = 0, 0; pet.root.winfo_pointerxy = real_pointerxy; d.settle(4)
    # a burst mid-dizzy still gets the line; the bars: seven keys in two seconds is a nod, fifteen in five the line
    P.save_owner_file(reacts=True); pet.flags_read = 0; pet.st["reacts"] = True
    pet.state = "idle"; pet.routine = []; pet.unsay(); pet.next_notice = 0; pet.react_seen = 0; pet.last_cheer = 0; P.react_file().unlink(missing_ok=True)
    pet.keys.presses = [time.time()] * 8; pet.reactions(time.time()); d.run(0.3)
    ok("eight keys in two seconds: a nod, no line", pet.state == "routine" and pet.saying is None, f"state {pet.state} say {pet.saying}")
    d.settle(4); pet.state = "idle"; pet.routine = []; pet.next_notice = 0; pet.react_seen = 0; pet.keys.presses = []
    pet.keys.presses = [time.time() - i * 0.3 for i in range(15)]; pet.reactions(time.time()); d.run(0.4)
    ok("fifteen keys in five seconds: the line", said_one("cheer", "Go go go.", "Look at you go.", "Fast fingers."), f"say {pet.saying}")
    d.settle(6); pet.unsay(); pet.keys.presses = []; pet.next_notice = 0; pet.react_seen = 0; P.react_file().unlink(missing_ok=True); pet.state = "idle"; pet.routine = []
    pet.last_easy = 0; pet.keys.clicks = [time.time() - i * 0.5 for i in range(15)]; pet.reactions(time.time()); d.run(0.4)
    ok("fifteen clicks in ten seconds, anywhere: the line", said_one("easy", "Easy.", "It's not going anywhere.", "Breathe."), f"say {pet.saying}")
    pet.keys.clicks = []; d.settle(6); pet.unsay()
    P.save_owner_file(reacts=False); pet.flags_read = 0; pet.st["reacts"] = False; P.react_file().unlink(missing_ok=True)
    # the menu does the same things
    pet.state = "idle"; pet.routine = []; pet.parachute_now(); d.run(0.5)
    up = pet.state in ("routine", "float") and pet.y < pet.floor - 100
    d.run(30, lambda: pet.state not in ("routine", "float"))
    ok("Parachute from the menu: a jump up and the float down", up and pet.y == pet.floor and pet.chute is None, f"up {up} state {pet.state}")
    d.settle(4); pet.next_dizzy = 0; pet.dizzy_now(); d.run(0.3)
    ok("Dizzy from the menu", pet.bit == "dizzy" and pet.last_frame[0] == "dizzy", f"bit {pet.bit} frame {pet.last_frame}")
    d.run(4); d.settle(6); pet.unsay()
    P.save_owner_file(reacts=False); pet.flags_read = 0; pet.st["reacts"] = False; P.react_file().unlink(missing_ok=True)
    # the owner's commands go through whatever the pet is doing
    pet.do_together("study"); d.run(0.3); pet.do_trick("backflip"); d.run(0.2)
    ok("a trick from the menu ends keeping you company", pet.state == "routine" and pet.together is not None and pet.state != "together", f"state {pet.state}")
    d.settle(8)
    pet.hide(); d.run(0.3); pet.do_trick("backflip"); d.run(0.2)
    ok("a trick from the menu brings it out of the folder", pet.state == "routine", f"state {pet.state}")
    d.settle(8)
    pet.take_break(); d.run(0.3); before = pet.state; pet.dance_now(5); d.run(0.5)
    ok("Dance from the menu ends a break", before == "break" and pet.state != "break", f"before {before} state {pet.state}")
    pet.dance_force_until = 0; d.run(1); pet.state = "idle"; pet.routine = []
    pet.state = "sleep"; pet.mood = "sleepy"; pet.until = time.time() + 30; pet.nap_now(); d.run(0.3)
    ok("Nap from the menu works while it's already napping", pet.state == "sleep", f"state {pet.state}")
    pet.state = "idle"; pet.until = 0; pet.routine = []; d.run(0.3)
    # what it remembers about the day feeds the gossip
    pet.st["today"] = {"day": date.today().isoformat(), "tickles": 0, "tricks": {}, "cheers": 0, "away": 0, "notes": 0}
    pet.tickle(); pet.tickle(); pet.do_trick("backflip"); d.settle(8)
    ok("it remembers the day: tickles and tricks asked for", pet.st["today"]["tickles"] == 2 and pet.st["today"]["tricks"].get("backflip") == 1, str(pet.st["today"]))
    # the gossip is about the owner, from the notebook and the day, not filler
    import pettalk as T
    pet.st["notes"] = [{"when": datetime.now().isoformat(timespec="minutes"), "text": t} for t in ("my name is Sam and I am a she", "my dog is called Biscuit", "i love sushi", "im tired today", "going to the gym tomorrow lol")]
    other = {"name": "Tutu", "notes": [], "picks": ["faint"], "adopted": date.today().isoformat(), "last_touch": time.time() - 100}
    talk = T.conversation(T.facts({pet.pid: pet.st, "ears": other}, N.Owner("Sam", "she")), [pet.pid, "ears"], random.Random(3))
    text = " ".join(l for _, l in talk)
    about = sum(1 for k in ("Biscuit", "sushi", "tired", "gym", "tickled", "Backflip") if k in text)
    ok("gossip: about the owner, from the notes and the day", about >= 4 and "picked" not in text and "don't know" not in text, f"{about} facts | {text[:300]}")
    ok("gossip: the pronoun after the name", "Sam said she was tired" in text or "tired" not in text, text[:200])
    pet.st["notes"] = []
    # every tile on the panel has a plain tip
    import menu as MENU
    for label in ("Tickle", "Tricks", "Keep you company", "Dance", "Hide", "Bathroom break", "Nap", "Cursor tricks", "Notebook", "Remind me", "Hold a sign", "Photo", "Clip 8 seconds", "Throw a party",
                  "Closet", "Hat maker", "Shop", "Enter a code", "Choose tricks", "Pets", "Egg", "Streamer stage", "Music", "Reacts", "With Windows", "Rename", "Your birthday"):
        if not MENU.TIPS.get(label): ok(f"a tip for {label}", False, "missing")
    ok("every tile on the panel has a plain tip", all(MENU.TIPS.get(l) for l in ("Tickle", "Keep you company", "Choose tricks", "Reacts")))
    # the arrival: it knows your usual time and says so; the size setting resizes the window
    wd = str(datetime.now().weekday()); pet.st["logins"][wd] = [datetime.now().strftime("%H:%M")] * 3; pet.st["birthday"] = None; pet.st["last_seen"] = datetime.now().isoformat(timespec="minutes")
    pet.unsay(); pet.state = "idle"; pet.routine = []; pet.arrive(); d.run(1, lambda: pet.saying is not None)
    ok("arrival: it says hi on time", pet.saying and pet.saying.get("text", "").startswith("Right on time"), f"say {pet.saying}")
    d.settle(6); before = pet.size; pet.set_size("large"); d.run(0.3); big = pet.size; pet.set_size("medium"); d.run(0.3)
    ok("size: large is bigger, medium is back", big > before and pet.size == before, f"{before} {big} {pet.size}")
    # a damaged state file (a crash mid-write) never takes the pet down: the last good copy is used
    P.save_state(pet.st); sp_ = P.state_path(pet.pid); txt_ = sp_.read_text(encoding="utf-8"); sp_.write_text(txt_[: len(txt_) // 2], encoding="utf-8")
    try:
        back_ = P.load_state(pet.sp, pet.pid); ok("a damaged state file loads from the last good copy", back_.get("name") == pet.st["name"], f"{back_.get('name')}")
    except Exception as e_:
        ok("a damaged state file loads from the last good copy", False, repr(e_))
    P.save_state(pet.st)
    # the owner's birthday is one thing for the whole house
    P.save_owner_file(birthday="03-21"); pet.st["birthday"] = None; pet.arrive(); d.run(0.3)
    ok("the birthday told to one pet reaches this one", pet.st.get("birthday") == "03-21" and P.owner_birthday() == "03-21")
    pet.st["birthday"] = None; P.save_owner_file(birthday=None)
    # every character has a bit for when the cursor lingers and leaves, every time it is free
    pet.state = "idle"; pet.routine = []; pet.until = time.time() + 30; pet.hover_since = time.time() - 3; pet.next_leave_bit = 0; pet.on_leave(None); d.run(0.3)
    ok("hover and leave: the snoop ducks", pet.state == "routine", f"state {pet.state}")
    d.settle(8)
    # a break by kind, the way the panel asks: the shower is a shower
    pet.state = "idle"; pet.routine = []; pet.until = time.time() + 30
    went = pet.take_break("shower"); d.run(0.5)
    ok("a shower from the panel", went and pet.state == "break" and pet.break_kind == "shower", f"{went} {pet.state} {getattr(pet, 'break_kind', None)}")
    pet.until = time.time() + 0.2; d.settle(4)
    pet.state = "idle"; pet.routine = []; pet.party_now(); d.run(0.6)
    ok("a party from the panel", pet.party_until > time.time() and pet.st["wearing"].get("hat") == "party")
    (H.base_dir() / "party.json").unlink(missing_ok=True); pet.party_until = time.time() - 1; d.run(0.3)
    pet.state = "idle"; pet.routine = []; pet.nap_now(); d.run(0.3)
    ok("a nap from the panel", pet.state == "sleep" and pet.mood == "sleepy", f"{pet.state}")
    pet.until = time.time() + 0.2; d.settle(4)
    head, lines = pet.egg_status(); ok("the egg page has something to say", "good day" in head and len(lines) >= 3, head)

    # mischief on the menace setting: every kind (cursor steal is faked so the real cursor stays put)
    import ctypes
    real_set = ctypes.windll.user32.SetCursorPos; ctypes.windll.user32.SetCursorPos = lambda *a: True
    pet.set_chaos("menace"); seen = set()
    for i in range(30):
        random.seed(i); pet.state = "idle"; pet.routine = []; pet.mischief_note = None; pet.bit = None
        pet.do_mischief(); d.run(0.4)
        seen.add(pet.state if pet.state == "steal" else (pet.mischief_note[0] if pet.mischief_note else ("trick" if pet.state == "routine" else "?")))
        pet.steal_until = 0; pet.routine = pet.routine[:1] if pet.bit == "rot" else pet.routine; d.settle(9)
        if seen >= {"steal", "prints", "note", "trick"}: break
    ctypes.windll.user32.SetCursorPos = real_set
    ok("mischief on menace: cursor, footprints, note, and a move", seen >= {"steal", "prints", "note", "trick"} and not d.errors, f"seen {seen} errors {d.errors[-1:] if d.errors else ''}")
    pet.set_chaos("sweet"); ok("attitude dial", pet.st["chaos"] == "sweet" and pet.next_mischief > time.time() + 600)
    pet.set_chaos("cheeky")
    # a clip: three seconds of the pet on the real desktop, as a GIF
    got = {}
    real_start = os.startfile; os.startfile = lambda p_: None
    pet.state = "idle"; pet.routine = []; pet.until = time.time() + 30
    S = pet.size
    F.record_clip(lambda: (pet.x - S * 0.75, pet.y - S * 1.1, pet.x + S * 1.75, pet.y + S * 0.4), seconds=3, fps=12, name="Test", out_dir=DATA / "clips", done=lambda p_: got.update(path=p_))
    d.run(8, lambda: "path" in got); os.startfile = real_start
    from PIL import Image as _I
    total = 0
    if got.get("path") and got["path"].exists():                    # PIL merges identical frames, so count the time, not the frames
        g = _I.open(got["path"])
        for i in range(g.n_frames):
            g.seek(i); total += g.info.get("duration", 0)
    ok("clip: a GIF of the pet", total >= 2500, f"{got} plays {total} ms")

    # the house: walk in, be inside, come out, get called out
    door = int(pet.area[0] + (pet.area[2] - pet.area[0]) * 0.6)
    house = {"door_x": door, "door_y": pet.floor, "x": door - 100, "y": pet.floor - 100, "size": 200, "area": list(pet.area), "open": False}
    def keep_house():
        (H.base_dir() / "house.json").write_text(json.dumps(dict(house, ts=time.time())), encoding="utf-8")
    keep_house()
    ok("sees the house", pet.house_here() is not None)
    pet.state = "idle"; pet.routine = []
    went = pet.go_inside("bedroom", 3)
    d.run(20, lambda: (keep_house(), pet.state == "inside")[1])
    ok("walks to the door and goes in", went and pet.state == "inside" and pet.inside == "bedroom" and pet.root.state() == "withdrawn", f"state {pet.state}")
    d.run(6, lambda: (keep_house(), pet.state != "inside")[1])
    ok("comes out when the time is up", pet.state != "inside" and pet.root.state() == "normal", f"state {pet.state}")
    d.settle(6); pet.go_inside("kitchen", 60); d.run(20, lambda: (keep_house(), pet.state == "inside")[1])
    (H.base_dir() / "plans" / f"house-out-{pet.pid}.json").write_text("{}", encoding="utf-8")
    d.run(4, lambda: (keep_house(), pet.state != "inside")[1])
    ok("called out by the house", pet.state != "inside", f"state {pet.state}")
    d.settle(6); pet.nap_now(); d.run(20, lambda: (keep_house(), pet.state == "inside")[1])
    ok("Nap on the panel goes to the bedroom when the house is out", pet.state == "inside" and pet.inside == "bedroom" and pet.next_house_nap > time.time() + 600, f"state {pet.state} room {pet.inside}")
    pet.inside_until = 0; d.run(3, lambda: (keep_house(), pet.state != "inside")[1]); d.settle(6)
    pet.bring_out_house(); d.run(0.3)
    ok("Bring out the house does nothing when it's already here", not launched and pet.saying is None or not launched)
    launched.clear()
    # the open house itself (its own process, like for real): a click on a room decorates it and does not close the house;
    # a drag moves it; the menu closes it
    code = (ROOT / "tools" / "testrun.py").read_text(encoding="utf-8").split("# --house" + "-check--")[1]
    fake = subprocess.Popen; subprocess.Popen = real_popen                      # this one really runs
    r = subprocess.run([PY, "-c", code], capture_output=True, text=True, cwd=str(ROOT), env=dict(os.environ), timeout=60)
    subprocess.Popen = fake
    for line in (r.stdout + r.stderr).splitlines():
        if line.startswith("CHECK "):
            name, res = line[6:].rsplit(" = ", 1); ok(name, res.strip() == "True", res.strip())
    if "CHECK " not in r.stdout: ok("open house checks ran", False, (r.stdout + r.stderr)[-400:])
    d.settle(6)
    pet.next_break = 0; pet.take_break()
    d.run(20, lambda: (keep_house(), pet.state == "inside")[1])
    ok("a break goes to the bathroom when there's a house", pet.state == "inside" and pet.inside == "bathroom", f"state {pet.state} room {pet.inside}")
    # a reminder that comes due while the pet is in the house: it comes out and says it, in person
    pet.st["reminders"] = [{"when": (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M"), "text": "call mom"}]
    pet.deliver_reminders(); d.run(0.8, lambda: (keep_house(), False)[1])
    ok("a reminder brings the pet out of the house to say it", pet.root.state() == "normal" and pet.state != "inside" and pet.saying and "call mom" in pet.saying["text"], f"win {pet.root.state()} state {pet.state} say {pet.saying}")
    pet.unsay(); d.settle(6)
    pet.inside_until = 0; d.run(3, lambda: (keep_house(), pet.state != "inside")[1]); d.settle(6)
    # a typing burst while it walks to the door: the line, but the errand goes on and it still goes in (0.28.3: the
    # reaction's interrupt() dropped the walk and the pet forgot it was going inside)
    P.save_owner_file(reacts=True); pet.flags_read = 0; pet.st["reacts"] = True
    keep_house(); pet.x = max(pet.area[0], door - 500); pet.place(); pet.state = "idle"; pet.routine = []; went = pet.go_inside("living", 3); d.run(0.4, lambda: (keep_house(), False)[1])
    pet.keys.presses = [time.time()] * 30; pet.last_cheer = 0; P.react_file().unlink(missing_ok=True); pet.unsay(); pet.reactions(time.time()); d.run(0.3)
    line = pet.saying; still = pet.state == "routine" and pet.after_routine is not None
    d.run(1.2); kept = pet.saying is not None and pet.saying.get("text") == (line or {}).get("text")       # the line stays up while it walks on
    d.run(25, lambda: (keep_house(), pet.state == "inside")[1])
    ok("a burst mid-errand: the line, and it still goes inside", went and line is not None and still and kept and pet.state == "inside", f"went {went} say {line} still {still} kept {kept} state {pet.state}")
    P.save_owner_file(reacts=False); pet.flags_read = 0; pet.st["reacts"] = False; P.react_file().unlink(missing_ok=True); pet.unsay()
    pet.inside_until = 0; d.run(3, lambda: (keep_house(), pet.state != "inside")[1]); d.settle(6)
    # dropped on the house: it lands and walks in; dragged out of an open room and let go up high: it floats down there
    class EvD: pass
    def evd(x, y):
        e_ = EvD(); e_.x_root, e_.y_root = int(x), int(y); return e_
    keep_house(); pet.state = "idle"; pet.routine = []
    ok("the house under a point: the closed house is the living room, off it is nothing", pet.house_room_at(door, pet.floor - 50) == "living" and pet.house_room_at(door - 400, pet.floor - 50) is None)
    pet.x = door - 500; pet.place(); pet.on_press(evd(pet.x + 40, pet.y + 40)); pet.on_drag(evd(door, pet.floor - 40)); d.run(0.1)
    pet.on_release(evd(door, pet.floor - 40)); d.run(0.3)
    went = d.run(30, lambda: (keep_house(), pet.state == "inside")[1])
    ok("dropped on the house: it lands, walks to the door and goes in", went and pet.inside == "living", f"state {pet.state} inside {pet.inside}")
    (H.base_dir() / "plans").mkdir(exist_ok=True)
    (H.base_dir() / "plans" / "house-out-antenna.json").write_text(json.dumps({"out": True, "x": door - 500, "y": pet.floor - 300}), encoding="utf-8")
    came = d.run(6, lambda: (keep_house(), pet.state != "inside")[1])
    high = pet.state == "float" and pet.chute is not None and pet.floor - pet.y > 200 and abs(pet.x + pet.size // 2 - (door - 500)) < 4
    ok("dragged out of a room and let go up high: it comes out there, under the chute", came and high, f"state {pet.state} chute {pet.chute is not None} x {int(pet.x)} y {int(pet.y)} floor {pet.floor}")
    d.run(30, lambda: pet.state != "float")
    ok("the float lands on the floor and the chute goes away", pet.y == pet.floor and pet.chute is None, f"y {pet.y} floor {pet.floor} chute {pet.chute}")
    d.settle(6)
    (H.base_dir() / "house.json").unlink()

    # eggs: seven good days -> an egg; a day later it hatches into a new pet (the launch is caught, not run)
    base = date.today()
    pet.st["care"] = {(base - timedelta(days=i)).isoformat(): 5 for i in range(1, 9)}; pet.st["egg_baseline"] = ""
    pet.state = "idle"; pet.routine = []; pet.find_egg(); d.run(0.5)
    egg = pet.egg(); d.settle(6); pet.state = "idle"; pet.routine = []
    ok("finds an egg after seven good days", egg is not None and egg.get("by") == pet.pid and egg.get("variant"), f"egg {egg}")
    egg["found"] = time.time() - E.HATCH_HOURS * 3600 - 10; pet.egg_file().write_text(json.dumps(egg), encoding="utf-8")
    pet.egg_tick(time.time()); d.run(1)
    new = [p for p in P.adopted_ids() if "#" in p]
    ok("egg hatches into a new pet", bool(new) and launched and pet.egg() is None, f"ids {P.adopted_ids()} launched {len(launched)}")
    if new:
        st = P.pet_state(new[0]); ok("hatchling has a name and picks", st.get("hatched") and st.get("name") and st.get("picks"), str(st)[:120])
        P.Frames(new[0], 128, variant=st.get("variant")).compose("happy", "idle", 0, {})
        ok("hatchling's colour renders", True)
        # minis: a hatched pet stays pocket-size for good; only minis count toward the cap, bought pets never do
        class Fake: pass
        old_st = P.pet_state(new[0]); old_st["adopted"] = (date.today() - timedelta(days=400)).isoformat(); f_ = Fake(); f_.st = old_st
        ok("a mini stays small for good", P.Pet.growth(f_) == E.MINI_SCALE and P.Pet.growth(pet) == 1.0, f"{P.Pet.growth(f_)} {P.Pet.growth(pet)}")
        fakes = []
        for n in range(3, 3 + E.MAX_MINIS):
            fp = P.state_path(f"leaf#{n}"); fp.write_text(json.dumps({"hatched": True, "name": f"mini {n}"}), encoding="utf-8"); fakes.append(fp)
        pet.st["care"] = {(base - timedelta(days=i)).isoformat(): 5 for i in range(1, 9)}; pet.st["egg_baseline"] = ""
        pet.find_egg(); d.run(0.3)
        head_full, _ = pet.egg_status()
        ok("six minis: no more eggs, and the page says the nest is full", pet.egg() is None and head_full == "The nest is full.", f"egg {pet.egg()} head {head_full}")
        for fp in fakes: fp.unlink()
        fakes = []
        for kind in ("ears", "leaf", "horns"):                       # every kind bought: still not a mini, still room for an egg
            if not P.state_path(kind).exists():
                P.save_state(P.load_state(P.load_species(kind), kind)); fakes.append(P.state_path(kind))
        pet.find_egg(); d.run(0.3)
        ok("bought pets never count toward the mini limit", pet.egg() is not None, f"ids {P.adopted_ids()}")
        pet.egg_file().unlink(); pet.egg_tick(time.time()); d.settle(6); pet.state = "idle"; pet.routine = []
        for fp in fakes: fp.unlink()

    # the hat maker, the closet, the shop, pick five, codes, notebook and remind dialogs open and close
    hat = HM.save_hat(P.hats_dir(), HM.from_code("PH1-cap-1E1B24-F4F1EA-star-F5C242-Night Star"))
    pet.st["wearing"]["hat"] = "my:" + hat["id"]; pet.frames.forget_custom(); pet.show(*pet.last_frame); d.run(0.5)
    ok("wears a hat from the hat maker", not d.errors)
    for name, fn in (("closet", pet.closet_dialog), ("hat maker", pet.hat_maker), ("shop", pet.shop_dialog), ("picks", pet.pick_dialog),
                     ("code", pet.code_dialog), ("notebook", pet.notebook_dialog), ("remind", pet.remind_dialog)):
        before = set(pet.root.winfo_children())
        try:
            fn(); d.run(0.4)
            new_wins = [w for w in set(pet.root.winfo_children()) - before if isinstance(w, P.tk.Toplevel)]
            ok(f"dialog {name} opens", bool(new_wins) and not d.errors, d.errors[-1:] if d.errors else "no window")
            for w in new_wins: w.destroy()
        except Exception as e:
            ok(f"dialog {name} opens", False, repr(e))
    ok("redeem code path", P.redeem_code("PERCH-NOPE")[0] is False)
    # picks are owned, not capped: a pet code brings five free picks, each unlock spends one, then it is the shop
    codes = P.owned_path().parent / "test-codes.json"; codes.write_text(json.dumps({"PERCH-T-PET": ["pet:leaf"], "PERCH-T-ONE": ["pick:robot"]}), encoding="utf-8")
    o = P.load_owned(); o["free_picks"] = 0
    o["items"] = [i for i in o["items"] if i not in {f"pick:{k}" for k in ("backflip", "karate", "yoga", "scream", "moonwalk", "parkour", "robot")}]
    P.save_owned(o); before_free = 0; P.redeem_code("PERCH-T-PET")
    ok("a pet code brings five free picks", P.free_picks() == before_free + 5, f"{before_free} -> {P.free_picks()}")
    spent = [P.unlock_pick(k) for k in ("backflip", "karate", "yoga", "scream", "moonwalk", "parkour")][:6]
    ok("free picks unlock five, the sixth needs the shop", spent[:5] == [True] * 5 and spent[5] is False and P.free_picks() == before_free
       and P.owns_pick("backflip") and not P.owns_pick("parkour"), f"{spent} free {P.free_picks()}")
    P.redeem_code("PERCH-T-ONE"); ok("a bought pick is added", P.owns_pick("robot"))
    pet.st["picks"] = [k for k in ("backflip", "karate", "yoga", "scream", "moonwalk", "robot", pet.sp["signature"]) if P.owns_pick(k)]
    P.save_state(pet.st); pet.st = P.load_state(pet.sp)
    ok("no cap on active picks", len(pet.st["picks"]) >= 7, str(pet.st["picks"]))
    codes.unlink()
    # the Choose tricks window itself, by clicks, with everything owned: every trick can be switched on and off at will
    owned_before = P.load_owned()
    cat_all = [(g, it) for g in ("tricks", "together", "behaviours") for it in pet.sp["catalog"].get(g, [])]
    P.save_owned(dict(owned_before, items=sorted(set(owned_before["items"]) | {f"pick:{it['id']}" for _, it in cat_all})))
    pet.st["picks"] = [pet.sp.get("signature")]; P.save_state(pet.st)
    def tiles_in(win):
        """label -> (tile frame, selected?, click) for every tile in the window."""
        out = {}
        def walk(w):
            for c in w.winfo_children():
                if isinstance(c, tk.Frame) and c.cget("bg") == MENU.CARD:
                    labels = [x for x in c.winfo_children() if isinstance(x, tk.Label) and x.cget("text")]
                    if labels:
                        sel = int(str(c.cget("highlightthickness"))) == 2
                        out[labels[0].cget("text")] = (c, sel, len(labels) > 1 and labels[1].cget("text") or "")
                walk(c)
        walk(win); return out
    def click(tile):
        tile.event_generate("<Button-1>")
    pet.pick_dialog(); d.run(0.4)
    win = [w for w in pet.root.winfo_children() if isinstance(w, tk.Toplevel) and w.title() == "Choose tricks"][-1]
    tiles = tiles_in(win)
    names = [it["name"] for _, it in cat_all]
    ok("Choose tricks shows every trick, habit and company pick as an owned tile, no price and no free-pick note",
       all(n in tiles for n in names) and not any(tiles[n][2] for n in names), f"{len(tiles)} tiles; notes {[(n, tiles[n][2]) for n in names if n in tiles and tiles[n][2]][:4]}; missing {[n for n in names if n not in tiles][:4]}")
    sig = next(it["name"] for _, it in cat_all if it["id"] == pet.sp.get("signature"))
    ok("only the signature move starts switched on", tiles[sig][1] and sum(1 for n in names if tiles[n][1]) == 1, f"on: {[n for n in names if tiles[n][1]]}")
    # click three tricks on
    for n in ("Backflip", "Moonwalk", "Statue"):
        click(tiles_in(win)[n][0]); d.run(0.25)
    tiles = tiles_in(win)
    ok("a click switches a trick on (the tile shows it)", all(tiles[n][1] for n in ("Backflip", "Moonwalk", "Statue")), f"{[(n, tiles[n][1]) for n in ('Backflip', 'Moonwalk', 'Statue')]}")
    click(tiles_in(win)["Moonwalk"][0]); d.run(0.25); tiles = tiles_in(win)
    ok("a second click switches it off again", not tiles["Moonwalk"][1] and tiles["Backflip"][1], f"moonwalk {tiles['Moonwalk'][1]}")
    click(tiles_in(win)[sig][0]); d.run(0.25)
    ok("the signature move can't be switched off", tiles_in(win)[sig][1])
    save_btn = next(x for w in win.winfo_children() for x in w.winfo_children() if isinstance(x, tk.Button) and x.cget("text") == "Save")
    save_btn.invoke(); d.run(0.4)
    ok("Save keeps exactly what's switched on", sorted(pet.st["picks"]) == sorted([pet.sp.get("signature"), "backflip", "statue"]) and not win.winfo_exists(), f"picks {pet.st['picks']}")
    # they are on the Tricks page now, and they run
    pet.on_menu(ev2); d.run(0.4); pet.panel.win.bind("<FocusOut>", lambda e: None); pet.panel.show("tricks"); d.run(0.3)
    page_tiles = tiles_in(pet.panel.frame)
    ok("the Tricks page lists the ones switched on", "Backflip" in page_tiles and "Statue" in page_tiles and "Moonwalk" not in page_tiles, str(list(page_tiles)[:8]))
    click(page_tiles["Backflip"][0]); d.run(0.4)
    ran = pet.state == "routine" and pet.panel is None
    d.settle(10)
    ok("a trick from the Tricks page runs, and the card closes", ran and not d.errors, f"ran {ran} errors {d.errors[-1:] if d.errors else ''}")
    # reopen, switch one off, save: gone from the page
    pet.pick_dialog(); d.run(0.4)
    win = [w for w in pet.root.winfo_children() if isinstance(w, tk.Toplevel) and w.title() == "Choose tricks"][-1]
    click(tiles_in(win)["Statue"][0]); d.run(0.25)
    next(x for w in win.winfo_children() for x in w.winfo_children() if isinstance(x, tk.Button) and x.cget("text") == "Save").invoke(); d.run(0.4)
    ok("switch one off and Save: it's gone", "statue" not in pet.st["picks"] and "backflip" in pet.st["picks"], str(pet.st["picks"]))
    pet.st["picks"] = ["faint", "sideeye", "study", "work", "peekaboo"] + [p_ for p_ in pet.st["picks"] if p_ not in ("faint", "sideeye", "study", "work", "peekaboo")]; P.save_state(pet.st)
    P.save_owned(owned_before); pet.unsay()
    # the keeper: a sibling that went quiet and a quiet house come back; a pet that quit and a closed house stay away
    P.save_state(P.load_state(P.load_species("ears")))
    H.announce("ears", {"name": "Tutu", "x": 1, "y": 1, "size": 100, "facing": 1, "state": "idle", "area": list(pet.area), "wearing": {}, "inside": None})
    hf = H.base_dir() / "here" / "ears.json"; dd = json.loads(hf.read_text(encoding="utf-8")); dd["ts"] = time.time() - 120; hf.write_text(json.dumps(dd), encoding="utf-8")
    (H.base_dir() / "house.json").write_text(json.dumps({"door_x": 1, "ts": time.time() - 120}), encoding="utf-8")
    launched.clear(); P.keep_household()
    back = [("house" if "--house" in str(c[0]) else str(c[0]).split("--pet ")[-1]) for c in launched]
    hf.unlink(); (H.base_dir() / "house.json").unlink(); launched.clear(); P.keep_household()
    ok("the keeper brings back a quiet pet and a quiet house, not a quit one", sorted(back) == ["ears", "house"] and not launched, f"{back} then {launched}")
    # the panel: every page opens and closes without errors
    class Ev2: pass
    ev2 = Ev2(); ev2.x_root, ev2.y_root = int(pet.x + 40), int(pet.y)
    pet.on_menu(ev2); d.run(0.5)
    pages_ok = pet.panel is not None
    for page in ("tricks", "together", "play", "attitude", "pets", "house", "egg", "break", "inside", "cursor", "home"):
        try:
            pet.panel.show(page); d.run(0.2)
        except Exception as e_:
            pages_ok = False; d.errors.append(repr(e_))
    pet.on_menu(ev2); panel = pet.panel; pending_before = set(panel.timers); panel.close()
    still = [t for t in pending_before if t in str(pet.root.tk.call("after", "info"))]
    ok("a closed panel leaves no timer behind to fire into a reused Tk command", not still and not panel.timers, f"still {still}")
    pet.shop_dialog(); d.run(0.3); wheel_before = bool(pet.root.tk.call("bind", "all", "<MouseWheel>"))
    pet.on_menu(ev2); d.run(0.3); pet.panel.close(); d.run(0.2)
    ok("closing the panel doesn't take the shop's wheel scrolling with it", wheel_before and bool(pet.root.tk.call("bind", "all", "<MouseWheel>")))
    for w_ in pet.root.winfo_children():
        if isinstance(w_, tk.Toplevel) and w_.title() == "Shop": w_.destroy()
    d.run(0.2)
    d.run(0.2)
    pet.on_menu(ev2); d.run(0.5); pet.panel.close(); d.run(0.2)
    ok("the panel: every page draws", pages_ok and pet.panel is None and not d.errors, d.errors[-1][-200:] if d.errors else "")
    # every tile on every page says what it does when a hand rests on it. A hand crosses the tile's edge onto the label,
    # which fires Leave on the tile: the crossing that hid every tip before 0.28.3.
    import menu as MENU
    def tiles_of(panel):
        with_, without = [], []
        def walk(w):
            for c in w.winfo_children():
                if isinstance(c, tk.Frame) and c.cget("bg") == MENU.CARD and any(isinstance(x, tk.Label) for x in c.winfo_children()):
                    (with_ if getattr(c, "tip_text", None) else without).append(c)
                walk(c)
        walk(panel.frame); return with_, without
    def label_of(tile):
        return [x for x in tile.winfo_children() if isinstance(x, tk.Label)][-1]
    def hand_on(tile):
        """The way a hand arrives: onto the tile's edge, across it onto the label, then it rests there."""
        label = label_of(tile)
        cx, cy = label.winfo_rootx() + label.winfo_width() // 2, label.winfo_rooty() + label.winfo_height() // 2
        tile.event_generate("<Enter>", rootx=cx, rooty=cy); tile.event_generate("<Leave>", rootx=cx, rooty=cy); label.event_generate("<Enter>", rootx=cx, rooty=cy)
        d.run(MENU.TIP_DELAY / 1000 + 0.25)
        t = getattr(tile.winfo_toplevel(), "_tip", None)
        shown = t is not None and t.win is not None and t.win.winfo_ismapped() and t.label.cget("text") == tile.tip_text
        label.event_generate("<Leave>", rootx=-5, rooty=-5); d.run(0.05)
        gone = t is None or t.win is None or not t.win.winfo_ismapped()
        return shown, gone
    def open_panel():
        """The card, kept open: it closes on focus-out by design, and a click of the owner's elsewhere on this PC
        would end the check halfway through."""
        if pet.panel is not None: pet.panel.close(); d.run(0.2)
        pet.on_menu(ev2); d.run(0.4); pet.panel.win.bind("<FocusOut>", lambda e: None)
    open_panel()
    seen, bad, untipped = 0, [], []
    for page in ("home", "tricks", "together", "play", "attitude", "pets", "house", "egg", "break", "inside", "cursor"):
        if pet.panel is None: open_panel()
        pet.panel.show(page); d.run(0.25)
        with_, without = tiles_of(pet.panel)
        untipped += [f"{page}: {label_of(t).cget('text')}" for t in without]
        for tile in with_:
            try:
                name = label_of(tile).cget("text"); shown, gone = hand_on(tile); seen += 1
                if not shown: shown, gone = hand_on(tile)                  # once more: the owner's own pointer may have crossed the card
            except tk.TclError as e_:
                bad.append(f"{page}: {name} gone mid-hover ({e_}); panel {pet.panel is not None}; page now {pet.panel.page if pet.panel else None}"); break
            if not (shown and gone): bad.append(f"{page}: {name} shown {shown} gone {gone}")
            if pet.panel is None: bad.append(f"{page}: the panel closed on hover"); break
        if pet.panel is None: break
    ok("every tile on every page shows its tip when a hand crosses onto the label, and hides when it leaves", seen >= 40 and not bad and pet.panel is not None, f"{seen} tiles; {bad[:6]}")
    ok("no tile on any page is without a tip", not untipped, str(untipped[:8]))
    if pet.panel is not None: pet.panel.close(); d.run(0.2)
    # the real pointer, gliding: only in the full run, on an unlocked PC nobody has touched for half a minute (it moves the
    # mouse and puts it back; under a hand it would fight the hand, and a click of theirs would fire whatever tile it sat on)
    if QUICK: pass
    elif real_locked() or real_idle() < 30:
        print("  skip the real-pointer glide: the screen is locked or someone is using this PC", flush=True)
    else:
        import ctypes
        u32 = ctypes.windll.user32
        class PT(ctypes.Structure): _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        was = PT(); u32.GetCursorPos(ctypes.byref(was))
        open_panel()
        with_, _ = tiles_of(pet.panel); glided, missed = 0, []
        for tile in with_[:12]:
            try:
                label = label_of(tile); name = label.cget("text")
                x, y = label.winfo_rootx() + label.winfo_width() // 2, label.winfo_rooty() + label.winfo_height() // 2
                y0 = tile.winfo_rooty() + tile.winfo_height() + 12
                u32.SetCursorPos(x, y0); d.run(0.1)
                for k in range(0, y0 - y, 2): u32.SetCursorPos(x, y0 - k); d.run(0.012)
                u32.SetCursorPos(x, y); d.run(MENU.TIP_DELAY / 1000 + 0.3)
                t = getattr(pet.panel.win, "_tip", None) if pet.panel else None
                if t is not None and t.win is not None and t.win.winfo_ismapped() and t.label.cget("text") == tile.tip_text: glided += 1
                else: missed.append(name)
            except tk.TclError as e_:
                missed.append(f"{name}: gone mid-glide ({e_})"); break
            if pet.panel is None: break
        u32.SetCursorPos(was.x, was.y)
        ok("the real pointer gliding onto a tile brings its tip, and the panel stays open", glided == len(with_[:12]) and pet.panel is not None, f"{glided}/{len(with_[:12])} missed {missed} panel {pet.panel is not None}")
        if pet.panel is not None: pet.panel.close(); d.run(0.2)
    # a newer version on GitHub: the pet says so and the panel's footer offers the update (the check itself, without the network)
    asks = []
    real_newest = P.newest_version; P.newest_version = lambda etag=None: (asks.append(etag) or ("v9.9.9", '"tag-999"')); pet.update_to = None; pet.unsay()
    P.update_file().unlink(missing_ok=True)
    pet.on_menu(ev2); d.run(0.3); pet.check_update(again=False); d.run(2.5, lambda: pet.update_to == "v9.9.9" and pet.saying is not None)
    foot_texts = [w.cget("text") for w in pet.panel.frame.winfo_children()[-1].winfo_children() if isinstance(w, tk.Label)] if pet.panel else []
    ok("a newer version: the pet says so and the open panel shows Update", pet.update_to == "v9.9.9" and pet.saying and "newer me" in pet.saying["text"] and any("Update to 9.9.9" in t for t in foot_texts), f"{pet.update_to} {pet.saying} {foot_texts}")
    pet.panel.close(); d.run(0.2)
    # the answer is written for the household: within the minute nobody asks GitHub again, and the ETag goes with the next ask
    known = P.load_update()
    ok("the household keeps the answer and the ETag", known.get("tag") == "v9.9.9" and known.get("etag") == '"tag-999"' and asks == [None], f"{known} asks {asks}")
    ok("within the minute the household's answer stands, no second ask", P.look_for_update() == "v9.9.9" and len(asks) == 1, f"asks {asks}")
    P.write_json_safely(P.update_file(), {"tag": "v9.9.9", "etag": '"tag-999"', "ts": time.time() - P.UPDATE_EVERY}); P.look_for_update()
    ok("a minute later it asks again, with the ETag", asks == [None, '"tag-999"'], f"asks {asks}")
    # nothing changed: GitHub's 304 keeps the known tag
    P.newest_version = lambda etag=None: ("same", etag)
    P.write_json_safely(P.update_file(), {"tag": "v9.9.9", "etag": '"tag-999"', "ts": time.time() - P.UPDATE_EVERY})
    ok("a 304 keeps the known tag", P.look_for_update() == "v9.9.9" and P.load_update().get("tag") == "v9.9.9")
    # no answer at all (offline): the last known tag stands
    P.newest_version = lambda etag=None: (None, None)
    P.write_json_safely(P.update_file(), {"tag": "v9.9.9", "etag": '"tag-999"', "ts": time.time() - P.UPDATE_EVERY})
    ok("offline: the last known tag stands", P.look_for_update() == "v9.9.9")
    P.newest_version = real_newest; P.update_file().unlink(missing_ok=True); pet.update_to = None; pet.unsay()
    # a note by command, the way the stage tells everyone
    pet.on_command("note", {"text": "I love sushi"}); d.run(0.3)
    ok("a note by command lands in the notebook and gets an answer", pet.st["notes"][-1]["text"] == "I love sushi" and pet.saying is not None, f"{pet.saying}")

    # every mood/pose/yaw the sheet is supposed to have
    idx = pet.frames.index
    need = [f"{m}_{p}_{y:03d}" for m in ("happy", "surprised", "sleepy", "sulky") for p in ("idle", "blink", "walk1", "walk2", "squash", "stretch") for y in (0, 60, 300)]
    need += [f"{m}_sit_000" for m in ("happy", "surprised", "sleepy", "sulky")] + ["happy_sit_060", "happy_sit_300"]
    need += [f"happy_{p}_000" for p in ("lie", "wave1", "wave2", "study", "work", "game", "eat1", "eat2", "dab", "flex")]
    need += [f"happy_idle_{y:03d}" for y in (120, 180, 240)] + ["sulky_idle_180"]
    missing = [k for k in need if k not in idx]
    ok("sheet has every frame the pet uses", not missing, f"missing {missing[:8]}")
    ok("no fallback frames were needed", not d.misses, f"{d.misses[:6]}")
    ok("no errors in the loop", not d.errors, d.errors[-1][-300:] if d.errors else "")
    pet.root.destroy()
    subprocess.Popen = real_popen
    return d


def other_pets():
    print("\n== part 1b: the other pets, tricks and together only")
    for species in ("ears", "leaf", "horns"):
        d = Driver(species); pet = d.pet; d.run(0.3)
        pet.root.winfo_pointerxy = lambda: (-9999, -9999)          # the owner's cursor stays out of it (a spin would make it dizzy)
        for ev_ in ("<ButtonPress-1>", "<B1-Motion>", "<ButtonRelease-1>", "<Button-3>", "<Enter>", "<Leave>"): pet.label.unbind(ev_)
        for t in pet.sp["catalog"]["tricks"]:
            if t["id"] == "nap": continue
            pet.routine = []; pet.state = "idle"; pet.do_trick(t["id"])
            if t["id"] == "rot": d.run(0.6); pet.routine = pet.routine[:1]; pet.routine[0] = ("sulky", "lie", 0, 0, 0, 300)
            pet.routine = [s[:5] + (min(s[5], 2500),) for s in pet.routine]
            if pet.state == "chase": pet.chase_until = time.time() + 1.5
            d.settle(14)
        for t in pet.sp["catalog"].get("together", []):
            pet.do_together(t["id"]); d.run(0.4); pet.stop_together()
        pet.dance_force_until = time.time() + 3; pet.state = "idle"; pet.until = 0; d.run(3.5)
        pet.state = "idle"; pet.routine = []; pet.until = time.time() + 30; pet.hover_since = time.time() - 3; pet.next_leave_bit = 0
        pet.on_leave(None); d.run(0.5)
        leave_ok = pet.state == "routine"                    # every character has a bit, every time it is free
        d.run(8, lambda: pet.state != "routine")
        ok(f"{species}: all tricks, together, dance and the leave bit ({pet.st['name']}, {pet.sp['archetype']})", not d.misses and not d.errors and leave_ok, f"misses {d.misses[:4]} errors {d.errors[-1:] if d.errors else ''} leave {leave_ok}")
        pet.root.destroy()
        pet = d = None; gc.collect()      # Tk objects die here, on the main thread; left to a watcher thread's garbage collection they crash Tcl


# ---------------------------------------------------------------- part 2: real programs
def presence(pid):
    f = H.base_dir() / "here" / f"{pid}.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    except (OSError, ValueError):
        return None


def wait_for(pred, timeout, every=0.1):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if pred(): return True
        except Exception:
            pass
        time.sleep(every)
    return False


def part2():
    print("\n== part 2: real pets, the house and the stage as separate programs")
    env = dict(os.environ); env["PERCH_EXTRA_KEYS"] = "7E"        # the test pets also count F15, so a burst can be injected without typing into anything
    P.save_owner_file(reacts=True, music=False)                    # reactions on for the burst check; the real speakers stay out of it
    procs = {}
    logs = {"house": open(DATA / "house.log", "w", encoding="utf-8")}
    procs["house"] = subprocess.Popen([PY, str(ROOT / "app" / "perchling.py"), "--house"], env=env, cwd=str(ROOT), stdout=logs["house"], stderr=subprocess.STDOUT)
    ok("the house comes out", wait_for(lambda: P.house_info() is not None, 20))
    for pid in ("antenna", "ears", "leaf"):
        logs[pid] = open(DATA / f"{pid}.log", "w", encoding="utf-8")
        procs[pid] = subprocess.Popen([PY, str(ROOT / "app" / "perchling.py"), "--pet", pid], env=env, cwd=str(ROOT), stdout=logs[pid], stderr=subprocess.STDOUT)
    ok("three pets come out", wait_for(lambda: all(presence(p) for p in ("antenna", "ears", "leaf")), 20))
    procs["stage"] = subprocess.Popen([PY, str(ROOT / "app" / "perchling.py"), "--stage"], env=env, cwd=str(ROOT))
    time.sleep(3)
    ok("the stage runs", procs["stage"].poll() is None)

    def cmd(pid, c, **kw):
        for p_, pr in procs.items():
            if pr.poll() is not None and not getattr(pr, "_reported", False):
                pr._reported = True; ok(f"{p_} still running before '{c}'", False, f"exit {pr.returncode}")
        S.command(pid, c, **kw)
    def states(): return {p: (presence(p) or {}).get("state") for p in ("antenna", "ears", "leaf")}
    def all_idle(timeout=40): return wait_for(lambda: all(s in ("idle", "walk", "sit", "sleep") for s in states().values()), timeout)

    cmd("antenna", "wave")
    ok("stage: wave", wait_for(lambda: (presence("antenna") or {}).get("pose") in ("wave1", "wave2"), 6))
    all_idle()
    cmd("ears", "dance")
    ok("stage: dance", wait_for(lambda: (presence("ears") or {}).get("state") == "dance", 6))
    wait_for(lambda: (presence("ears") or {}).get("state") != "dance", 30)

    # every play with everyone: the leader is told, the others must join
    for kind in H.KINDS + ["parade"]:
        all_idle()
        if kind == "hatswap":
            continue                                         # needs two pets in hats; tested below
        cmd("antenna", "play", kind=kind)
        group = kind in H.GROUP_KINDS
        joined = wait_for(lambda: all(states()[p] == "routine" for p in (("antenna", "ears", "leaf") if group else ("antenna",))) and
                          any(states()[p] == "routine" for p in ("ears", "leaf")), 12)
        talk = None
        if kind == "gossip":
            said = set()
            wait_for(lambda: [said.add((presence(p) or {}).get("say", {}).get("text")) for p in ("antenna", "ears", "leaf") if (presence(p) or {}).get("say")] and len(said) >= 6, 40)
            talk = len([s for s in said if s])
        ok(f"play {kind}: everyone joins" + (f", {talk} lines said" if talk is not None else ""), joined and (talk is None or talk >= 4), f"states {states()}")
        all_idle(60)

    # hats on two pets, then a swap
    for pid, hat in (("antenna", "beanie"), ("ears", "crown")):
        pass
    cmd("antenna", "wear", hat="beanie"); cmd("ears", "wear", hat="party"); cmd("leaf", "wear", hat="mushroom")
    hats = lambda: {p: (presence(p) or {}).get("wearing", {}).get("hat") for p in ("antenna", "ears", "leaf")}
    ok("wear by command", wait_for(lambda: hats() == {"antenna": "beanie", "ears": "party", "leaf": "mushroom"}, 8), f"{hats()}")
    all_idle(); cmd("antenna", "play", kind="hatswap")
    swapped = wait_for(lambda: hats()["antenna"] in ("party", "mushroom") and sorted(hats().values()) == ["beanie", "mushroom", "party"], 30)
    ok("play hatswap: hats change heads", swapped, f"{hats()}")
    all_idle(60)

    # the house: a pet goes inside on command, the house shows it, it comes out
    cmd("leaf", "inside", room="living")
    ok("goes inside the house", wait_for(lambda: (presence("leaf") or {}).get("inside") == "living", 25), f"{(presence('leaf') or {}).get('state')} house {P.house_info() is not None}")
    time.sleep(1.5)
    cmd("leaf", "out")
    ok("comes back out", wait_for(lambda: (presence("leaf") or {}).get("inside") is None and (presence("leaf") or {}).get("state") != "inside", 10))
    all_idle()
    # the house, driven the way a pet's panel drives it: through its command file
    S.command("house", "open"); ok("house: open by command", wait_for(lambda: (P.house_info() or {}).get("open") is True, 6))
    S.command("house", "style", style="loft"); ok("house: Loft by command", wait_for(lambda: (P.house_info() or {}).get("style") == "loft", 6))
    S.command("house", "close"); ok("house: close by command", wait_for(lambda: (P.house_info() or {}).get("open") is False, 6))
    S.command("house", "style", style="cozy"); wait_for(lambda: (P.house_info() or {}).get("style") == "cozy", 6)
    cmd("ears", "inside", room="bedroom"); wait_for(lambda: (presence("ears") or {}).get("inside") == "bedroom", 25)
    S.command("house", "out"); ok("house: everyone out by command", wait_for(lambda: (presence("ears") or {}).get("inside") is None, 12), f"{(presence('ears') or {}).get('inside')}")
    all_idle()
    cmd("ears", "trick", id="moonwalk")
    ok("trick by command", wait_for(lambda: states()["ears"] == "routine", 5))
    all_idle()
    for p_ in ("antenna", "ears", "leaf"): cmd(p_, "note", text="We moved to Toronto")
    ok("stage: tell everyone reaches every pet", wait_for(lambda: all((presence(p_) or {}).get("say") for p_ in ("antenna", "ears", "leaf")), 8), f"{[(presence(p_) or {}).get('say') for p_ in ('antenna', 'ears', 'leaf')]}")
    hats_before = hats(); t_party = time.time(); cmd("leaf", "party")
    trail = []
    spread = wait_for(lambda: (trail.append((round(time.time() - t_party, 1), hats(), states())), all(h == "party" for h in hats().values()))[1], 25, every=0.5)
    ok("party spreads to the household", spread, f"before {hats_before}; then " + "; ".join(f"{t}s {h} {st}" for t, h, st in trail[::4]))
    # one real typing burst (F15, a key no app uses, which the test pets count) gets a line from every free pet at the same moment
    wait_for(lambda: all(states()[p] in ("idle", "walk", "sit") for p in ("antenna", "ears", "leaf")), 60)
    cheers = {p: v.get("voice", {}).get("cheer", []) + ["Go go go.", "Look at you go.", "Fast fingers."] for p, v in ((p, P.load_species(p)) for p in ("antenna", "ears", "leaf"))}
    P.react_file().unlink(missing_ok=True)
    import ctypes
    u = ctypes.windll.user32
    class KI(ctypes.Structure): _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort), ("dwFlags", ctypes.c_uint), ("time", ctypes.c_uint), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]
    class IN(ctypes.Structure): _fields_ = [("type", ctypes.c_uint), ("ki", KI), ("pad", ctypes.c_ubyte * 8)]
    said = {}
    def note_says():
        for p_ in ("antenna", "ears", "leaf"):
            s = (presence(p_) or {}).get("say")
            if s and s.get("text") in cheers[p_]: said[p_] = s["text"]
    # one tap first: if this PC has sat untouched for a few minutes the pets are "away", and the tap brings them back (a hello),
    # which must not be mistaken for the cheer; the burst comes after they've settled
    for flags in (0, 2):
        i = IN(); i.type = 1; i.ki = KI(0x7E, 0, flags, 0, None); u.SendInput(1, ctypes.byref(i), ctypes.sizeof(i)); time.sleep(0.06)
    time.sleep(4.5); P.react_file().unlink(missing_ok=True)
    wait_for(lambda: all(states()[p] in ("idle", "walk", "sit") for p in ("antenna", "ears", "leaf")), 30)
    landed = 0
    for _ in range(30):                                      # 6 taps a second for five seconds
        for flags in (0, 2):
            i = IN(); i.type = 1; i.ki = KI(0x7E, 0, flags, 0, None); u.SendInput(1, ctypes.byref(i), ctypes.sizeof(i))
            if flags == 0:
                time.sleep(0.02); landed += 1 if u.GetAsyncKeyState(0x7E) & 0x8000 else 0; time.sleep(0.04)
        time.sleep(0.1); note_says()
    wait_for(lambda: (note_says(), len(said) == 3)[1], 6)
    if F.screen_locked() or F.idle_seconds() > 30:                  # injected keys don't reach a locked PC, and nobody was here to see it
        print("  skip the burst checks: the screen is locked or nobody has touched this PC for a while, so injected keys don't count", flush=True)
    elif landed < 15:                                                # Windows dropped the injection (an elevated window in front, UIPI)
        print(f"  skip the burst checks: only {landed} of 30 injected taps reached the system (an elevated window in front blocks them)", flush=True)
    else:
        ok("a real typing burst reaches every free pet at once", len(said) == 3, f"{said} states {states()}")
        shared = P.load_react()
        ok("the burst was shared through the household file", shared.get("kind") == "cheer" and shared.get("by") in ("antenna", "ears", "leaf"), str(shared)[:100])

    for name, pr in procs.items():
        if pr.poll() is not None:
            logs[name].close()
            ok(f"{name} stayed up", False, f"exit {pr.returncode}; log: " + (DATA / f"{name}.log").read_text(encoding="utf-8", errors="replace")[-600:])
    for pr in procs.values():
        try: pr.terminate()
        except OSError: pass
    time.sleep(1)
    # the house (and any hatchling) the pets started themselves: only test-run processes run from this folder
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process -Filter \"name='pythonw.exe' or name='python.exe'\" | Where-Object { $_.CommandLine -like '*" + str(ROOT / "app" / "perchling.py") + "*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                   capture_output=True)


def stop_leftovers():
    """Test-run pets, house and stage still running from a run that died before its cleanup (they share this folder and
    would haunt the next run: a house that is suddenly "here", pets that answer plans). Only processes started from this
    repo's app/perchling.py; the installed Perchlings.exe is another program."""
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process -Filter \"name='pythonw.exe' or name='python.exe'\" | Where-Object { $_.CommandLine -like '*" + str(ROOT / "app" / "perchling.py") + "*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                   capture_output=True)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    import ctypes
    ctypes.windll.kernel32.CreateMutexW(None, False, "Perchlings-testrun")      # one run at a time: two share .testrun/appdata and wreck each other
    if ctypes.windll.kernel32.GetLastError() == 183:
        sys.exit("another test run is going; wait for it")
    stop_leftovers()
    if what in ("all", "quick"): part1("antenna")
    if what == "all": other_pets()
    if what in ("all", "part2"): part2()
    print(f"\n{len(PASSES)} passed, {len(FAILS)} failed")
    for f in FAILS: print("  FAIL", f)
    if not FAILS: shutil.rmtree(DATA, ignore_errors=True)
    sys.exit(1 if FAILS else 0)


# --house-check--
import os, sys, time
sys.path.insert(0, os.path.join(os.getcwd(), "app"))
import house as HS
hs = HS.House(selftest=False); hs.toggle_open(); hs.root.update(); time.sleep(0.2); hs.root.update()
w = hs.open_win; s = hs.open_scale(); lr = HS.LAYOUT["rooms"]["kitchen"]
cx, cy = int((lr["wall"][0] + lr["wall"][2]) / 2 * s), int((lr["wall"][1] + lr["floor"]) / 2 * s)
class Ev: pass
ev = Ev(); ev.x, ev.y, ev.x_root, ev.y_root = cx, cy, w.winfo_rootx() + cx, w.winfo_rooty() + cy
hs.on_open_press(ev); hs.on_open_release(ev); hs.root.update()
print("CHECK open house: a click on a room opens that room, house stays open =", bool(hs.open and hs.deco_win is not None and hs.deco_win.title() == "Kitchen"))
hs.deco_win.destroy(); hs.root.update()
x0 = w.winfo_x(); hs.on_open_press(ev); ev2 = Ev(); ev2.x, ev2.y, ev2.x_root, ev2.y_root = cx - 100, cy, ev.x_root - 100, ev.y_root
hs.on_open_drag(ev2); hs.on_open_release(ev2); hs.root.update(); time.sleep(0.2); hs.root.update()
print("CHECK open house: a drag moves it =", w.winfo_x() - x0 <= -90 and hs.open)
hs.toggle_open(); print("CHECK open house: the menu closes it =", not hs.open and hs.open_win is None)
hs.on_menu(ev); hs.root.update()
print("CHECK house card: the right click opens a card with tiles =", bool(hs.panel is not None and hs.panel.win.winfo_exists()))
hs.panel.close(); hs.root.update()
hs.decorate_dialog(); hs.root.update()
print("CHECK decorate: a window with a preview and picture tiles =", bool(hs.deco_win.winfo_exists() and hs.deco_win.winfo_reqwidth() > 400 and len([k for k in hs.frames if isinstance(k, tuple) and k[0] == "thumb"]) >= 14))
hs.deco_win.destroy(); hs.root.update()
before = hs.st.get("style", "cozy"); hs.on_command("style", {"style": "loft"}); hs.root.update()
print("CHECK house: a style command switches the style =", hs.st["style"] == "loft")
hs.on_command("style", {"style": before}); hs.on_command("open"); hs.root.update(); opened = hs.open; hs.on_command("close"); hs.root.update()
print("CHECK house: open and close by command =", opened and not hs.open)
# open again: the pets are told the window and the rooms in screen pixels, for drops; a pet in a room can be dragged out
import json as _j
import household as _H, perchling as _P
hs.toggle_open(); hs.root.update(); time.sleep(0.2); hs.root.update(); hs.tell()
info = _P.house_info() or {}
w = hs.open_win; box = info.get("open_box") or []; rooms = info.get("rooms") or {}
print("CHECK open house: it tells the pets its window and its rooms =", bool(len(box) == 4 and box[2] > 200 and set(rooms) >= {"living", "bedroom", "kitchen"} and all(box[0] <= r[0] < r[2] <= box[0] + box[2] + 2 for r in rooms.values())))
# a pet inside: its own presence file says so, the open house draws it and remembers where
here = _H.base_dir() / "here"; here.mkdir(parents=True, exist_ok=True)
(here / "ears.json").write_text(_j.dumps({"pid": "ears", "name": "Tutu", "x": 100, "y": 100, "state": "inside", "inside": "living", "area": list(hs.area), "ts": time.time(), "wearing": {}, "species": "ears"}), encoding="utf-8")
hs.draw_open(); hs.root.update()
bx = getattr(hs, "pet_boxes", {}).get("ears")
print("CHECK open house: a pet inside is drawn in its room and remembered =", bool(bx))
if bx:
    x0, y0, x1, y1, im = bx; px, py = (x0 + x1) // 2, (y0 + y1) // 2 + (y1 - y0) // 6
    ev3 = Ev(); ev3.x, ev3.y, ev3.x_root, ev3.y_root = px, py, w.winfo_rootx() + px, w.winfo_rooty() + py
    hs.on_open_press(ev3); hs.root.update()
    picked = getattr(hs, "pet_drag", None) is not None and hs.pet_drag["pid"] == "ears" and hs.open_drag is None
    ev4 = Ev(); ev4.x, ev4.y, ev4.x_root, ev4.y_root = px - 400, py - 300, ev3.x_root - 400, ev3.y_root - 300
    hs.on_open_drag(ev4); hs.root.update(); hs.on_open_release(ev4); hs.root.update()
    f = _H.base_dir() / "plans" / "house-out-ears.json"
    d = _j.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    print("CHECK open house: a pet dragged out of a room and let go outside: the drop point reaches the pet, the house stays put =", bool(picked and d.get("x") == ev4.x_root and d.get("y") == ev4.y_root and hs.open and getattr(hs, "pet_drag", None) is None))
    f.unlink(missing_ok=True)
    # let go back over the house: nothing happens
    hs.on_open_press(ev3); ev5 = Ev(); ev5.x, ev5.y, ev5.x_root, ev5.y_root = px + 20, py, ev3.x_root + 20, ev3.y_root
    hs.on_open_drag(ev5); hs.on_open_release(ev5); hs.root.update()
    print("CHECK open house: let go back over the house: the pet stays in =", not f.exists() and hs.open)
(here / "ears.json").unlink(missing_ok=True)
hs.toggle_open(); hs.root.update()
hs.root.destroy()
# --house-check--
