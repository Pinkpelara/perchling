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

# "my sister is called amy" in any case; "my dog Max" only with a capital, since that is what says it is a name
PERSON_RX = re.compile(r"\bmy " + PEOPLE + r"(?:'s name is|’s name is| is called| is named| named| called) ([A-Za-z][a-z]{1,20})\b", re.I)
PERSON_CAP_RX = re.compile(r"\b(?i:my " + PEOPLE + r")(?: is)? ([A-Z][a-z]{1,20})\b")


def _cap(s):
    return s[:1].upper() + s[1:]


def person_named(text):
    """(relation, Name) from a note like "my cat is called pumpkin", or None."""
    m = PERSON_RX.search(text) or PERSON_CAP_RX.search(text)
    if not m or m.group(2).lower() in NOT_NAMES:
        return None
    return m.group(1).lower(), _cap(m.group(2))


RULES = [
    # my dog Max / my sister is called amy / my friend named Sam
    (PERSON_RX, lambda m, age: random.choice([f"How's {_cap(m.group(2))}?", f"Say hi to {_cap(m.group(2))} for me.", f"Is {_cap(m.group(2))} around today?"])),
    (PERSON_CAP_RX, lambda m, age: random.choice([f"How's {m.group(2)}?", f"Say hi to {m.group(2)} for me.", f"Is {m.group(2)} around today?"])),
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
    (re.compile(r"\bi(?:'m|’m|m| am| feel| felt| was| have been| get)\s+(?:so |very |really |a bit |a little )?" + FEELINGS + r"\b", re.I),
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
    # I live in Toronto / I'm from Vancouver
    (re.compile(r"\bi (?:live in|'m from|am from|moved to)\s+([A-Z][\w' -]{1,30}?)(?=[.,!?;]|$)", re.I),
     lambda m, age: random.choice([f"How's {m.group(1).strip()} today?", f"{m.group(1).strip()}. I'd like to see it."])),
    # I work at a cafe / I work for the city
    (re.compile(r"\bi work (?:at|for|in)\s+([^.,!?;]{2,40}?)(?=\s+(?:and|but|because|so)\b|[.,!?;]|$)", re.I),
     lambda m, age: random.choice([f"How's {m.group(1).strip()}?", f"Busy day at {m.group(1).strip()}?"])),
    # I want a puppy / I want to sleep
    (re.compile(r"\bi (?:want|wish i had|need)\s+([^.,!?;]{2,40}?)(?=\s+(?:and|but|because|so)\b|[.,!?;]|$)", re.I),
     lambda m, age: random.choice([f"Did you get {m.group(1).strip()} yet?", f"Still want {m.group(1).strip()}?"])),
    # my car is red / my room is a mess (anything that isn't a person)
    (re.compile(r"\bmy (\w{3,})(?: is| was| are)\s+([^.,!?;]{2,40}?)(?=\s+(?:and|but|because|so)\b|[.,!?;]|$)", re.I),
     lambda m, age: random.choice([f"Your {m.group(1).lower()}. {m.group(2).strip().capitalize()}. I remember.", f"Is your {m.group(1).lower()} still {m.group(2).strip()}?"])),
]


def matched(text):
    """True if any rule knows what to do with this note."""
    return any(rx.search(text) for rx, _ in RULES)


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
    @property
    def pro(self):   return self.pronoun                     # the pronoun even when the name is known: "Polin said she was tired"

    def pv(self, singular, plural):
        """The verb after the pronoun: "Polin said they were tired" needs the plural even with a name."""
        return plural if self.pronoun == "they" else singular

    def v(self, singular, plural):
        """Pick the verb form: "shows up" for a named person, she or he; "show up" for they."""
        return plural if self.plural else singular

    def call(self, line):
        """Add the name to a line said to the owner, when known: "Right on time." -> "Right on time, Polin." """
        if not self.name:
            return line
        return line[:-1] + f", {self.name}" + line[-1] if line and line[-1] in ".?!" else f"{line}, {self.name}"


NOT_NAMES = {"not", "so", "very", "just", "also", "still", "here", "back", "home", "fine", "okay", "good", "tired", "happy", "sad", "sorry", "a", "an", "the",
             "she", "he", "they", "woman", "girl", "man", "boy", "female", "male", "your", "their", "his", "her", "polite", "busy", "bored", "done", "new"}
IM = r"i(?:'m|’m|m| am)"          # I'm, I’m, im, I am (people type all of them)


NAME_STOP = NOT_NAMES | set(FEELINGS.strip("()").split("|")) | {   # words that follow "I'm" or "call me" and are never a name
    "at", "in", "on", "from", "going", "gonna", "about", "like", "all", "ready", "there", "out", "off", "always", "never", "really",
    "late", "early", "free", "old", "ok", "well", "bad", "cold", "hot", "home", "sure", "right", "glad", "grateful", "thankful", "single",
    "married", "pregnant", "canadian", "american", "mexican", "british", "english", "french", "german", "chinese", "indian", "korean",
    "japanese", "irish", "italian", "spanish", "persian", "iranian", "filipino", "vietnamese", "australian", "christian", "muslim",
    "jewish", "catholic", "vegan", "vegetarian", "when", "later", "tonight", "tomorrow", "today", "maybe", "if", "after", "before",
    "now", "soon", "please", "again", "back"}


def owner_from_notes(notes):
    """Name and pronouns the owner wrote down, if any. "my name is polin" is a name in any case; "call me Sam" and
    "I'm Sam" only with the capital a name is written with, and never a word like Tired, Going or Canadian. A name
    spelled out ("my name is", "call me") beats one read off "I'm", and the newest note wins. Until 0.29.6 any word after
    "I'm" was taken, so "I'm stressed" renamed the owner Stressed for every pet, and beat "My name is Polin" too."""
    named, guessed, pronoun = None, None, None
    for note in notes:
        text = note.get("text", "")
        for m in re.finditer(r"\bmy name(?:'s|’s| is)\s+([A-Za-z][a-z]{1,20})\b", text, re.I):
            if m.group(1).lower() not in NAME_STOP:
                named = m.group(1).capitalize()
        for m in re.finditer(r"\b(?i:call me)\s+([A-Z][a-z]{1,20})\b", text):
            if m.group(1).lower() not in NAME_STOP:
                named = m.group(1)
        for m in re.finditer(r"\b(?i:i(?:'m|’m|m| am))\s+([A-Z][a-z]{1,20})\b", text):
            w = m.group(1).lower()
            if w not in NAME_STOP and not w.endswith("ing"):
                guessed = m.group(1)
        low = text.lower().replace("’", "'")
        if re.search(r"\b(she/her|(?:" + IM + r") (?:a )?(?:she|woman|girl|lady|female|mom|mum|mother|wife|sister|grandma|aunt|daughter))\b", low):
            pronoun = "she"
        elif re.search(r"\b(he/him|(?:" + IM + r") (?:a )?(?:he|man|boy|guy|male|dad|father|husband|brother|grandpa|uncle|son))\b", low):
            pronoun = "he"
        elif re.search(r"\b(they/them|non-?binary|(?:" + IM + r") (?:a )?they)\b", low):
            pronoun = "they"
    return named or guessed, pronoun


def an(word):
    return ("an " if word[:1] in "aeiou" else "a ") + word
