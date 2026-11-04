# Suez University course ILO ingestion and topic crosswalk

## Scope and provenance

This update ingests the course specifications and teaching guides supplied for the Suez University Faculty of Medicine project. The primary official sources are the user-provided Suez University documents. The machine-readable catalog is `data/suez_course_ilos.json`; the existing topic profile is extended in `data/suez_university_curriculum.json`.

**Institution boundary:** the target is Suez University (جامعة السويس), not Suez Canal University (جامعة قناة السويس). No Suez Canal University material is used as an official curriculum source.

## Official Suez University sources ingested

| Module | Source | Scope |
|---|---|---|
| SI 2.4.2 | Surgery I Course Specifications, 2022–2023 | General, plastic, vascular, cardiothoracic, urology and neurosurgery; knowledge and psychomotor skills |
| MI 2.4.1 | Medicine I Study Guide, 2021–2022 | Infectious disease, hepatology/GIT, endocrinology, nephrology, clinical pathology, cardiology, chest, radiology and oncology |
| MII 2.5.1 | Medicine II Course Specifications | Neurology, psychiatry, rheumatology, dermatology and andrology |
| SII 2.5.2 | Surgery II Course Specifications | ENT, ophthalmology and orthopedics |
| E&MR 2.5.3 | Emergency Course Guide and Medical Reporting ILO Proposal | Emergency medicine, toxicology, drug abuse and medical reporting |
| PHC/Obs 2.3.2 | Third-year Study Guide, 2020–2021 | Obstetrics/gynaecology, family medicine and occupational medicine |

The ENT and ophthalmology teaching outlines are also catalogued as **teaching schedules**, not independent ILO specifications. The PHC/Obs guide is not the Pediatrics module.

## Granular source transcription milestone

The granular transcription workspace now contains **616 individually identified, page-cited outcome statements across seven supplied source files**:

| Module/source | Statements | Printed pages |
|---|---:|---:|
| Surgery I (SI 2.4.2, 2022–2023) | 180 | 3–17 |
| Medicine I (MI 2.4.1, 2021–2022) | 111 | 7–26 |
| Medicine II (MII 2.5.1) | 70 | 4–16 |
| Surgery II (SII 2.5.2) | 64 | 4–11 |
| PHC/Obs 2.3.2 (2020–2021) | 112 | 6–17 |
| Emergency Course Guide (E&MR 2.5.3) | 52 | 4–9 |
| Medical Reporting/Toxicology proposal (E&MR 2.5.3) | 27 | 1–3 |

Each statement has a stable transcription ID, source ID, module code, classification and printed page. Source wording has light spelling, punctuation and whitespace normalization; multi-part statements remain grouped where the source groups them. Topic outlines and assessment methods are not counted as ILOs. The Emergency guide and Medical Reporting proposal are separate source documents within the same module.

All records remain `transcribed_not_faculty_verified`. Automated validation checks source identity against the official Suez catalogue, module identity, unique IDs, non-empty text and page bounds. Granular transcription is not the same as objective-to-curriculum mapping or faculty approval. These seven files do not establish that every official course specification has been obtained. PHC/Obs 2.3.2 is explicitly the Obstetrics/Gynaecology, Family Medicine and Occupational Medicine module; it is not the Pediatrics PHC/ped 2.3.1 module.

## Outcome mapping

The catalog distinguishes knowledge, intellectual/clinical reasoning, clinical skills and procedural skills. Outcome statements are concise normalized paraphrases of the uploaded source ILOs, not verbatim transcriptions; source file, institution and module provenance are retained for traceability. The 73 official Suez outcome records are a first-pass grouped catalog: some closely related source bullets have been combined. This is not yet a line-by-line exhaustive transcription of every individual ILO in every supplied course specification; complete outcome-by-outcome extraction and mapping remains a follow-up for the remaining modules. Starter topics receive explicit `course_outcome_refs` only where the uploaded course specifications support a direct or clearly related outcome. Each topic also receives a `course_outcome_mapping_status`.

- `direct_course_outcome`: an explicit course outcome addresses the topic.
- `partial_related_outcome`: the source supports a related but broader outcome.
- `external_benchmark_only`: only an external Pediatrics benchmark is available.
- `module_only_no_specific_ilo`: the module is known, but no sufficiently specific outcome was established.

A null `official_outcome_reference` is intentional when multiple outcomes apply or there is no official single outcome reference. The complete references remain in `course_outcome_refs`.

## Pediatrics: online benchmark, not official Suez ILOs

The Suez University bylaw identifies PHC/ped 2.3.1 in Year 3, Semester 5. The supplied third-year study guide is instead PHC/Obs 2.3.2 and covers Obstetrics/Gynaecology, Family Medicine and Occupational Medicine. It does not supply Pediatrics ILOs.

A public undergraduate Pediatrics course specification was located on the Al-Azhar University, Damietta Faculty of Medicine website. It is a fifth-year course with 260 teaching hours (105 lecture and 155 practical/clinical). A second public undergraduate specification was located on the Aswan University Faculty of Medicine website: a fifth-year course, 2017–2018, with 240 hours (108 lecture and 132 tutorial/practical). Both provide knowledge, intellectual, professional/clinical and general-skill outcomes. Their topic coverage includes growth/development, nutrition, neonatology, preventive pediatrics, genetics, nephrology, cardiovascular and respiratory systems, hematology, infection, endocrinology, musculoskeletal/neuromuscular disorders, CNS, gastroenterology/hepatobiliary, pediatric emergencies/poisoning, behavioral pediatrics and radiology.

Both sources are stored under `external_benchmarks` with institution, URL, course year and explicit non-Suez provenance. They may help identify candidate topic/skill gaps, but:
- it is **not** a Suez University course specification;
- both are fifth-year rather than the Suez bylaw's third-year PHC/ped placement;
- its outcomes are not copied into `official_outcome_reference`;
- pediatric topics remain externally benchmarked until the official Suez PHC/ped 2.3.1 course specification is obtained.

Sources: [Al-Azhar University, Damietta Faculty of Medicine – Pediatric Course Specification](https://domazhermedicine.edu.eg/اقسام-الكلية/الأقسام-الإكلينيكية/طب-الأطفال/الابحاث-العلمية-للقسم/) and [Aswan University, Faculty of Medicine – Pediatrics Course Specification (2017–2018)](https://med.aswu.edu.eg/wp-content/uploads/PDF/CourseSpecification/5/course-specification-pediatrics.pdf).

## Validation and remaining gaps

Automated tests verify that:
1. every crosswalk topic exists in the Suez curriculum profile;
2. every referenced outcome ID exists in the official catalog or the explicitly external benchmark;
3. external Pediatrics outcomes are never treated as official Suez outcomes;
4. PHC/Obs 2.3.2 is not mislabelled as Pediatrics;
5. schedule-only documents are not treated as formal ILO sources.

Remaining gates:
- obtain official Suez University PHC/ped 2.3.1 course specifications/ILOs;
- confirm all uploaded course-specification versions apply to the target cohort;
- obtain missing/current specifications for any modules not represented;
- complete outcome-to-topic coverage analysis and faculty/clinical educator review.

The catalog is currently a machine-readable source of truth; it is not yet wired into a card-generation runtime. Generator integration must consume these outcome references and preserve official-versus-external provenance. This is a source-traceable working crosswalk, not faculty-approved curriculum mapping or exam validation.
