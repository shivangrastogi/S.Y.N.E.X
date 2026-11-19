"""Slot value pools for the template generator.

Every pool is split by a stable hash: ~12% of values appear ONLY in the
test split. So the test set checks that the model copies a name/message it
has never seen — not that it memorised "Ravi".

Optional private pools: put one value per line in aeris_brain/private/
contacts.txt or apps.txt (git-ignored) and they are mixed into the TRAIN
split. Only do that on Colab / your own machine.
"""
from __future__ import annotations

import hashlib
import os
import random

_HERE = os.path.dirname(os.path.abspath(__file__))
PRIVATE_DIR = os.path.join(_HERE, os.pardir, "private")


def _bucket(value: str) -> int:
    return int(hashlib.md5(value.encode("utf-8")).hexdigest()[:8], 16) % 100


class Pool:
    def __init__(self, values, test_pct: int = 12):
        vals = list(dict.fromkeys(v for v in values if v))  # dedupe, keep order
        self.test = [v for v in vals if _bucket(v) < test_pct]
        self.train = [v for v in vals if _bucket(v) >= test_pct] or vals
        if not self.test:
            self.test = vals

    def sample(self, rng: random.Random, split: str) -> str:
        return rng.choice(self.test if split == "test" else self.train)

    def add_train(self, values):
        self.train += [v for v in values if v and v not in self.train]


def _private(name: str) -> list[str]:
    p = os.path.join(PRIVATE_DIR, name)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]


# ── people ──────────────────────────────────────────────────────────────
FIRST = """Ravi Priya Amit Neha Rahul Pooja Arjun Sneha Vikram Anjali Rohan Kavya
Aditya Isha Karan Riya Siddharth Meera Varun Nisha Akash Divya Manish Shreya
Nikhil Tanvi Gaurav Simran Harsh Ananya Deepak Payal Sanjay Ritu Abhishek Komal
Vivek Swati Mohit Jyoti Ankit Preeti Saurabh Megha Rajat Kriti Yash Aarti
Kunal Sonam Tarun Bhavna Pranav Naina Ashish Shruti Rakesh Pallavi Sumit Rashmi
Imran Ayesha Faisal Zoya Sameer Farah Arif Sana Joseph Maria Daniel Sarah
Gurpreet Harleen Jaspreet Manpreet Suresh Lakshmi Venkat Kavitha Arun Deepa
Shivang Aman Chirag Dhruv Ishaan Kabir Laksh Om Parth Reyansh Vihaan Aarav
Aditi Bhumi Charu Diya Esha Gauri Hina Ira Juhi Khushi Lavanya Mahi Nidhi
Rupal Sakshi Trisha Urvi Vani Yamini Zara Bunty Pinky Chintu Golu Monu Sonu""".split()

LAST = """Sharma Verma Gupta Singh Kumar Patel Shah Mehta Joshi Rastogi Agarwal Bansal
Malhotra Kapoor Chopra Reddy Nair Iyer Menon Das Bose Banerjee Mukherjee Khan
Sheikh Ansari Fernandes DSouza Gill Sandhu Yadav Mishra Tiwari Pandey Dubey
Saxena Srivastava Chauhan Rathore Thakur Desai Kulkarni Jain
Chatterjee Ghosh Sen Roy Bhattacharya Mohanty Pradhan Pillai Krishnan Rao Naidu
Subramanian Rajan Lyngdoh Sangma Bora Gogoi Lepcha Siddiqui Qureshi Thomas Mathew
Pereira Ahluwalia Irani Mistry Hussain Kujur Toppo Marandi""".split()
# Brain v2: the region/community-balanced first names (diversity.NAMES) join the
# pool — the original list leaned heavily North/West (audit, 2026-11-17).
from .diversity import NAMES as _BALANCED  # noqa: E402
FIRST = FIRST + [n for n, *_ in _BALANCED if n not in FIRST]

RELATIONS_EN = ["mom", "dad", "my mom", "my dad", "my brother", "my sister",
                "my wife", "my husband", "my boss", "brother", "sister",
                "grandma", "grandpa", "my uncle", "my aunt", "my cousin",
                "my friend", "the office", "home"]
RELATIONS_HI = ["mummy", "papa", "maa", "mumma", "bhaiya", "bhai", "didi",
                "dadi", "nani", "dada ji", "nana ji", "chacha", "chachi",
                "mama", "mami", "mausi", "bua", "jiju", "bhabhi", "boss",
                "ghar", "office wale"]


def _people() -> list[str]:
    rng = random.Random(7)
    full = [f"{rng.choice(FIRST)} {rng.choice(LAST)}" for _ in range(220)]
    nick = [f"{n} {s}" for n, s in [("Ravi", "bhai"), ("Neha", "di"),
            ("Amit", "sir"), ("Sharma", "ji"), ("Gupta", "uncle"),
            ("Verma", "aunty"), ("Rahul", "bro")]]
    return FIRST + full + nick


CONTACTS = Pool(_people() + RELATIONS_EN + RELATIONS_HI)
CONTACTS.add_train(_private("contacts.txt"))


# ── phone numbers (generated; formats as STT writes them) ────────────────
def phone_number(rng: random.Random, split: str) -> str:
    first = rng.choice("6789")
    digits = first + "".join(rng.choice("0123456789") for _ in range(9))
    style = rng.randrange(7)
    if style == 0:
        return digits
    if style == 1:
        return f"{digits[:5]} {digits[5:]}"
    if style == 2:
        return f"{digits[:4]} {digits[4:]}"
    if style == 3:
        return f"+91 {digits[:5]} {digits[5:]}"
    if style == 4:
        return f"{digits[:3]} {digits[3:6]} {digits[6:]}"
    if style == 5:
        return f"+91{digits}"
    return f"{digits[:5]}-{digits[5:]}"


# ── message text ──────────────────────────────────────────────────────────
MESSAGES_EN = """I'm running late|I will be there in 10 minutes|call me when you are free
|happy birthday|good morning|good night|I reached home|I'm on my way
|can you send me the notes|let's meet at 5|where are you|I'm stuck in traffic
|don't forget the meeting tomorrow|thank you so much|sorry I missed your call
|I'll call you back|are you coming tonight|please pick me up from the station
|the meeting is postponed|send me the location|congratulations|get well soon
|lunch at 1 pm|I love you|miss you|check your email|I'm in a meeting
|bring milk on the way|what time is the train|see you tomorrow|ok done
|all the best for your exam|reached the office|dinner is ready
|can we talk tonight|I'll be late for dinner|please call back urgently
|the parcel has arrived|have a safe journey|hi|hello|hey what's up|yes|no
|I'll send the money tonight|meeting moved to 4 pm|leaving now""".replace("\n", "").split("|")

MESSAGES_HI = """main late ho jaunga|10 minute mein pahunch raha hoon|free ho to call karna
|happy birthday yaar|good morning|good night|ghar pahunch gaya|raste mein hoon
|notes bhej do|5 baje milte hain|kahan ho|traffic mein phansa hoon
|kal meeting yaad rakhna|bahut bahut thank you|sorry call miss ho gaya
|baad mein call karta hoon|aaj raat aa rahe ho kya|station se pick kar lo please
|meeting cancel ho gayi|location bhejo|badhai ho|jaldi theek ho jao
|khana kha liya kya|main pahunch gaya|thodi der mein aata hoon
|doodh lete aana|train kitne baje hai|kal milte hain|ok ho gaya
|exam ke liye all the best|office pahunch gaya|khana ready hai
|aaj raat baat karein|dinner pe late ho jaunga|urgent hai call karo
|parcel aa gaya|safe journey|kya chal raha hai|haan|nahi|chalo theek hai
|paise raat ko bhej dunga|meeting 4 baje shift ho gayi|nikal raha hoon""".replace("\n", "").split("|")

MESSAGES = {"en": Pool(MESSAGES_EN), "hi": Pool(MESSAGES_HI)}


# ── apps ──────────────────────────────────────────────────────────────────
APPS = Pool("""WhatsApp|Instagram|YouTube|Facebook|Snapchat|Telegram|Gmail|Chrome
|Google Maps|Maps|Spotify|YouTube Music|Netflix|Amazon|Flipkart|Myntra|Meesho
|Swiggy|Zomato|Zepto|Blinkit|BigBasket|Uber|Ola|Rapido|PhonePe|Google Pay|GPay
|Paytm|Camera|Gallery|Photos|Calculator|Clock|Calendar|Contacts|Settings
|Play Store|Truecaller|LinkedIn|Twitter|X|Hotstar|JioCinema|Prime Video
|ChatGPT|Gemini|Claude|Duolingo|Notes|Files|File Manager|Drive|Google Drive
|Keep|Google Keep|Brave|Firefox|Discord|Teams|Zoom|Google Meet|Outlook
|Excel|Word|Canva|CapCut|PicsArt|Shazam|Cred|IRCTC|MakeMyTrip|Airtel Thanks
|My Jio|Axis Mobile|SBI YONO|HDFC Bank|Kotak|Groww|Zerodha Kite|Cricbuzz
|Dream11|Inshorts|Pinterest|Reddit|Threads|Signal|Messages|Phone|Recorder
|Weather|Clock app|Vaani|AppliTrack|Momentum""".replace("\n", "").split("|"))
APPS.add_train(_private("apps.txt"))


# ── music & search ────────────────────────────────────────────────────────
MUSIC = Pool("""Arijit Singh|Kesariya|Tum Hi Ho|Shape of You|lofi music|lo-fi beats
|old Hindi songs|90s Bollywood songs|Kishore Kumar|Lata Mangeshkar|AR Rahman
|Diljit Dosanjh|AP Dhillon|Badshah|Honey Singh|Atif Aslam|Shreya Ghoshal
|Taylor Swift|Ed Sheeran|The Weeknd|Coldplay|Imagine Dragons|BTS
|punjabi songs|romantic songs|sad songs|party songs|workout music|bhajan
|Hanuman Chalisa|Gayatri Mantra|ghazals|Jagjit Singh|sufi music|classical music
|Pasoori|Chaleya|Apna Bana Le|Raataan Lambiyan|Kun Faya Kun|Tujhe Kitna Chahne Lage
|Believer|Blinding Lights|Perfect|Despacito|jazz|rock music|instrumental music
|study music|sleep music|rain sounds|meditation music|Bollywood hits
|Karan Aujla|Sidhu Moose Wala|Prateek Kuhad|Anuv Jain|Lucky Ali|KK
|Nusrat Fateh Ali Khan|Mohammed Rafi|Kumar Sanu|Sonu Nigam""".replace("\n", "").split("|"))

SEARCH = Pool("""cricket score|India vs Australia highlights|best phones under 20000
|how to make chai|paneer butter masala recipe|nearest petrol pump|train status
|PNR status|weather tomorrow|Python tutorial|Flutter tutorial|news today
|stock market today|gold price today|movie showtimes|IPL schedule
|how to tie a tie|funny cat videos|motivational speech|Bhagavad Gita
|meaning of serendipity|full form of NASA|best laptop for coding
|Delhi metro map|dentist near me|how to lose weight|yoga for beginners
|Shah Rukh Khan movies|new web series|lofi study|guitar lessons
|how to invest in mutual funds|income tax filing|Aadhaar update
|passport appointment|bike service center|cake shops near me
|English speaking practice|resume format|interview tips|DSA questions""".replace("\n", "").split("|"))


# ── time / duration / days (as STT writes them) ───────────────────────────
TIMES_EN = Pool("""7 am|7:30 am|6 am|5:45 am|8 o'clock|8 pm|9:15 pm|10 pm|11:30 pm
|6 in the morning|7 in the evening|half past six|quarter to eight|quarter past nine
|noon|midnight|5 pm|4:20 pm|3 pm|1 pm|2:30 pm|12:45 pm|6:10 am|9 am|10:30 am
|11 am|seven thirty|six fifteen|5 in the evening|9 at night|10 in the morning""".replace("\n", "").split("|"))
TIMES_HI = Pool("""subah 7 baje|subah 6 baje|subah saade 6 baje|shaam 6 baje|shaam 5:30 baje
|raat 10 baje|raat 11 baje|dopahar 2 baje|dopahar 1 baje|saat baje|aath baje
|saade saat baje|paune aath baje|sawa nau baje|9 baje|6 baje|5:30 baje
|subah 5 baje|subah 8 baje|raat 9:30 baje|shaam 7 baje|dopahar 3 baje
|subah paanch baje|chhe baje|das baje|gyarah baje""".replace("\n", "").split("|"))
DAYS_EN = Pool("""tomorrow|every day|daily|on weekdays|every weekday|on Monday
|on Sunday|this Saturday|every Monday|on Friday|tomorrow morning|on weekends""".replace("\n", "").split("|"))
DAYS_HI = Pool("""kal|roz|har roz|kal subah|somvar ko|sunday ko|weekdays pe
|har monday|parso|shaniwar ko|har din""".replace("\n", "").split("|"))
DURATIONS_EN = Pool("""5 minutes|10 minutes|2 minutes|1 minute|30 seconds|90 seconds
|15 minutes|20 minutes|25 minutes|45 minutes|1 hour|2 hours|half an hour
|an hour and a half|1 hour 30 minutes|3 minutes|7 minutes|40 minutes
|one minute|five minutes|ten minutes|twenty minutes""".replace("\n", "").split("|"))
DURATIONS_HI = Pool("""5 minute|10 minute|2 minute|ek minute|paanch minute|das minute
|aadha ghanta|ek ghanta|dedh ghanta|do ghante|30 second|15 minute|20 minute
|45 minute|1 ghante 20 minute|3 minute|pandrah minute|bees minute""".replace("\n", "").split("|"))
TIMES = {"en": TIMES_EN, "hi": TIMES_HI}
DAYS = {"en": DAYS_EN, "hi": DAYS_HI}
DURATIONS = {"en": DURATIONS_EN, "hi": DURATIONS_HI}

LABELS = Pool("""gym|office|medicine|meeting|pooja|walk|study|tea|eggs|pasta
|rice|cooking|nap|class|bus|school pickup|exercise|water|call mom""".replace("\n", "").split("|"))


# ── places, facts, maths, misc ────────────────────────────────────────────
PLACES = Pool("""Connaught Place|India Gate|the airport|the railway station|home
|office|Phoenix Mall|Select Citywalk|AIIMS|Noida Sector 18|Cyber Hub|Gurgaon
|Bandra|Marine Drive|Andheri station|Koramangala|MG Road|Indiranagar
|Charminar|Hitech City|Salt Lake|Park Street|Hazratganj|Lucknow|Jaipur
|Agra|Taj Mahal|the nearest hospital|nearest petrol pump|nearest ATM
|Starbucks|McDonald's|the gym|my college|Rajiv Chowk metro station
|Mumbai|Delhi|Bangalore|Pune|Chandigarh|Dehradun|Rishikesh|Goa""".replace("\n", "").split("|"))

FACTS_EN = Pool("""my wifi password is sunshine123|mom's birthday is on 12 March
|I parked on level 2|my car number is DL 3C AB 1234|my blood group is B positive
|I keep the spare keys in the drawer|my locker code is 4471|Ravi's wife is Neha
|I take my medicine at 9 pm|my gym days are Monday Wednesday Friday
|my passport expires in 2029|I lent Amit 2000 rupees|the AC service is due in June
|my favourite colour is blue|I don't eat onion|my flight is on 20 December""".replace("\n", "").split("|"))
FACTS_HI = Pool("""mera wifi password sunshine123 hai|mummy ka birthday 12 March ko hai
|gaadi level 2 pe park ki hai|meri gaadi ka number DL 3C AB 1234 hai
|mera blood group B positive hai|spare chabi drawer mein rakhi hai
|Amit ko 2000 rupaye diye hain|dawai raat 9 baje leni hai
|gym monday wednesday friday ko jaata hoon|AC ki service June mein hai
|main pyaaz nahi khata|meri flight 20 December ko hai""".replace("\n", "").split("|"))
FACTS = {"en": FACTS_EN, "hi": FACTS_HI}

RECALL_EN = Pool("""my wifi password|mom's birthday|where I parked|my car number
|my blood group|where the spare keys are|my locker code|when my flight is
|how much I lent Amit|my gym days""".replace("\n", "").split("|"))
RECALL_HI = Pool("""wifi password|mummy ka birthday|gaadi kahan park ki|gaadi ka number
|mera blood group|spare chabi kahan hai|Amit ko kitne paise diye
|flight kab hai|gym ke din""".replace("\n", "").split("|"))
RECALL = {"en": RECALL_EN, "hi": RECALL_HI}


def maths(rng: random.Random, lang: str) -> str:
    a, b = rng.randint(2, 999), rng.randint(2, 99)
    if lang == "hi":
        return rng.choice([f"{a} plus {b}", f"{a} minus {b}", f"{a} into {b}",
                           f"{a} guna {b}", f"{a} divided by {b}",
                           f"{a} ka {b} percent", f"{b} percent of {a}",
                           f"{b} ka square", f"{a} aur {b} ka total"])
    return rng.choice([f"{a} plus {b}", f"{a} minus {b}", f"{a} times {b}",
                       f"{a} multiplied by {b}", f"{a} divided by {b}",
                       f"{b} percent of {a}", f"the square of {b}",
                       f"{a} into {b}", f"{a} + {b}", f"{a} x {b}"])


TAP_TARGETS = Pool("""OK|Cancel|Send|Next|Skip|Allow|Accept|Continue|Done|Save
|Settings|Search|Back|Sign in|Login|Play|Pause|Subscribe|Like|Share
|Download|Install|Open|Close|Not now|Got it|Yes|No|Reply|Delete""".replace("\n", "").split("|"))

TRANSLATE_TEXT = Pool("""good morning|how are you|thank you very much|where is the station
|I am hungry|what is your name|see you tomorrow|I love India
|please help me|how much does this cost|mujhe paani chahiye|aap kaise ho
|main ghar ja raha hoon|kya haal hai""".replace("\n", "").split("|"))
LANGUAGES = Pool("""Hindi|English|Tamil|Telugu|Marathi|Bengali|Punjabi|Gujarati
|Kannada|Malayalam|Urdu|French|Spanish|German|Japanese|Arabic""".replace("\n", "").split("|"))

LAPTOP_CMDS_EN = Pool("""open Chrome|open VS Code|lock the screen|shut down|restart
|take a screenshot|play music|pause the video|increase the volume|mute
|open my downloads|close all windows|minimize everything|open notepad
|start the presentation|open YouTube|open Gmail|put it to sleep
|turn up the brightness|show the desktop""".replace("\n", "").split("|"))
LAPTOP_CMDS_HI = Pool("""chrome kholo|vs code kholo|screen lock karo|band kar do|restart karo
|screenshot lo|gaana chalao|video pause karo|volume badhao|mute karo
|downloads kholo|saari windows band karo|notepad kholo|youtube kholo
|sleep mode mein daalo|desktop dikhao""".replace("\n", "").split("|"))
LAPTOP_CMDS = {"en": LAPTOP_CMDS_EN, "hi": LAPTOP_CMDS_HI}

NOTES = {"en": Pool("""buy milk and bread|call the plumber on Monday|ideas for the app
|pay the electricity bill|book tickets for Goa|renew the car insurance
|gift ideas for mom|read the Flutter docs""".replace("\n", "").split("|")),
         "hi": Pool("""doodh aur bread lana hai|plumber ko monday ko call karna
|bijli ka bill bharna hai|Goa ki tickets book karni hain|gaadi ka insurance renew karna
|mummy ke liye gift sochna""".replace("\n", "").split("|"))}

REMIND_TEXT = {"en": Pool("""take my medicine|call mom|pay the rent|submit the report
|water the plants|pick up the kids|join the meeting|buy groceries|drink water
|go for a walk|check the oven|charge the phone""".replace("\n", "").split("|")),
               "hi": Pool("""dawai lena|mummy ko call karna|kiraya dena|report submit karna
|paudhon ko paani dena|bachchon ko lena|meeting join karna|sabzi lana
|paani peena|walk pe jaana|phone charge karna""".replace("\n", "").split("|"))}

EVENT_TITLES = Pool("""team meeting|dentist appointment|lunch with Priya|project review
|parents' anniversary dinner|interview with Google|gym session|doctor visit
|movie night|client call|standup|birthday party""".replace("\n", "").split("|"))
