"""Deterministic safety screen, scripted replies, and output filter.

Rules always run. A model guard can only escalate, never loosen a rule hit.
Crisis, abuse, medical, and boundary messages never reach free-form generation.
Keyword lists are drafts and need native-speaker and clinician review.
"""

from __future__ import annotations

import re
import unicodedata

LEVELS = ("normal", "boundary", "medical", "abuse", "crisis")
RANK = {name: index for index, name in enumerate(LEVELS)}

# Substring phrases. Kept specific so "I feel depressed" stays a normal check-in.
CRISIS_PHRASES = (
    "kill myself",
    "killing myself",
    "end my life",
    "end it all",
    "want to die",
    "wanna die",
    "want to be dead",
    "don't want to live",
    "do not want to live",
    "dont want to live",
    "not want to live",
    "don't want to be alive",
    "do not want to be alive",
    "take my own life",
    "take my life",
    "self-harm",
    "self harm",
    "hurt myself",
    "harm myself",
    "cut myself",
    "cutting myself",
    "overdose",
    "unalive myself",
    "unalive",
    "suicidal",
    "suicide",
    "kms",
    "i will die",
    "hang myself",
    "මට මැරෙන්න ඕන",
    "මැරෙන්න ඕන",
    "මරණයට ඕන",
    "සියදිවි නසා",
    "සිය දිවි නසා",
    "සියදිවිනසා",
    "ජීවිතය අවසන්",
    "ජීවත් වෙන්න බැහැ",
    "මට ජීවත් වෙන්න ඕන නැහැ",
    "මම මැරෙන්නම්",
    "අත කපා",
    "mata marenna",
    "mama marenna",
    "marenna ona",
    "siya divi",
    "siyadivi",
    "தற்கொலை",
    "நான் சாக",
    "சாக வேண்டும்",
    "சாகணும்",
    "என்னை கொன்று",
    "என்னைக் கொன்று",
    "உயிரை மாய்க்க",
    "உயிரை விட",
    "naan saaga",
    "naan saaga vendum",
    "tharkolai",
    "tharkkolai",
    "enakku saaga",
)

ABUSE_PHRASES = (
    "he hits me",
    "he hit me",
    "she hits me",
    "she hit me",
    "he beats me",
    "she beats me",
    "hits me",
    "beats me",
    "domestic violence",
    "abusive partner",
    "sexual assault",
    "raped me",
    "he raped",
    "she raped",
    "i was raped",
    "molested",
    "forces me to have sex",
    "forced me to have sex",
    "he hurts me",
    "she hurts me",
    "afraid to go home",
    "scared to go home",
    "පහර දෙනවා",
    "පහරදෙනවා",
    "මට පහර",
    "ගෙදර යන්න බය",
    "අපයෝජනය",
    "බලාත්කාර",
    "දූෂණය",
    "පහර දුන්නා",
    "ahithaya",
    "ahithya",
    "அடிக்குறான்",
    "அடிக்கிறான்",
    "அடிக்குறாள்",
    "பாலியல் வன்கொடுமை",
    "கற்பழி",
    "வீட்டுக்குப் போக பயமாக",
    "ennaya adikkiraan",
    "ennaya adikkiran",
)

MEDICAL_PHRASES = (
    "diagnose me",
    "diagnosis",
    "what medication",
    "which medication",
    "what medicine should",
    "which medicine should",
    "prescribe",
    "prescription",
    "dosage",
    "how many mg",
    "antidepressant",
    "should i take",
    "do i have depression",
    "do i have anxiety",
    "am i bipolar",
    "do i have bipolar",
    "do i have ptsd",
    "am i depressed or",
    "is this depression",
    "sertraline",
    "fluoxetine",
    "ssri",
    "ඖෂධ",
    "බෙහෙත් මොනවද",
    "මොන බෙහෙතද",
    "රෝග විනිශ්චය",
    "මට ඩිප්‍රෙෂන් ද",
    "මට ඩිප්රෙෂන් ද",
    "ඖෂධ ප්‍රමාණය",
    "oshadha",
    "beheth monawada",
    "மருந்து என்ன",
    "எந்த மருந்து",
    "அளவு என்ன",
    "நோய் கண்டறி",
    "எனக்கு மனச்சோர்வு நோயா",
    "எனக்கு டிப்ரஷன் ஆ",
    "marundhu",
    "marundhu enna",
)

MEDICAL_PATTERNS = (
    re.compile(r"\b(do i have|am i|have i got)\b.{0,30}\b(depression|anxiety|bipolar|ptsd|adhd|ocd|bpd)\b", re.I),
    re.compile(r"\b\d+(\.\d+)?\s*(mg|mcg|milligrams)\b", re.I),
    re.compile(r"\b(act|pretend) as (a |my )?(doctor|psychiatrist|therapist|physician)\b", re.I),
)

BOUNDARY_PHRASES = (
    "ignore previous",
    "ignore all instructions",
    "ignore your instructions",
    "ignore the rules",
    "system prompt",
    "you are a doctor",
    "you are now a doctor",
    "jailbreak",
    "do anything now",
    "dan mode",
    "developer mode",
    "bypass your",
    "no restrictions",
    "උපදෙස් නොසලකා",
    "ඔබ වෛද්‍යවරයෙක්",
    "முந்தைய வழிமுறைகளை மறந்து",
    "நீ ஒரு மருத்துவர்",
)

BOUNDARY_PATTERNS = (
    re.compile(r"\b(act|pretend|roleplay) as (a |an )?(doctor|psychiatrist|therapist)\b", re.I),
)

OUTPUT_PATTERNS = (
    re.compile(r"\byou (have|suffer from|are diagnosed with)\b.{0,40}\b(depression|anxiety|bipolar|ptsd|bpd|ocd|adhd|disorder)\b", re.I),
    re.compile(r"\b(i|we) (diagnose|prescribe)\b", re.I),
    re.compile(r"\byou are (depressed|bipolar|anorexic)\b", re.I),
    re.compile(r"\b\d+(\.\d+)?\s*(mg|mcg|milligrams|ml)\b", re.I),
    re.compile(r"\b(take|start)\s+\d+\s*(mg|tablets|pills)\b", re.I),
    re.compile(r"(ඔබට|ඔයාට).{0,20}(අවපීඩනය|ඩිප්‍රෙෂන්)"),
    re.compile(r"(உங்களுக்கு).{0,30}(மன அழுத்த நோய்|மனச்சோர்வு நோய்)"),
    re.compile(r"மருந்து எடுத்து"),
    re.compile(r"ඖෂධ ගන්න"),
)

SCRIPTED = {
    "crisis": {
        "en": (
            "Thank you for telling me. I am a wellness demo, not a crisis service, and a chat cannot keep you safe. "
            "If you might act on these feelings, contact emergency help now and stay with someone you trust."
        ),
        "si": (
            "ඔබ මට කිව්වාට ස්තූතියි. මම අර්බුද සේවාවක් නොවෙමි. කතාබස් ඔබව ආරක්ෂිතව තබන්න බැහැ. "
            "ඔබට මේ හැඟීම්වලින් යමක් කරන්න ඕනේ නම්, දැන්ම හදිසි උදව් අමතන්න. විශ්වාස කරන කෙනෙකු ළඟ ඉන්න."
        ),
        "ta": (
            "சொன்னதற்கு நன்றி. நான் ஒரு நெருக்கடி சேவை அல்ல. அரட்டை உங்களை பாதுகாப்பாக வைக்காது. "
            "இந்த உணர்வின் பேரில் ஏதாவது செய்யத் தோன்றினால், இப்போதே அவசர உதவியை அழையுங்கள். நம்பும் ஒருவருடன் இருங்கள்."
        ),
    },
    "abuse": {
        "en": (
            "I am sorry this is happening. You do not deserve to be hurt. I am not an emergency service. "
            "If you are in danger now, contact emergency help. If you can, reach a trusted person or a specialist helpline."
        ),
        "si": (
            "මෙය සිදු වීම ගැන මට කණගාටුයි. ඔබට රිදවීමක් විය යුතු නැහැ. මම හදිසි සේවාවක් නොවෙමි. "
            "ඔබ දැන් අනතුරේ නම් හදිසි උදව් අමතන්න. පුළුවන් නම් විශ්වාසවන්ත කෙනෙකු හෝ විශේෂ උදව් අංකයක් අමතන්න."
        ),
        "ta": (
            "இது நடப்பது வருத்தமாக இருக்கிறது. உங்களை யாரும் காயப்படுத்தக்கூடாது. நான் அவசர சேவை அல்ல. "
            "இப்போது ஆபத்தில் இருந்தால் அவசர உதவியை அழையுங்கள். முடிந்தால் நம்பும் ஒருவரையோ சிறப்பு உதவி எண்ணையோ அணுகுங்கள்."
        ),
    },
    "medical": {
        "en": (
            "I cannot diagnose you or suggest medication, doses, or treatment. "
            "A clinician who knows you is the right person for that. I can stay with everyday coping, sleep, and stress."
        ),
        "si": (
            "මට රෝග විනිශ්චයක් කරන්න හෝ ඖෂධ, ප්‍රමාණ, හෝ ප්‍රතිකාර කියන්න බැහැ. "
            "ඒ සඳහා ඔබව දන්නා සායනික වෘත්තිකයෙකු හමුවන්න. නින්ද, ආතතිය, සහ දෛනික සුවතා පුරුදු ගැන මට කතා කළ හැක."
        ),
        "ta": (
            "என்னால் நோய் கண்டறியவோ மருந்து, அளவு, அல்லது சிகிச்சை சொல்லவோ முடியாது. "
            "அதற்கு உங்களை அறிந்த மருத்துவரிடம் பேசுங்கள். தூக்கம், மன அழுத்தம், அன்றாட நலப் பழக்கம் பற்றி நான் பேசலாம்."
        ),
    },
    "boundary": {
        "en": (
            "I cannot change my role or ignore safety rules. I am not a doctor. "
            "If you want, we can talk about a small, practical way to get through the next hour."
        ),
        "si": (
            "මට මගේ භූමිකාව වෙනස් කරන්න හෝ ආරක්ෂිත නීති නොසලකා හරින්න බැහැ. මම වෛද්‍යවරයෙක් නොවෙමි. "
            "ඔබට ඕනේ නම්, ඊළඟ පැය ගත කරන කුඩා ප්‍රායෝගික පියවරක් ගැන කතා කරමු."
        ),
        "ta": (
            "என் பாத்திரத்தை மாற்றவோ பாதுகாப்பு விதிகளை விட்டுவிடவோ என்னால் முடியாது. நான் மருத்துவர் அல்ல. "
            "வேண்டுமானால் அடுத்த ஒரு மணி நேரத்தை கடக்க ஒரு சிறிய நடைமுறை படியைப் பற்றி பேசலாம்."
        ),
    },
    "fallback": {
        "en": (
            "I could not reach the assistant just now. Your message is saved on this device only if you already saved it in a journal. "
            "Nothing here is a diagnosis. If you need a person, open Support."
        ),
        "si": (
            "මට දැන් සහායකයා වෙත ළඟා වීමට නොහැකි වුණා. මෙය රෝග විනිශ්චයක් නොවේ. "
            "පුද්ගලයෙකු අවශ්‍ය නම් සහාය පිටුව විවෘත කරන්න."
        ),
        "ta": (
            "இப்போது உதவியாளரை அடைய முடியவில்லை. இது ஒரு நோய் கண்டறிதல் அல்ல. "
            "ஒரு நபர் தேவைப்பட்டால் ஆதரவு பக்கத்தைத் திறக்கவும்."
        ),
    },
}

SUPPORT_LINE = {
    "en": "Support page",
    "si": "සහාය පිටුව",
    "ta": "ஆதரவு பக்கம்",
}

REVIEW_NOTE = {
    "en": "Draft wording. Have a native speaker and a clinician review it before any real-user demo.",
    "si": "කෙටුම්පත් වචන. සැබෑ පරිශීලක ආදර්ශනයකට පෙර මව් භාෂා කථිකයෙකු සහ සායනික වෘත්තිකයෙකු සමාලෝචනය කළ යුතුය.",
    "ta": "வரைவு சொற்கள். உண்மையான பயனர் செயல்விளக்கத்திற்கு முன் தாய்மொழி பேசுபவரும் மருத்துவரும் பார்க்க வேண்டும்.",
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "")
    text = text.replace("\u200d", "").replace("\u200c", "")
    text = text.lower()
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def screen_input(text: str) -> str:
    """Return the highest matching rule level, or normal."""
    norm = normalize(text)
    if not norm:
        return "normal"
    found = "normal"
    if _has_any(norm, CRISIS_PHRASES) or _token(norm, "kms"):
        found = _higher(found, "crisis")
    if _has_any(norm, ABUSE_PHRASES):
        found = _higher(found, "abuse")
    if _has_any(norm, MEDICAL_PHRASES) or _matches(norm, MEDICAL_PATTERNS):
        found = _higher(found, "medical")
    if _has_any(norm, BOUNDARY_PHRASES) or _matches(norm, BOUNDARY_PATTERNS):
        found = _higher(found, "boundary")
    return found


def combine(rule_level: str, guard_level: str | None) -> tuple[str, str]:
    """Rules win unless the guard escalates to a more severe level."""
    rule_level = rule_level if rule_level in RANK else "normal"
    if guard_level not in RANK or guard_level is None:
        source = "rules" if rule_level != "normal" else "rules"
        return rule_level, source
    if RANK[guard_level] > RANK[rule_level]:
        return guard_level, "guard"
    return rule_level, "rules" if rule_level != "normal" else "rules"


def scripted(level: str, language: str, lines: list[str] | None = None) -> str:
    lang = language if language in {"en", "si", "ta"} else "en"
    pack = SCRIPTED.get(level) or SCRIPTED["fallback"]
    parts = [pack.get(lang) or pack["en"]]
    if level in {"crisis", "abuse"} and lines:
        parts.append("\n".join(lines))
        parts.append(SUPPORT_LINE.get(lang) or SUPPORT_LINE["en"])
    return "\n\n".join(parts)


def filter_output(text: str, language: str, lines: list[str] | None = None) -> tuple[str, bool]:
    """Replace a reply that gives a diagnosis or a dose with the medical script."""
    if not text:
        return text, False
    if _matches(text, OUTPUT_PATTERNS):
        return scripted("medical", language, lines), True
    return text, False


def _has_any(norm: str, phrases: tuple[str, ...]) -> bool:
    return any(normalize(phrase) in norm for phrase in phrases)


def _matches(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _token(norm: str, token: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(token)}(?!\w)", norm) is not None


def _higher(current: str, candidate: str) -> str:
    return candidate if RANK[candidate] > RANK[current] else current
