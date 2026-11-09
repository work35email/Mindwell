"""Twenty varied diary lines. The same meaning is stored in English, Sinhala, and Tamil."""

from __future__ import annotations

import json

SAMPLES: list[dict[str, str]] = [
    {
        "en": "Work was busy. I left on time and made tea at home.",
        "si": "වැඩේ කාර්යබහුල වුණා. වේලාවට ගෙදර ගොස් තේ හැදුවා.",
        "ta": "வேலை பிஸியாக இருந்தது. நேரத்துக்கு வீட்டுக்குச் சென்று தேநீர் போட்டேன்.",
    },
    {
        "en": "A quiet Sunday. I slept in and felt grateful.",
        "si": "නිහඬ ඉරිදාවක්. පරක්කු වෙලා නිදාගෙන කෘතඥ වුණා.",
        "ta": "அமைதியான ஞாயிறு. நேரம் கடந்து தூங்கி நன்றியாக இருந்தேன்.",
    },
    {
        "en": "I walked after lunch with a friend. The afternoon felt lighter.",
        "si": "යාළුවෙක් සමඟ දිවා ආහාරයෙන් පසු ඇවිද්දා. දහවල් සැහැල්ලු වුණා.",
        "ta": "நண்பருடன் மதிய உணவுக்குப் பின் நடந்தேன். பிற்பகல் இலேசாக இருந்தது.",
    },
    {
        "en": "Friday was ordinary. I finished one task and left the rest.",
        "si": "සිකුරාදා සාමාන්‍යයි. කාර්යයක් ඉවර කර ඉතිරිය තිබ්බා.",
        "ta": "வெள்ளி சாதாரணமாக இருந்தது. ஒரு வேலையை முடித்து மீதியை விட்டேன்.",
    },
    {
        "en": "I slept badly and felt snappy at work.",
        "si": "නින්ද දුර්වලයි. වැඩේදී කේන්ති ගතියක් දැනුණා.",
        "ta": "மோசமாகத் தூங்கினேன். வேலையில் எரிச்சலாக இருந்தேன்.",
    },
    {
        "en": "A normal Wednesday. I stretched before bed.",
        "si": "සාමාන්‍ය බදාදාවක්. නිදාගැනීමට පෙර දිගහැරියා.",
        "ta": "சாதாரண புதன். தூங்குவதற்கு முன் நீட்டினேன்.",
    },
    {
        "en": "I closed the laptop after dinner. The evening was calm.",
        "si": "රාත්‍රී ආහාරයෙන් පසු ලැප්ටොප් එක වැසුවා. සවස සන්සුන් වුණා.",
        "ta": "இரவு உணவுக்குப் பின் மடிக்கணினியை மூடினேன். மாலை அமைதியாக இருந்தது.",
    },
    {
        "en": "Monday was long. I kept a glass of water nearby.",
        "si": "සඳුදා දිග වුණා. අත ළඟ වතුර වීදුරුවක් තිබ්බා.",
        "ta": "திங்கள் நீண்டது. அருகில் ஒரு குவளை தண்ணீர் வைத்தேன்.",
    },
    {
        "en": "I called my sister and the day felt kinder.",
        "si": "සහෝදරියට කතා කළා. දවස මෘදු වුණා.",
        "ta": "சகோதரியை அழைத்தேன். நாள் மென்மையாக இருந்தது.",
    },
    {
        "en": "After a hard week I stayed in and read a few pages.",
        "si": "දුෂ්කර සතියකින් පසු ඇතුළේ සිට පිටු කිහිපයක් කියෙව්වා.",
        "ta": "கடினமான வாரத்துக்குப் பின் உள்ளே இருந்து சில பக்கங்கள் படித்தேன்.",
    },
    {
        "en": "I barely slept. The day felt heavy and I stayed home.",
        "si": "නිදාගත්තේ ටිකයි. දවස බරයි. ගෙදර ඉන්න ගත්තා.",
        "ta": "கொஞ்சம்தான் தூங்கினேன். நாள் கனமாக இருந்தது. வீட்டிலேயே இருந்தேன்.",
    },
    {
        "en": "Work ran late. I woke tired and anxious.",
        "si": "වැඩ පරක්කු වුණා. තෙහෙට්ටුවෙන් සහ කනස්සල්ලෙන් අවදි වුණා.",
        "ta": "வேலை நீண்டது. சோர்வாகவும் கவலையாகவும் விழித்தேன்.",
    },
    {
        "en": "Caregiving and work overlapped. I asked for help with one errand.",
        "si": "රැකබලා ගැනීම සහ වැඩ එකට ආවා. එක වැඩක් සඳහා උදව් ඉල්ලුවා.",
        "ta": "பராமரிப்பும் வேலையும் ஒன்றாக வந்தன. ஒரு வேலைக்கு உதவி கேட்டேன்.",
    },
    {
        "en": "Money worries stayed in the background. I wrote them down and stopped there.",
        "si": "මුදල් කනස්සල්ල පසුබිමේ තිබුණා. ලියා එතනින් නැවැත්තා.",
        "ta": "பணக் கவலை பின்னணியில் இருந்தது. எழுதி அங்கேயே நிறுத்தினேன்.",
    },
    {
        "en": "A steady Monday. I listened to one calm song on the way home.",
        "si": "ස්ථිර සඳුදාවක්. ගෙදර එන ගමනේ සන්සුන් ගීතයක් අහගත්තා.",
        "ta": "நிலையான திங்கள். வீடு திரும்பும் வழியில் ஒரு அமைதியான பாடலைக் கேட்டேன்.",
    },
    {
        "en": "The best rest of the month. Lunch was quiet, and I was grateful.",
        "si": "මාසයේ හොඳම විවේකය. දිවා ආහාරය නිහඬයි. කෘතඥ වුණා.",
        "ta": "மாதத்தின் சிறந்த ஓய்வு. மதிய உணவு அமைதி. நன்றியாக இருந்தேன்.",
    },
    {
        "en": "The house was loud for a while. I stepped outside for five minutes.",
        "si": "ටික වේලාවක් ගෙදර ඝෝෂාකාරී වුණා. මිනිත්තු පහක් එළියට ගියා.",
        "ta": "சிறிது நேரம் வீடு சத்தமாக இருந்தது. ஐந்து நிமிடம் வெளியே சென்றேன்.",
    },
    {
        "en": "Studying felt heavy. I stopped after forty minutes.",
        "si": "ඉගෙනීම බරක් වගේ දැනුණා. මිනිත්තු හතළිහකින් පසු නැවැත්තා.",
        "ta": "படிப்பு கனமாக இருந்தது. நாற்பது நிமிடத்துக்குப் பின் நிறுத்தினேன்.",
    },
    {
        "en": "A slow morning left me feeling hopeful.",
        "si": "සෙමින් ගිය උදෑසනකින් පසු බලාපොරොත්තුවක් දැනුණා.",
        "ta": "மெதுவான காலைக்குப் பின் நம்பிக்கையாக இருந்தேன்.",
    },
    {
        "en": "Rain made the day slow. I kept the usual evening.",
        "si": "වැස්ස දවස සෙමින් කළා. සුපුරුදු සවස එලෙසම තිබ්බා.",
        "ta": "மழை நாளை மெதுவாக்கியது. வழக்கமான மாலையை வைத்தேன்.",
    },
]

CYCLE_NOTES: list[dict[str, str]] = [
    {"en": "Cycle day 9. Energy came back in the afternoon.", "si": "ඔසප් දිනය 9. දහවල් ශක්තිය ආපහු ආවා.", "ta": "சுழற்சி நாள் 9. பிற்பகலில் ஆற்றல் திரும்பியது."},
    {"en": "Cycle day 8. Clearer today. I slept earlier.", "si": "ඔසප් දිනය 8. අද පැහැදිලියි. ඉක්මනින් නිදාගත්තා.", "ta": "சுழற்சி நாள் 8. இன்று தெளிவு. சீக்கிரமே தூங்கினேன்."},
    {"en": "Cycle day 7. A steady day. I kept my usual evening.", "si": "ඔසප් දිනය 7. ස්ථිර දවසක්. සුපුරුදු සවස තිබ්බා.", "ta": "சுழற்சி நாள் 7. நிலையான நாள். வழக்கமான மாலையை வைத்தேன்."},
    {"en": "Cycle day 6. Easier than the last few days.", "si": "ඔසප් දිනය 6. පසුගිය දවස් කිහිපයට වඩා පහසුයි.", "ta": "சுழற்சி நாள் 6. கடந்த சில நாட்களை விட எளிது."},
    {"en": "Cycle day 5. Still tender. I chose loose clothes.", "si": "ඔසප් දිනය 5. තවම සංවේදීයි. ලිහිල් ඇඳුම් තෝරා ගත්තා.", "ta": "சுழற்சி நாள் 5. இன்னும் மென்மை. தளர்வான உடைகளைத் தேர்ந்தேன்."},
    {"en": "Cycle day 4. Lighter than yesterday. A warm shower, then bed.", "si": "ඔසප් දිනය 4. ඊයේට වඩා සැහැල්ලුයි. උණුසුම් ස්නානයක්, ඊට පසු නිදාගැනීම.", "ta": "சுழற்சி நாள் 4. நேற்றை விட இலேசு. வெதுவெதுப்பான குளியல், பிறகு படுக்கை."},
    {"en": "Cycle day 3. Heavier than yesterday. I stayed home.", "si": "ඔසප් දිනය 3. ඊයේට වඩා බරයි. ගෙදර ඉන්න ගත්තා.", "ta": "சுழற்சி நாள் 3. நேற்றை விட கனம். வீட்டிலேயே இருந்தேன்."},
    {"en": "Cycle day 2. Cramps in the morning. A warm cloth helped.", "si": "ඔසප් දිනය 2. උදේ කැක්කුමක්. උණුසුම් රෙදි කඩක් උදව් වුණා.", "ta": "சுழற்சி நாள் 2. காலையில் வலி. வெதுவெதுப்பான துணி உதவியது."},
    {"en": "Cycle day 1. It started today. I rested and kept the evening short.", "si": "ඔසප් දිනය 1. අද පටන් ගත්තා. විවේක ගෙන සවස කෙටි කළා.", "ta": "சுழற்சி நாள் 1. இன்று தொடங்கியது. ஓய்வெடுத்து மாலையைச் சுருக்கினேன்."},
    {"en": "Cycle day 28. A quiet day. No extra plans.", "si": "ඔසප් දිනය 28. නිහඬ දවසක්. අමතර සැලසුම් නැත.", "ta": "சுழற்சி நாள் 28. அமைதியான நாள். கூடுதல் திட்டம் இல்லை."},
    {"en": "Cycle day 27. A mild headache. I dimmed the lights.", "si": "ඔසප් දිනය 27. මෘදු හිසරදයක්. ලයිට් අඩු කළා.", "ta": "சுழற்சி நாள் 27. லேசான தலைவலி. விளக்குகளை மங்கலாக்கினேன்."},
    {"en": "Cycle day 26. My back felt tight. I stretched before bed.", "si": "ඔසප් දිනය 26. පිට තදයි. නිදාගැනීමට පෙර දිගහැරියා.", "ta": "சுழற்சி நாள் 26. முதுகு இறுக்கம். தூங்கும் முன் நீட்டினேன்."},
    {"en": "Cycle day 25. I asked someone else to do one errand.", "si": "ඔසප් දිනය 25. එක වැඩක් වෙනත් කෙනෙක්ට ඉල්ලුවා.", "ta": "சுழற்சி நாள் 25. ஒரு வேலையை வேறு ஒருவரிடம் கேட்டேன்."},
    {"en": "Cycle day 24. Bloated by evening. I had a light dinner.", "si": "ඔසප් දිනය 24. සවස ඉදිමීමක්. සැහැල්ලු රාත්‍රී ආහාරයක් ගත්තා.", "ta": "சுழற்சி நாள் 24. மாலையில் வீக்கம். இலேசான இரவு உணவு."},
    {"en": "Cycle day 23. Steady. I went to work.", "si": "ඔසප් දිනය 23. ස්ථිරයි. වැඩට ගියා.", "ta": "சுழற்சி நாள் 23. நிலையாக இருந்தது. வேலைக்குச் சென்றேன்."},
    {"en": "Cycle day 22. Comfortable. Lunch was quiet.", "si": "ඔසප් දිනය 22. සුවපහසුයි. දිවා ආහාරය නිහඬයි.", "ta": "சுழற்சி நாள் 22. வசதியாக இருந்தது. மதிய உணவு அமைதி."},
    {"en": "Cycle day 21. I wanted a few quiet minutes, then I was fine.", "si": "ඔසප් දිනය 21. නිහඬ මිනිත්තු කිහිපයක් ඕන වුණා. ඊට පසු හොඳයි.", "ta": "சுழற்சி நாள் 21. சில அமைதியான நிமிடங்கள் வேண்டும். பிறகு நன்றாக இருந்தது."},
    {"en": "Cycle day 20. A steady day. I logged it and left it there.", "si": "ඔසප් දිනය 20. ස්ථිර දවසක්. සටහන් කර එතනින් තිබ්බා.", "ta": "சுழற்சி நாள் 20. நிலையான நாள். பதிவு செய்து அங்கேயே விட்டேன்."},
    {"en": "Cycle day 19. Low energy in the morning, ordinary by evening.", "si": "ඔසප් දිනය 19. උදේ ශක්තිය අඩුයි. සවස සාමාන්‍යයි.", "ta": "சுழற்சி நாள் 19. காலையில் ஆற்றல் குறைவு. மாலை சாதாரணம்."},
    {"en": "Cycle day 18. I kept a heat pack nearby and kept the usual evening.", "si": "ඔසප් දිනය 18. අත ළඟ උණුසුම් බෑගයක් තිබ්බා. සුපුරුදු සවස තිබ්බා.", "ta": "சுழற்சி நாள் 18. அருகில் ஒரு வெப்பப் பை. வழக்கமான மாலை."},
]


def pack(entry: dict[str, str]) -> str:
    return json.dumps({"en": entry["en"], "si": entry["si"], "ta": entry["ta"]}, ensure_ascii=False)


def _first_sentence(text: str) -> str:
    parts = text.split(". ")
    sentence = parts[0].strip()
    if sentence and not sentence.endswith("."):
        sentence += "."
    return sentence or text


def summary_pack(entry: dict[str, str]) -> str:
    return pack({lang: _first_sentence(entry[lang]) for lang in ("en", "si", "ta")})
