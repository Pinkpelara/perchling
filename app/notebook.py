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
    (re.compile(r"\bi (?:really |just )?(?:like|love|enjoy)\s+([^.,!?;]{2,40})", re.I),
     lambda m, age: random.choice([f"{m.group(1).strip().capitalize()} again today?", f"Still into {m.group(1).strip()}?", f"I thought about {m.group(1).strip()}."])),
    # I hate / I don't like
    (re.compile(r"\bi (?:hate|can't stand|don't like|dislike)\s+([^.,!?;]{2,40})", re.I),
     lambda m, age: random.choice([f"No {m.group(1).strip()} today, I hope.", f"Still not a fan of {m.group(1).strip()}?"])),
    # my favorite food is pizza
    (re.compile(r"\bmy (?:favorite|favourite) (\w+) (?:is|are) ([^.,!?;]{2,40})", re.I),
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
        m = re.search(r"\bi (?:really |just )?(?:like|love|enjoy)\s+([^.,!?;]{2,40})", t, re.I)
        if m:
            out.append(f"They like {m.group(1).strip()}. Don't ask me why.")
    return out[-3:]
