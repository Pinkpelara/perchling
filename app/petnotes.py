"""What the owner tells the pet, and how the pet brings it back up.

Notes are plain sentences the owner types. The pet keeps them and, now and then, says something
about one: a straight "You told me: ..." or, when a note has a shape it knows (a pet's name, a like,
a feeling, a plan), a more pointed line. All of it is small pattern matching on this computer.
"""
import random, re
from datetime import datetime, date

PEOPLE = r"(dog|cat|puppy|kitten|bunny|hamster|sister|brother|mom|mum|dad|mother|father|grandma|grandpa|friend|best friend|wife|husband|son|daughter|partner|boyfriend|girlfriend|boss|teacher|roommate|cousin|aunt|uncle)"
FEELINGS = r"(tired|exhausted|stressed|sad|happy|sick|nervous|excited|bored|anxious|angry|lonely|busy|worried|proud|hungry|sleepy|scared|fine|great|okay)"
EVENTS = r"\b(exam|test|interview|meeting|trip|game|match|party|wedding|appointment|presentation|recital|deadline|flight|concert|date|dentist|doctor)\b"

RULES = [
    # my dog Max / my sister is called Amy / my friend named Sam
    (re.compile(r"\b(?i:my " + PEOPLE + r"(?:'s name is| is called| is named| named| called| is)?) ([A-Z][a-z]+)\b"),
     lambda m, age: random.choice([f"How's {m.group(2)}?", f"Say hi to {m.group(2)} for me.", f"Is {m.group(2)} around today?"])),
    # I like / I love
    (re.compile(r"\bi (?:really |just )?(?:like|love|enjoy)\s+([^.,!?;]{2,40}?)(?=\s+(?:and|but|because|so)\b|[.,!?;]|$)", re.I),
     lambda m, age: random.choice([f"{m.group(1).strip().capitalize()} again today?", f"Still into {m.group(1).strip()}?", f"I thought about {m.group(1).strip()}."])),
    # I hate / I don't like
    (re.compile(r"\bi (?:hate|can't stand|don't like|dislike)\s+([^.,!?;]{2,40}?)(?=\s+(?:and|but|because|so)\b|[.,!?;]|$)", re.I),
     lambda m, age: random.choice([f"No {m.group(1).strip()} today, I hope.", f"Still not a fan of {m.group(1).strip()}?"])),
    # my favorite food is pizza
    (re.compile(r"\bmy (?:favorite|favourite) (\w+) (?:is|are) ([^.,!?;]{2,40}?)(?=\s+(?:and|but|because|so)\b|[.,!?;]|$)", re.I),
     lambda m, age: random.choice([f"{m.group(2).strip().capitalize()}: still your favorite {m.group(1)}?", f"I remembered your favorite {m.group(1)}. {m.group(2).strip().capitalize()}."])),
    # I'm tired / I feel stressed / I was sad
    (re.compile(r"\bi(?:'m| am| feel| felt| was| have been| get)\s+(?:so |very |really |a bit |a little )?" + FEELINGS + r"\b", re.I),
     lambda m, age: (random.choice([f"Still {m.group(1).lower()}?", f"You said you were {m.group(1).lower()}. Same today?"]) if m.group(1).lower() in ("happy", "excited", "proud", "great", "fine", "okay")
                     else random.choice([f"You said you were {m.group(1).lower()}. Better today?", f"Less {m.group(1).lower()} today, I hope.", "I'm here, by the way."]))),
    # exam / interview / trip
    (re.compile(EVENTS, re.I),
     lambda m, age: (f"How did the {m.group(1).lower()} go?" if age >= 2 else random.choice([f"Ready for the {m.group(1).lower()}?", f"The {m.group(1).lower()} is coming up, right?"]))),
    # you're shy / you are brave  (about the pet)
    (re.compile(r"\byou(?:'re| are)\s+(?:a bit |a little |kind of |pretty |a |so |very |really )*(\w{3,})\b", re.I),
     lambda m, age: random.choice([f"You said I'm {m.group(1).lower()}. Working on it.", f"Am I still {m.group(1).lower()}?", f"{m.group(1).capitalize()}. That's me."])),
    # I'm going to / I want to / I'm learning
    (re.compile(r"\bi(?:'m| am) ((?:going to|learning(?: to)?|trying to|starting to|planning to)\s+[^.,!?;]{2,40})", re.I),
     lambda m, age: random.choice([f"You're {m.group(1).strip()}, right? How's it going?", f"Still {m.group(1).strip()}?"])),
]


def age_days(note):
    try:
        return (date.today() - datetime.fromisoformat(note["when"]).date()).days
    except (KeyError, ValueError):
        return 0


def reaction(text):
    """What the pet says the moment a note is saved."""
    t = text.lower()
    if re.search(r"\b(tired|stressed|sad|sick|nervous|anxious|lonely|worried|scared)\b", t):
        return random.choice(["I'm here.", "Okay. I'll remember.", "That's a lot. I'm right here."])
    if re.search(r"\b(like|love|favorite|favourite)\b", t):
        return random.choice(["Me too.", "Noted.", "Good taste."])
    if re.search(r"\bmy " + PEOPLE, t):
        return random.choice(["I'd like to meet them.", "Got it.", "I'll remember them."])
    if re.search(r"\byou(?:'re| are)\b", t):
        return random.choice(["If you say so.", "Okay.", "I'll take it."])
    return random.choice(["Got it.", "I'll remember.", "Okay.", "Thanks for telling me."])


def recall(notes):
    """One line about one of the notes, newer ones a little more likely. None if there are no notes."""
    if not notes:
        return None
    weights = [1.0 + 2.0 / (1 + age_days(n)) for n in notes]
    note = random.choices(notes, weights=weights)[0]
    age = age_days(note)
    text = note.get("text", "").strip()
    for rx, make in RULES:
        m = rx.search(text)
        if m:
            try:
                return make(m, age)
            except (IndexError, AttributeError):
                pass
    short = text if len(text) <= 70 else text[:67].rstrip() + "..."
    when = "today" if age == 0 else ("yesterday" if age == 1 else (f"{age} days ago" if age < 14 else "a while ago"))
    return random.choice([f"You told me {when}: {short}", f"I remember: {short}", f"Still true? {short}"])


def gossip_bits(notes):
    """A line or two another pet could pass on. Names and likes only, nothing about feelings."""
    out = []
    for n in notes[-12:]:
        t = n.get("text", "")
        m = re.search(r"\b(?i:my " + PEOPLE + r"(?:'s name is| is called| is named| named| called| is)?) ([A-Z][a-z]+)\b", t)
        if m:
            out.append(f"Their {m.group(1)} is called {m.group(2)}.")
        m = re.search(r"\bi (?:really |just )?(?:like|love|enjoy)\s+([^.,!?;]{2,40}?)(?=\s+(?:and|but|because|so)\b|[.,!?;]|$)", t, re.I)
        if m:
            out.append(f"They like {m.group(1).strip()}. Don't ask me why.")
    return out[-3:]


# ------------------------------------------------------------------ who the owner is
class Owner:
    """How the pets refer to the owner. Name and pronouns come from the notebook; the default is "they"."""
    def __init__(self, name=None, pronoun="they"):
        self.name = name
        self.pronoun = pronoun if pronoun in ("she", "he", "they") else "they"

    @property
    def subj(self):  return self.name or {"she": "she", "he": "he", "they": "they"}[self.pronoun]
    @property
    def Subj(self):  return self.name or {"she": "She", "he": "He", "they": "They"}[self.pronoun]
    @property
    def obj(self):   return self.name or {"she": "her", "he": "him", "they": "them"}[self.pronoun]
    @property
    def poss(self):  return (self.name + "'s") if self.name else {"she": "her", "he": "his", "they": "their"}[self.pronoun]
    @property
    def Poss(self):  return (self.name + "'s") if self.name else {"she": "Her", "he": "His", "they": "Their"}[self.pronoun]
    @property
    def plural(self):  return self.pronoun == "they" and not self.name

    def v(self, singular, plural):
        """Pick the verb form: "shows up" for a named person, she or he; "show up" for they."""
        return plural if self.plural else singular

    def call(self, line):
        """Add the name to a line said to the owner, when known: "Right on time." -> "Right on time, Polin." """
        if not self.name:
            return line
        return line[:-1] + f", {self.name}" + line[-1] if line and line[-1] in ".?!" else f"{line}, {self.name}"


def owner_from_notes(notes):
    """Name and pronouns the owner wrote down, if any."""
    name, pronoun = None, None
    for note in notes:
        text = note.get("text", "")
        m = re.search(r"\b(?i:my name(?:'s| is)|call me|i(?:'m| am)) ([A-Z][a-z]{1,20})\b", text)
        if m and m.group(1).lower() not in ("not", "so", "very", "just", "also", "still", "here", "back", "home", "fine", "okay", "good", "tired", "happy", "sad", "sorry"):
            name = m.group(1)
        low = text.lower()
        if re.search(r"\b(she/her|i(?:'m| am) a (?:woman|girl|lady|mom|mum|mother|wife|sister|grandma|aunt|daughter))\b", low):
            pronoun = "she"
        elif re.search(r"\b(he/him|i(?:'m| am) a (?:man|boy|guy|dad|father|husband|brother|grandpa|uncle|son))\b", low):
            pronoun = "he"
        elif re.search(r"\b(they/them|non-?binary)\b", low):
            pronoun = "they"
    return name, pronoun


N_PRON = {"she": {"subj": "she", "poss": "her"}, "he": {"subj": "he", "poss": "his"}}


def an(word):
    return ("an " if word[:1] in "aeiou" else "a ") + word


def gossip_facts(notes, st, other, owner):
    """What this pet could say about the owner to another pet, all of it from things it knows. Feelings stay private."""
    import statistics
    from datetime import datetime
    import time as _t
    o = owner
    lines = []
    now = datetime.now()
    log = st.get("logins", {}).get(str(now.weekday()), [])
    if len(log) >= 2:
        mins = sorted(int(x[:2]) * 60 + int(x[3:]) for x in log); m = int(statistics.median(mins))
        lines.append(f"{o.Subj} usually {o.v('shows', 'show')} up at {m // 60}:{m % 60:02d}.")
    last = st.get("last_touch")
    if last:
        h = (_t.time() - last) / 3600
        lines.append(f"{o.Subj} {o.v('hasn\'t', 'haven\'t')} touched me in {int(h)} hour{'s' if h >= 2 else ''}." if h >= 1 else f"{o.Subj} played with me just now.")
    if st.get("birthday"):
        lines.append(f"{o.Poss} birthday is on {st['birthday'].replace('-', '/')}. Don't forget.")
    try:
        days = (now.date() - datetime.fromisoformat(st.get("adopted", now.date().isoformat())).date()).days
        lines.append(f"{o.Subj} {o.v('adopted', 'adopted')} me " + ("today." if days == 0 else f"{days} day{'s' if days != 1 else ''} ago."))
    except ValueError:
        pass
    picks = st.get("picks", [])
    if picks:
        from household import rnd_name
        lines.append(f"{o.Subj} picked {rnd_name(picks)} for me.")
    for r in st.get("reminders", [])[:2]:
        lines.append(f"{o.Subj} {o.v('has', 'have')} something on {r['when'][5:10].replace('-', '/')}. I'm not supposed to say.")
    hat = (other or {}).get("wearing", {}).get("hat")
    if hat:
        lines.append(f"Nice hat, by the way. Did {o.subj} pick it?")
    if (st.get("wearing") or {}).get("hat"):
        lines.append(f"{o.Subj} put this hat on me. I didn't ask.")
    if st.get("attention", 70) < 40:
        lines.append(f"I'm a little bored, honestly. {o.Subj} {o.v('has', 'have')} been busy.")
    # from the notebook
    for note in notes[-40:]:
        text = note.get("text", "")
        m = re.search(r"\b(?i:my " + PEOPLE + r"(?:'s name is| is called| is named| named| called| is)?) ([A-Z][a-z]+)\b", text)
        if m: lines.append(f"{o.Poss} {m.group(1).lower()} is called {m.group(2)}.")
        m = re.search(r"\bi (?:really |just )?(?:like|love|enjoy)\s+([^.,!?;]{2,40}?)(?=\s+(?:and|but|because|so)\b|[.,!?;]|$)", text, re.I)
        if m: lines.append(f"{o.Subj} {o.v('likes', 'like')} {m.group(1).strip()}.")
        m = re.search(r"\bi (?:hate|can't stand|don't like|dislike)\s+([^.,!?;]{2,40}?)(?=\s+(?:and|but|because|so)\b|[.,!?;]|$)", text, re.I)
        if m: lines.append(f"{o.Subj} can't stand {m.group(1).strip()}.")
        m = re.search(r"\bmy (?:favorite|favourite) (\w+) (?:is|are) ([^.,!?;]{2,40}?)(?=\s+(?:and|but|because|so)\b|[.,!?;]|$)", text, re.I)
        if m: lines.append(f"{o.Poss} favorite {m.group(1)} is {m.group(2).strip()}.")
        m = re.search(EVENTS, text, re.I)
        if m: lines.append(f"{o.Subj} {o.v('has', 'have')} {an(m.group(1).lower())} coming up." if age_days(note) < 2 else f"{o.Subj} had {an(m.group(1).lower())} the other day.")
        m = re.search(r"\byou(?:'re| are)\s+(?:a bit |a little |kind of |pretty |a |so |very |really )*(\w{3,})\b", text, re.I)
        if m: lines.append(f"{o.Subj} {o.v('says', 'say')} I'm {m.group(1).lower()}.")
        m = re.search(r"\bi(?:'m| am) ((?:going to|learning(?: to)?|trying to|starting to|planning to)\s+[^.,!?;]{2,40})", text, re.I)
        if m: lines.append(f"{o.Subj} {o.v('is', 'are')} {m.group(1).strip()}.")
    # no repeats; and with a name known, every other line uses the pronoun so it doesn't sound like a roll call
    seen, out = set(), []
    for l in lines:
        if l not in seen:
            seen.add(l); out.append(l)
    if o.name and o.pronoun in ("she", "he"):
        pr = N_PRON[o.pronoun]
        out = [l if i % 2 == 0 else l.replace(o.name + "'s", pr["poss"]).replace(o.name, pr["subj"]).replace(f"Did {pr['subj']}", f"Did {pr['subj']}") for i, l in enumerate(out)]
        out = [l[0].upper() + l[1:] if l else l for l in out]
    if len(out) < 3:
        out += ["Psst.", "Hehe.", "Don't tell them I said that."][: 3 - len(out)]
    return out
