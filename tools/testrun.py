"""Test run of everything a pet can do, on the real app code, in a scratch data folder (.testrun/appdata).

Part 1 drives one pet in this process: every trick, every together pick, hide, breaks, sulking and the nudge,
reminders, the notebook, signs, photos, parties, dancing, reactions, mischief, eggs and hatching, the house,
the hat maker, and every dialog. Every frame the pet asks for must exist in its sheet.
Part 2 starts real pets, the house and the stage as separate programs and drives them through the command
files, the way the stage does: plays with everyone, going inside, coming out.

    python tools/testrun.py            # everything
    python tools/testrun.py quick      # part 1 only, one pet
"""
import json, os, random, shutil, subprocess, sys, time, traceback
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
    pet.take_break(); d.run(0.5); kind = pet.break_kind
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
    said_one = lambda key, *fallback: pet.saying and any(pet.saying.get("text", "").startswith(v.split("{")[0]) for v in voice.get(key, list(fallback)) + list(fallback))
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
    for label in ("Tickle", "Tricks", "Keep you company", "Dance", "Hide", "Bathroom break", "Nap", "Notebook", "Remind me", "Hold a sign", "Photo", "Clip 8 seconds", "Throw a party",
                  "Closet", "Hat maker", "Shop", "Enter a code", "Choose tricks", "Pets", "Egg", "Streamer stage", "Music", "Reacts", "With Windows", "Rename", "Your birthday"):
        if not MENU.TIPS.get(label): ok(f"a tip for {label}", False, "missing")
    ok("every tile on the panel has a plain tip", all(MENU.TIPS.get(l) for l in ("Tickle", "Keep you company", "Choose tricks", "Reacts")))
    # the arrival: it knows your usual time and says so; the size setting resizes the window
    wd = str(datetime.now().weekday()); pet.st["logins"][wd] = [datetime.now().strftime("%H:%M")] * 3; pet.st["birthday"] = None; pet.st["last_seen"] = datetime.now().isoformat(timespec="minutes")
    pet.unsay(); pet.state = "idle"; pet.routine = []; pet.arrive(); d.run(1, lambda: pet.saying is not None)
    ok("arrival: it says hi on time", pet.saying and pet.saying.get("text", "").startswith("Right on time"), f"say {pet.saying}")
    d.settle(6); before = pet.size; pet.set_size("large"); d.run(0.3); big = pet.size; pet.set_size("medium"); d.run(0.3)
    ok("size: large is bigger, medium is back", big > before and pet.size == before, f"{before} {big} {pet.size}")
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
    pet.inside_until = 0; d.run(3, lambda: (keep_house(), pet.state != "inside")[1]); d.settle(6)
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
    for page in ("tricks", "together", "play", "attitude", "pets", "house", "egg", "break", "inside", "home"):
        try:
            pet.panel.show(page); d.run(0.2)
        except Exception as e_:
            pages_ok = False; d.errors.append(repr(e_))
    pet.panel.close(); d.run(0.2)
    ok("the panel: every page draws", pages_ok and pet.panel is None and not d.errors, d.errors[-1][-200:] if d.errors else "")
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
    cmd("leaf", "party")
    ok("party spreads to the household", wait_for(lambda: all((presence(p) or {}).get("wearing", {}).get("hat") == "party" for p in ("antenna", "ears", "leaf")), 25), f"{[(presence(p) or {}).get('wearing') for p in ('antenna', 'ears', 'leaf')]}")
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
    for _ in range(30):                                      # 6 taps a second for five seconds
        for flags in (0, 2):
            i = IN(); i.type = 1; i.ki = KI(0x7E, 0, flags, 0, None); u.SendInput(1, ctypes.byref(i), ctypes.sizeof(i))
            if flags == 0: time.sleep(0.06)
        time.sleep(0.1); note_says()
    wait_for(lambda: (note_says(), len(said) == 3)[1], 6)
    if F.screen_locked() or F.idle_seconds() > 30:                  # injected keys don't reach a locked PC, and nobody was here to see it
        print("  skip the burst checks: the screen is locked or nobody has touched this PC for a while, so injected keys don't count", flush=True)
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


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
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
hs.root.destroy()
# --house-check--
