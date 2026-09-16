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
    pet.st["reacts"] = False                      # the real keyboard stays out of it until the reactions check
    pet.st["music"] = False                       # and so do the speakers; dancing is forced below
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
    pet.dance_force_until = time.time() + 13; pet.state = "idle"; pet.until = 0; pet.routine = []
    d.run(2, lambda: pet.state == "dance"); before = len(d.misses)
    frames = set()
    d.run(13.5, lambda: (frames.add(pet.last_frame[1]), pet.state != "dance")[1])
    ok("dances with real moves", {"walk1", "dab", "flex", "squash"} <= frames and len(d.misses) == before, f"frames {sorted(frames)}")

    # reactions to typing and undo
    pet.st["reacts"] = True; pet.state = "idle"; pet.routine = []; pet.until = time.time() + 30
    pet.keys.presses = [time.time()] * 30; pet.keys.undo_times = []; pet.keys.save_times = []; pet.keys.clicks = []
    pet.last_cheer = 0; pet.unsay(); pet.reactions(time.time()); d.run(1)
    ok("reacts to fast typing", said_one("cheer", "Go go go.", "Look at you go.", "Fast fingers."), f"say {pet.saying}")
    d.settle(6); pet.keys.undo_times = [time.time()] * 3; pet.last_oops = 0; pet.reactions(time.time()); d.run(0.3)
    ok("reacts to undo x3", said_one("oops", "Oops.", "Undo, undo, undo.", "That bad?"), f"say {pet.saying}")
    pet.st["reacts"] = False

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

    # the hat maker, the closet, the shop, pick five, codes, notebook and remind dialogs open and close
    hat = HM.save_hat(P.hats_dir(), HM.from_code("PH1-cap-1E1B24-F4F1EA-star-F5C242-Night Star"))
    pet.st["wearing"]["hat"] = "my:" + hat["id"]; pet.frames.forget_custom(); pet.show(*pet.last_frame); d.run(0.5)
    ok("wears a hat from the hat maker", not d.errors)
    for name, fn in (("closet", pet.closet_dialog), ("hat maker", pet.hat_maker), ("shop", pet.shop_dialog), ("pick five", pet.pick_dialog),
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
    for page in ("tricks", "together", "play", "attitude", "pets", "home"):
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
        random.seed(1); pet.on_leave(None); d.run(0.5)
        leave_ok = (pet.state == "routine") if pet.sp.get("signature") in ("faint", "sideeye") else (pet.state != "routine")
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
    env = dict(os.environ)
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
    cmd("ears", "trick", id="moonwalk")
    ok("trick by command", wait_for(lambda: states()["ears"] == "routine", 5))
    all_idle()
    for p_ in ("antenna", "ears", "leaf"): cmd(p_, "note", text="We moved to Toronto")
    ok("stage: tell everyone reaches every pet", wait_for(lambda: all((presence(p_) or {}).get("say") for p_ in ("antenna", "ears", "leaf")), 8), f"{[(presence(p_) or {}).get('say') for p_ in ('antenna', 'ears', 'leaf')]}")
    cmd("leaf", "party")
    ok("party spreads to the household", wait_for(lambda: all((presence(p) or {}).get("wearing", {}).get("hat") == "party" for p in ("antenna", "ears", "leaf")), 25), f"{[(presence(p) or {}).get('wearing') for p in ('antenna', 'ears', 'leaf')]}")

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
print("CHECK open house: a click on a room opens that room, house stays open =", hs.open and getattr(hs, "room_win", None) is not None and hs.room_win.title() == "Kitchen")
x0 = w.winfo_x(); hs.on_open_press(ev); ev2 = Ev(); ev2.x, ev2.y, ev2.x_root, ev2.y_root = cx - 100, cy, ev.x_root - 100, ev.y_root
hs.on_open_drag(ev2); hs.on_open_release(ev2); hs.root.update(); time.sleep(0.2); hs.root.update()
print("CHECK open house: a drag moves it =", w.winfo_x() - x0 <= -90 and hs.open)
hs.toggle_open(); print("CHECK open house: the menu closes it =", not hs.open and hs.open_win is None)
hs.root.destroy()
# --house-check--
