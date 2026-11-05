"""
Comprehensive, streamlined test suite for OllamaOccupationExtractor.
Tests:
  - Specific planned employment vs vague aspirations / interview processes
  - Organizational and sector employment (non-profit, tech)
  - Third-party mentions & Service recipients
  - Metaphors, Idioms, Costumes & Hypotheticals
  - Aspirations, Job Applications & Legal/Medical Disclaimers
  - Casual identity nouns, Hobbies, Family roles & Compliments
  - Authentic first-person self-reports, verbal actions & profile bios
"""

import pytest
from dataset.scripts.ingest.ollama_extractor import OllamaOccupationExtractor


@pytest.fixture(scope="module")
def extractor():
    return OllamaOccupationExtractor(model="granite4.1:3b", temperature=0.0)


TEST_SCENARIOS = [
    # --- Specific Planned Employment (Valid) vs Vague / Unhired Aspirations (Reject) ---
    ("I'm going to work at a software company this summer", True, ("software", "employee"), "Specific planned summer job"),
    ("I'm going to work at Wendy's with jake in winter", True, ("wendy", "fast food", "worker"), "Specific planned winter job with peer"),
    ("I'm going to work at Wendy's downtown", True, ("wendy", "fast food", "worker"), "Specific planned job with location"),
    ("i plan to work at KFC this june holiday with ahmad", True, ("fast food", "kfc", "worker"), "Specific planned holiday job with peer"),
    ("I'm doing an interview for Wendys and its going to be hard", False, None, "Job interview / unhired"),
    ("I'm going to work at Wendy's in a few years", False, None, "Distant aspiration without concrete plan"),
    ("I'm going to work at Wendy's", False, None, "Vague future intention without specifics"),

    # --- Organizational, Sector & Workplace Employment ---
    ("I work in tech.", True, ("tech", "worker"), "Sector role tech worker"),
    ("I work for a non-profit organization.", True, ("non-profit", "worker"), "Organizational employment non-profit worker"),
    ("I get in free because I work for a non-profit cultural institution.", True, ("non-profit", "cultural", "worker", "institution"), "Employed at cultural institution"),
    ("Two days and I'll have been working at McDonald's for one year.", True, ("fast food", "mcdonald", "worker", "cashier"), "One year workplace tenure"),
    ("I got the corn maze job!!", True, ("corn maze", "worker", "guide"), "Hired for seasonal corn maze job"),
    ("I am a Hardee's employee.", True, ("hardee", "fast food", "employee", "worker"), "Workplace employee self-report"),

    # --- Third-party mentions & Coworkers (Must be rejected -> []) ---
    ("Sissy is a lady I work with.", False, None, "Coworker reference / lady"),
    ("My dentist came to visit today.", False, None, "Third party dentist visit"),
    ("My brother is an electrician, he fixed my wiring.", False, None, "Third party brother"),
    ("I took my dog to the vet yesterday.", False, None, "Third party vet visit"),
    ("The police officer gave me a speeding ticket.", False, None, "Third party police encounter"),
    ("Had a long meeting with our accountant.", False, None, "Third party client meeting"),
    ("The doctor told me I need surgery.", False, None, "Third party doctor advice"),
    ("My teacher was very strict in school.", False, None, "Third party teacher memory"),
    ("Called the plumber to fix the sink leak.", False, None, "Third party plumber hiring"),
    ("My therapist recommended I try daily meditation.", False, None, "Patient not therapist"),
    ("Hired a contractor to remodel our master bathroom.", False, None, "Homeowner hired contractor"),
    ("The flight attendant gave me an extra ginger ale.", False, None, "Passenger not flight attendant"),
    ("My personal trainer destroyed my legs at the gym today.", False, None, "Client not trainer"),
    ("My lawyer told me not to sign the contract.", False, None, "Third party lawyer"),
    ("I am currently seeing an occupational therapist.", False, None, "Patient not therapist"),
    ("Unlike my sister who is a dentist, I never went to college.", False, None, "Third party sister dentist"),

    # --- Metaphors, Idioms, Costumes, Pretend & Hypotheticals (Must be rejected -> []) ---
    ("If I were a carpenter, I would build you a house.", False, None, "Hypothetical carpenter"),
    ("Acting like a referee between my two arguing toddlers.", False, None, "Metaphorical referee"),
    ("She is a real butcher when it comes to cutting hair.", False, None, "Idiom butcher / third-party"),
    ("I had to play detective to find where my cat hid my keys.", False, None, "Metaphorical detective"),
    ("My boss is a clown and our manager is a joke.", False, None, "Insult clown/joke"),
    ("I am the architect of my own destiny.", False, None, "Philosophical architect"),
    ("He is a wizard with Excel spreadsheets.", False, None, "Idiom wizard / third-party"),
    ("Dressed up as a sexy nurse for Halloween.", False, None, "Costume nurse"),
    ("When I was little I pretended to be an astronaut.", False, None, "Childhood pretend astronaut"),

    # --- Aspirations, Applying, Disclaimers, Seeking Services (Must be rejected -> []) ---
    ("Studying hard for the bar exam so I can become a lawyer.", False, None, "Aspiration lawyer"),
    ("I applied for a software engineer role at Netflix today.", False, None, "Applicant software engineer"),
    ("Dreaming of being a commercial pilot one day.", False, None, "Dreaming pilot"),
    ("Interviewed for a barista position this morning.", False, None, "Interviewed barista"),
    ("I am NOT a lawyer and this is not legal advice.", False, None, "Disclaimer not a lawyer"),
    ("I am no doctor, but you should get that mole checked out.", False, None, "Disclaimer no doctor"),
    ("Looking for a reliable plumber in the Chicago area.", False, None, "Seeking plumber service"),

    # --- Casual Nouns, Hobbies, Status, Compliments (Must be rejected -> []) ---
    ("I'm a kind, gentle a computer whiz and with a huge family", False, None, "Compliment / skill not job"),
    ("She is a very sweet lady.", False, None, "Casual noun lady"),
    ("I love video games and I am a big Marvel fan.", False, None, "Hobby / fandom"),
    ("Proud mother of two and loving wife.", False, None, "Family role"),
    ("Just a cool guy who loves sports.", False, None, "Casual noun guy"),
    ("Senior at Ohio State studying biology.", False, None, "Student status"),
    ("Woke up with a terrible migraine and headache.", False, None, "Medical symptoms"),
    ("Everyone thinks I am a librarian because I wear glasses.", False, None, "Stereotype librarian"),

    # --- Valid Self-Reports & Bios (Must be extracted) ---
    ("My bio: Dentist", True, "dentist", "Bio self-report dentist"),
    ("Bio: High school biology teacher and coffee addict", True, "teacher", "Bio teacher"),
    ("I work as a commercial electrician.", True, "electrician", "Self-report electrician"),
    ("As a carpenter, I always check the plumb line.", True, "carpenter", "Self-report carpenter"),
    ("Before becoming a lawyer, I worked as a paralegal.", True, "paralegal", "Career history paralegal"),
    ("Software Engineer at Google. Views my own.", True, "software engineer", "Bio software engineer"),
    ("Registered Nurse (RN) at Memorial Hospital.", True, "nurse", "Bio registered nurse"),
    ("I have been a welder for 12 years.", True, "welder", "Self-report welder"),
    ("Freelance comic artist and illustrator.", True, "artist", "Bio comic artist & illustrator"),
    ("Working as a line cook at Denny's 40 hours a week.", True, "cook", "Colloquial line cook"),
    ("My 9-5 is front-end web development at a fintech startup.", True, "developer", "Colloquial web developer"),
    ("I drive a school bus for the local county district.", True, "bus driver", "Colloquial school bus driver"),
    ("Been doing commercial roofing since I was eighteen.", True, "roof", "Colloquial roofer"),
    ("Staff pediatrician at Seattle Children's Hospital.", True, "pediatrician", "Bio pediatrician"),
    ("I do freelance wedding photography on weekends.", True, "photographer", "Colloquial photographer"),
    ("Apprentice electrician with IBEW Local 46.", True, "electrician", "Bio apprentice electrician"),
    ("I teach eighth grade history and coach varsity track.", True, "teacher", "Teacher and coach"),
    ("I quit my retail cashier job last week after three years.", True, "cashier", "Past cashier job"),
    ("I sling drinks at a dive bar on weekends.", True, "bar", "Colloquial bartender"),
    ("I bag groceries at Safeway on weekends.", True, ("retail", "bagger", "grocery", "cashier", "worker", "employee", "store"), "Colloquial grocery worker"),
    ("I stock shelves on the graveyard shift at Walmart.", True, ("stock", "worker", "cashier", "retail"), "Colloquial shelf stocker"),
    ("I retired after 30 years as a high school principal.", True, "principal", "Retired principal"),
    ("I was promoted to senior backend engineer last month.", True, "engineer", "Promoted backend engineer"),
    ("I got hired as a barista at the campus coffee shop.", True, "barista", "Hired barista"),
    ("I work as an auto mechanic specializing in diesel engines.", True, "mechanic", "Auto mechanic"),

    # --- Real-World Social Media Bios (Hashtags, Pipes, Academic, Creative & Executive) ---
    ("My bio: Data Viz, Maps & GIS. Tech Writer for MapTiler. FOSS4G UK 2019 Co-Chair.", True, ("tech writer", "writer"), "Bio tech writer"),
    ("My bio: Researcher IRD @ UMR MARBEC Honorary Researcher LECReefs @ Lancaster Environment Centre", True, "researcher", "Bio researcher"),
    ("My bio: #physician #dementia #delirium #disabled Honorary Visiting Professor, School of Law", True, ("physician", "professor"), "Bio physician hashtag & visiting professor"),
    ("My bio: VP of Research and Policy at TDC | Author of Our Common Wealth", True, ("author", "vp", "research", "policy"), "Bio VP & Author"),
    ("My bio: Author 'The Politics of Intersectional Practice' Bristol University Press Adjunct Prof, York Univers", True, ("author", "prof"), "Bio Author & Adjunct Prof"),
    ("My bio: Recovering academic, now working for the National Trust Honorary Associate Professor at UEA", True, ("associate professor", "professor", "academic"), "Bio Associate Professor"),
    ("My bio: Postdoctoral Researcher @unibe.ch & Honorary Research Fellow", True, ("researcher", "fellow"), "Bio Postdoctoral Researcher & Fellow"),
    ("My bio: Concept and Cover Artist for Lucasfilm, Dark Horse, IDW, Prime Video/Gaming", True, ("artist", "concept artist", "cover artist"), "Bio concept and cover artist"),
    ("My bio: Former beat reporter. Wrestling and music nerd.", True, ("reporter", "beat reporter"), "Bio former beat reporter"),
    ("My bio: 3d generalist at @sparkuniverse.com", True, ("generalist", "3d", "artist"), "Bio 3D generalist"),
    ("My bio: Former 911 operator. Married. 1 son. Proud Maritimer", True, ("operator", "911"), "Bio former 911 operator"),
    ("My bio: Culture correspondent at NPR, music critic at the New York Times.", True, ("correspondent", "critic", "journalist"), "Bio culture correspondent & music critic"),
    ("My bio: Nature Photographer, Physician, Artist, Historian, Polymath.", True, ("photographer", "physician", "artist", "historian"), "Bio photographer physician artist"),
    ("My bio: Retired horticulturist, chicken wrangler, pedant, general goofball.", True, ("horticulturist", "gardener"), "Bio retired horticulturist"),
    ("My bio: I'm a retired hotelier & Progressive Bisabuelo", True, ("hotelier", "hotel"), "Bio retired hotelier"),
    ("My bio: BS, MS, JD. Rtd. labor atty. Writer, researcher", True, ("attorney", "lawyer", "writer", "researcher", "atty"), "Bio retired labor atty writer researcher"),
    ("My bio: Appalachian Horticulturalist & Visual Artist", True, ("horticulturalist", "artist"), "Bio horticulturalist & visual artist"),
    ("My bio: Ex teacher, ex bookseller, now ex Labour member. Vet receptionist.", True, ("receptionist", "teacher", "bookseller"), "Bio vet receptionist ex teacher"),

    # --- Real-World Social Media Noise / Non-Job Bios (Must be rejected -> []) ---
    ("My bio: Riverdale Dirtbusters Cleaning LLC. is professional fully insured cleaning company, known for our experties and honesty", False, None, "Company promotional bio"),
    ("My bio: Fascinating fishing stories from anglers around the world https://thehookup1.substack.com/", False, None, "Newsletter promotional bio"),
    ("My bio: B. Pharm + MBA (Healthcare Management and Hospital Administration and Marketing) + MSc", False, None, "Degree listing without occupation"),
]


@pytest.mark.parametrize("text,should_extract,expected_keyword,description", TEST_SCENARIOS)
def test_occupation_extraction(extractor, text, should_extract, expected_keyword, description):
    res = extractor.extract(text)
    if should_extract:
        assert len(res) > 0, f"[{description}] Expected extraction for: '{text}', got: {res}"
        if expected_keyword:
            res_lower = " ".join(item.lower() for item in res)
            keywords = (expected_keyword,) if isinstance(expected_keyword, str) else expected_keyword
            assert any(kw.lower() in res_lower for kw in keywords), (
                f"[{description}] Expected any of {keywords} in {res} for: '{text}'"
            )
    else:
        assert res == [], f"[{description}] Expected empty list (rejection) for: '{text}', got: {res}"


def test_sanitize_occupation_title():
    from dataset.scripts.ingest.ollama_extractor import sanitize_occupation_title

    # Comma in parentheses -> stripped to "VP"
    assert sanitize_occupation_title("VP (e.g., VP of Operations, VP of Marketing, etc.)") == "VP"
    # Comma outside parentheses -> rejected
    assert sanitize_occupation_title("VP of Operations, VP of Marketing") is None
    # Banned words
    assert sanitize_occupation_title("Hey there! It sounds like you had quite a day...") is None
    assert sanitize_occupation_title("I'm sorry to hear about that") is None
    assert sanitize_occupation_title("Hello world engineer") is None
    assert sanitize_occupation_title("Please help me find a job") is None
    assert sanitize_occupation_title("Unspecified worker") is None
    assert sanitize_occupation_title("temp worker") is None
    assert sanitize_occupation_title("25 year old carpenter") is None
    # Substring of banned word does not trigger whole-word match
    assert sanitize_occupation_title("fold specialist") == "fold specialist"
    # Long strings >= 15 words
    long_str = "This is a run on conversational sentence that has way more than fifteen words in total length and should be rejected"
    assert sanitize_occupation_title(long_str) is None
    # Clean occupations preserved
    assert sanitize_occupation_title("Registered Nurse (RN)") == "Registered Nurse (RN)"
    assert sanitize_occupation_title("Software Engineer") == "Software Engineer"


if __name__ == "__main__":
    pytest.main(["-v", "-s", __file__])
