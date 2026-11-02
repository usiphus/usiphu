# Suez University Faculty of Human Medicine: curriculum crosswalk

## Institution identity

This profile targets **Suez University (جامعة السويس), Faculty of Human Medicine (كلية الطب البشري)**. It explicitly excludes **Suez Canal University (جامعة قناة السويس)**; the latter is a separate university and its curriculum must not be substituted.

## What is verified from Suez University's own website

The Faculty of Human Medicine describes a **5+2** medical education model. Its published educational approach is integrated and community-oriented, with self-directed learning, early clinical exposure, clinical-skills development, and emphasis on ethical integrity. It also describes team-based learning, small-group learning, and problem-based learning.

Primary institutional sources:

1. [Faculty of Medicine – Dean's introduction and educational approach](https://suezuni.edu.eg/Med/StaticContent/Index/18)
2. [Faculty of Medicine – official bylaw landing page (لائحة الكلية)](https://suezuni.edu.eg/Med/StaticContent/Index/42)

## Important access limitation

The official bylaw landing page links to a SharePoint-hosted PDF. During this mapping run, opening that PDF redirected to Microsoft sign-in, so the detailed course tables, course codes, academic-year/semester allocations, learning outcomes, hours, and assessment blueprint could not be verified. The student portal is linked from the official site, but it requires student-specific access.

Accordingly, this repository records a **provisional institutional crosswalk**, not a complete or officially approved Suez University syllabus. It uses the existing 13-specialty / 62-topic starter blueprint and associates each topic's existing learning objectives with broad competency strands consistent with the university's publicly stated educational approach. It deliberately leaves official course code, year, semester, and outcome reference blank.

## Crosswalk approach

| Institutional educational feature | Usiphu representation |
|---|---|
| Integrated medical curriculum | Cross-specialty topic map; no unsupported module sequencing asserted |
| Community-oriented learning | Prevention and community-health competency strand |
| Early clinical exposure and clinical skills | Clinical assessment and patient-management strands |
| Team-based and small-group learning | Communication and teamwork strand; suitable case/OSCE activity |
| Problem-based learning | Clinical reasoning and case-based practice |
| Self-directed learning and continuous updating | Evidence-informed learning and resource-discovery workflow |
| Ethical integrity and conduct | Professionalism and ethics strand |
| 5+2 model | Programme metadata only; no invented year/semester breakdown |

## What is not yet mapped

- Official course/module titles and codes.
- The exact distribution of subjects across the five academic years.
- The official two-year internship rotations and competency sign-offs.
- Official course-level learning outcomes and assessment weighting.
- Suez-specific exam blueprint, past-paper weighting, OSCE station blueprint, and progression rules.

## Promotion from provisional to official

1. Obtain the current bylaw PDF and course specifications from the Faculty of Medicine / Student Affairs (or upload them to the repository issue/PR).
2. Extract every official course, module, outcome, academic year, semester, teaching/clinical hours, and assessment method.
3. Create a many-to-many crosswalk from official outcomes to Usiphu topic/objective IDs; preserve unmapped official outcomes as explicit coverage gaps.
4. Ask the relevant departments and curriculum committee to review and approve the mapping.
5. Only then mark the relevant outcomes as sourced, reviewed, and exam-validated. Do not infer approval from automated tests.

The machine-readable profile is [data/suez_university_curriculum.json](../data/suez_university_curriculum.json). Its per-topic status is intentionally `provisional_framework_alignment`.
