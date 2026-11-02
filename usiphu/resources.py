"""Curated outbound discovery links; no third-party content is copied."""
from urllib.parse import quote_plus

PROVIDERS = [
    ("pubmed", "PubMed", "Biomedical literature index", "https://pubmed.ncbi.nlm.nih.gov/?term=",
     "Free citations and abstracts; full text is not guaranteed."),
    ("pmc", "PubMed Central", "Open full-text archive", "https://pmc.ncbi.nlm.nih.gov/?term=",
     "Free full text where deposited; check each article's reuse license."),
    ("bookshelf", "NCBI Bookshelf", "Books and reports", "https://www.ncbi.nlm.nih.gov/books/?term=",
     "Free books and reports; check edition and update date."),
    ("cureus", "Cureus", "Open-access medical journal", "https://www.cureus.com/search?query=",
     "Open access; assess peer review, methods, conflicts, and article-specific license."),
    ("ankiweb", "AnkiWeb shared decks", "Community flashcard discovery",
     "https://ankiweb.net/shared/decks?search=",
     "User-contributed decks; independently verify accuracy and licensing before reuse."),
    ("doctorde", "DoctorDE (web search)", "Medical challenge discovery",
     "https://www.google.com/search?q=DoctorDE+",
     "Search route only: a stable official DoctorDE endpoint has not been verified."),
    ("who", "WHO publications", "International guidance",
     "https://www.who.int/publications/i?search=",
     "Check publication date and applicability to local practice."),
    ("nice", "NICE guidance", "Clinical guidelines",
     "https://www.nice.org.uk/search?q=",
     "UK guidance; compare with local protocols and national recommendations."),
    ("cochrane", "Cochrane Library", "Systematic reviews",
     "https://www.cochranelibrary.com/search?searchBy=0&searchText=",
     "Check review date, population, and certainty of evidence."),
    ("mededportal", "MedEdPORTAL", "Peer-reviewed medical teaching resources",
     "https://www.mededportal.org/search?query=",
     "Check resource permissions and intended learner level."),
    ("guidelines", "Guidelines search", "Guideline discovery",
     "https://www.google.com/search?q=",
     "Prefer current society or government guidelines; verify the issuing organization."),
]


SPECIALTY_GUIDELINES = {
    "urology": ("EAU Guidelines", "https://uroweb.org/guidelines",
                "European Association of Urology guideline library."),
    "cardiology": ("ESC Clinical Practice Guidelines",
                   "https://www.escardio.org/Guidelines/Clinical-Practice-Guidelines",
                   "European Society of Cardiology guideline library."),
    "nephrology": ("KDIGO Guidelines", "https://kdigo.org/guidelines/",
                   "Kidney Disease: Improving Global Outcomes guideline library."),
    "respiratory": ("GINA Strategy Reports", "https://ginasthma.org/reports/",
                    "Global Initiative for Asthma reports; check current edition."),
    "pulmonology": ("GOLD Reports", "https://goldcopd.org/",
                    "Global Initiative for Chronic Obstructive Lung Disease reports."),
    "infectious": ("IDSA Practice Guidelines", "https://www.idsociety.org/practice-guideline/",
                   "Infectious Diseases Society of America guideline library."),
    "obstetrics": ("ACOG Clinical Guidance", "https://www.acog.org/clinical",
                   "American College of Obstetricians and Gynecologists guidance."),
    "paediatrics": ("AAP Clinical Practice Guidelines", "https://www.aap.org/en/patient-care/",
                    "American Academy of Pediatrics patient-care guidance."),
    "ophthalmology": ("AAO Preferred Practice Patterns", "https://www.aao.org/education/preferred-practice-pattern",
                      "American Academy of Ophthalmology practice patterns."),
    "vascular": ("SVS Clinical Practice Guidelines", "https://vascular.org/clinical-guidance",
                 "Society for Vascular Surgery clinical guidance."),
    "anaesthesia": ("ASA Practice Parameters", "https://www.asahq.org/standards-and-practice-parameters",
                    "American Society of Anesthesiologists standards and practice parameters."),
    "neurology": ("AAN Practice Guidelines", "https://www.aan.com/Guidelines/home/ByTopic",
                  "American Academy of Neurology guideline topics."),
    "dermatology": ("AAD Clinical Guidelines", "https://www.aad.org/member/clinical-quality/guidelines",
                    "American Academy of Dermatology clinical guidelines."),
    "psychiatry": ("APA Clinical Practice Guidelines", "https://www.psychiatry.org/psychiatrists/practice/clinical-practice-guidelines",
                   "American Psychiatric Association clinical practice guidelines."),
}


def discover_resources(topic: str, specialty: str | None = None) -> list[dict[str, str]]:
    """Build search URLs and append a specialty guideline hub when recognized."""
    query = " ".join(part for part in (specialty, topic) if part).strip()
    encoded = quote_plus(query)
    results = [
        {"id": pid, "name": name, "kind": kind, "url": base + encoded,
         "note": note}
        for pid, name, kind, base, note in PROVIDERS
    ]
    results.extend([
        {"id": "acp-doctors-dilemma", "name": "ACP Doctor's Dilemma",
         "kind": "Interactive medical quiz challenge", "url": "https://ddm.acponline.org/",
         "note": "American College of Physicians quiz competition format; educational challenge, not a guideline."},
        {"id": "doximity-case-challenges", "name": "Doximity Clinical Case Challenges",
         "kind": "Clinical case challenge library",
         "url": "https://blog.doximity.com/articles/compete-learn-and-grow-with-our-clinical-case-challenge-library",
         "note": "External case-challenge resource; access may require a Doximity account."},
        {"id": "doctors-challenge", "name": "Doctors Challenge app",
         "kind": "Medical quiz app",
         "url": "https://play.google.com/store/apps/details?id=com.mahmoudhssn.doctorschallenge",
         "note": "External app listing; availability, privacy terms, ads, and content quality are controlled by its publisher."},
        {"id": "geeky-medics", "name": "Geeky Medics free question bank",
         "kind": "Free medical question bank",
         "url": "https://app.geekymedics.com/questions/",
         "note": "Free account required for the free question bank; premium exam products are separate."},
        {"id": "geeky-medics-osce", "name": "Geeky Medics OSCE guides",
         "kind": "Open-access clinical skills and OSCE revision",
         "url": "https://geekymedics.com/",
         "note": "Most revision articles and OSCE guides are free to read; interactive platform features vary by plan."},
        {"id": "teachmesurgery", "name": "TeachMeSurgery",
         "kind": "Surgical revision resource",
         "url": "https://teachmesurgery.com/",
         "note": "Surgical topic guides; question-bank and MRCS features may require a paid plan."},
        {"id": "teachmepaediatrics", "name": "TeachMePaediatrics",
         "kind": "Paediatrics revision resource",
         "url": "https://teachmepaediatrics.com/",
         "note": "Topic-based paediatric revision and clinical learning resource."},
        {"id": "surghub", "name": "SURGhub",
         "kind": "Free global surgery courses",
         "url": "https://www.surghub.org/",
         "note": "Free account and free courses; course availability and language vary."},
        {"id": "teachmeanatomy", "name": "TeachMeAnatomy",
         "kind": "Anatomy revision resource",
         "url": "https://teachmeanatomy.info/",
         "note": "Topic-based anatomy revision; check access and licensing for each resource."},
    ])
    normalized = (specialty or "").casefold()
    for key, (name, url, note) in SPECIALTY_GUIDELINES.items():
        if key in normalized:
            results.append({
                "id": f"guideline-{key}", "name": name,
                "kind": "Specialty guideline hub", "url": url, "note": note,
            })
    return results
