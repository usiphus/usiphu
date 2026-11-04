"""Streamlit interface for the Usiphu 2.0 learning workspace."""
import json
import os
import random
from datetime import UTC, datetime

import streamlit as st

from usiphu.ai_answer_grader import AnswerGradingError, grade_assessment_answers
from usiphu.ai_provider import (
    GenerationNotConfigured,
    generate_topic_cards,
    provider_status,
)
from usiphu.ai_question_review import QuestionReviewError, review_mcq_candidate
from usiphu.answer_checker import check_assessment_answers, check_mcq_answer
from usiphu.assessment_review import list_non_mcq_candidates, load_assessments, save_non_mcq_review
from usiphu.coverage import coverage_report, load_coverage_register
from usiphu.curriculum import coverage_summary, flatten_topics, load_curriculum
from usiphu.extraction import extract_source, load_extraction
from usiphu.models import ReviewState
from usiphu.pilot_validation import build_pilot_validation_report, record_ai_review
from usiphu.practice import filter_questions, load_cases, load_questions
from usiphu.question_review import approve_candidate, list_review_candidates, save_candidate_review
from usiphu.resources import discover_resources
from usiphu.scheduler import schedule_review
from usiphu.source_inbox import DEFAULT_SOURCE_DIR, list_sources, save_source
from usiphu.storage import (
    dashboard_stats,
    due_cards,
    generated_drafts,
    initialize,
    question_attempt_history,
    question_bank_stats,
    question_topic_performance,
    record_question_attempt,
    record_review,
    save_flashcard,
    save_generated_drafts,
    set_topic_progress,
    topic_progress,
)

st.set_page_config(page_title="USIPHU", page_icon="🩺", layout="wide")

AUTH_REQUIRED = os.getenv("USIPHU_AUTH_REQUIRED", "false").lower() == "true"
if AUTH_REQUIRED:
    if not st.user.is_logged_in:
        st.title("🩺 USIPHU")
        st.write("Sign in with your configured identity provider to access your learning workspace.")
        st.button("Sign in", on_click=st.login)
        st.stop()
    subject = st.user.get("sub")
    if not subject:
        st.error("The identity provider did not return a stable subject identifier.")
        st.stop()
    learner_id = f"{st.user.get('iss', 'oidc')}:{subject}"
    reviewer_subjects = {value.strip() for value in os.getenv("USIPHU_REVIEWER_SUBJECTS", "").split(",") if value.strip()}
    reviewer_access = subject in reviewer_subjects
    with st.sidebar:
        st.caption(f"Signed in: {st.user.get('email', 'learner')}")
        st.button("Sign out", on_click=st.logout)
else:
    learner_id = "local"
    reviewer_access = True
    st.sidebar.warning("Local single-learner mode. Enable OIDC before deploying for multiple learners.")

initialize()
st.markdown("""
<style>
:root { --usiphu-ink:#172b4d; --usiphu-teal:#087e83; --usiphu-mist:#f2f6f8; }
[data-testid="stAppViewContainer"] { background: #f5f8fa; }
[data-testid="stHeader"] { background: rgba(245,248,250,.88); }
.block-container { max-width: 1440px; padding-top: 1.6rem; padding-bottom: 3rem; }
h1, h2, h3 { color: var(--usiphu-ink); letter-spacing: -.025em; }
[data-testid="stMetric"] { background: white; border: 1px solid #e3ebef; padding: 1rem 1.1rem; border-radius: 16px; box-shadow: 0 4px 18px rgba(20,45,70,.035); }
[data-testid="stTabs"] [role="tablist"] { gap: .45rem; border-bottom: 1px solid #dce6eb; }
[data-testid="stTabs"] button[role="tab"] { border-radius: 12px 12px 0 0; padding: .7rem 1rem; font-weight: 600; }
[data-testid="stTabs"] button[aria-selected="true"] { color: var(--usiphu-teal); border-bottom: 3px solid var(--usiphu-teal); }
[data-testid="stButton"] button[kind="primary"], .stButton button[kind="primary"] { background: var(--usiphu-teal); border-color: var(--usiphu-teal); border-radius: 11px; }
[data-testid="stTextInput"] input, [data-testid="stSelectbox"] div[data-baseweb="select"] { border-radius: 10px; }
[data-testid="stExpander"] { background: white; border: 1px solid #e3ebef; border-radius: 12px; }
[data-testid="stSidebar"] { background: #edf3f5; }
div[data-testid="stAlert"] { border-radius: 12px; }
</style>
""", unsafe_allow_html=True)

st.title("🩺 USIPHU")
st.caption("Your medical learning workspace · Learn clearly. Practise deliberately. Track mastery.")

curriculum = load_curriculum()
stats = dashboard_stats(learner_id=learner_id)
coverage = {**coverage_summary(curriculum), **coverage_report()}
coverage_register = load_coverage_register()

st.caption(
    f"Curriculum validation: {coverage['topics_sourced']} sourced · "
    f"{coverage['topics_reviewed']} clinically reviewed · "
    f"{coverage['topics_exam_validated']} exam validated. "
    f"{coverage['topics_planned']} planned topics; mapped topics are not automatically syllabus-complete."
)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Medical disciplines", coverage["specialties"])
c2.metric("Curriculum topics", coverage["topics"])
c3.metric("Your flashcards", stats["flashcards"])
c4.metric("Your reviews", stats["reviews_completed"])

page = st.sidebar.radio(
    "Workspace",
    ["Learn", "Resources", "Practice", "Flashcards", "Progress", "AI Studio", "Question Bank", "Review Editor", "Pilot Dashboard"],
    label_visibility="visible",
)
if page == "Learn":
    st.subheader("Specialty curriculum")
    st.write(f"{coverage['domains']} domains · {coverage['topics']} topics · {coverage['objectives']} learning objectives")
    st.progress(coverage["objective_coverage_percent"] / 100,
                text=f"{coverage['objective_coverage_percent']}% of listed topics have learning objectives")
    st.subheader("Suez University course-outcome mapping")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        "Official outcomes linked",
        f"{coverage['official_outcomes_linked_at_topic_level']}/{coverage['course_outcomes_catalogued']}",
        f"{coverage['official_outcome_mapping_percent']}% topic-level",
    )
    m2.metric("Outcomes not linked", coverage["official_outcomes_not_linked_in_current_crosswalk"])
    m3.metric("Topics without verified ILO", coverage["topics_without_verified_outcome_mapping"])
    m4.metric("External-only topics", coverage["topics_external_benchmark_only"])
    st.caption(
        "The 73-outcome catalogue is a first-pass, non-exhaustive extraction. "
        "Topic-level links do not prove that each individual objective is fully mapped. "
        "No objective has yet received individual faculty-verified mapping."
    )
    with st.expander("Official Suez outcomes not linked in the current topic crosswalk"):
        unlinked = [
            row for row in coverage_register["official_course_outcomes"]
            if row["mapping_status"] == "not_linked_in_current_topic_crosswalk"
        ]
        st.dataframe(
            [{"Outcome ID": row["outcome_id"], "Module": row["module_code"],
              "Domain": row["domain"], "Outcome": row["text"]} for row in unlinked],
            use_container_width=True, hide_index=True,
        )
    with st.expander("Topics still requiring verified course-outcome mapping"):
        unmapped = [
            row for row in coverage_register["topics"]
            if row["course_outcome_mapping_status"] == "not_mapped_no_verified_course_outcome"
        ]
        st.dataframe(
            [{"Specialty": row["specialty_title"], "Domain": row["domain_title"],
              "Topic": row["topic_title"], "Objectives": len(row["objectives"])}
             for row in unmapped],
            use_container_width=True, hide_index=True,
        )
    with st.expander("Objective-level mapping status"):
        st.write({
            "Direct topic link only (not objective-specific)": coverage["objectives_with_topic_level_link_only"],
            "Partial topic link only": coverage["objectives_partially_linked_at_topic_level"],
            "External benchmark only": coverage["objectives_external_benchmark_only"],
            "Module-only alignment": coverage["objectives_module_only_no_specific_ilo"],
            "No verified mapping": coverage["objectives_without_verified_outcome_mapping"],
            "Individually faculty-verified": coverage["objective_level_mapping_verified"],
        })
    search = st.text_input("Search specialties, domains, and topics")
    rows = flatten_topics(curriculum)
    if search:
        rows = [row for row in rows if search.casefold() in " ".join(row.values()).casefold()]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    with st.expander("Browse specialty objectives"):
        for specialty in curriculum.specialties:
            with st.expander(specialty.title):
                for domain in specialty.domains:
                    st.markdown(f"**{domain.title}**")
                    for topic in domain.topics:
                        st.write("• " + topic.title)
                        for objective in topic.objectives:
                            st.caption(f"  – {objective.text}")
elif page == "Resources":
    st.subheader("Discover learning sources")
    topic = st.text_input("Topic", placeholder="e.g. acute urinary retention")
    specialty = st.text_input("Specialty (optional)", placeholder="e.g. Urology")
    if topic.strip():
        for resource in discover_resources(topic.strip(), specialty.strip() or None):
            st.markdown(f"**[{resource['name']}]({resource['url']})** · {resource['kind']}")
            st.caption(resource["note"])
elif page == "Practice":
    st.subheader("Question practice")
    questions = load_questions()
    draft_count = sum(question.review_status == "draft" for question in questions)
    st.warning(f"{draft_count} sample questions are still editorial drafts and require clinical review.")
    if questions:
        selected = st.selectbox("Choose a question", questions, format_func=lambda question: question.stem)
        st.caption(f"Content status: {selected.review_status.replace('_', ' ')}")
        answer = st.radio("Select your answer", selected.options, format_func=lambda option: option.text,
                          key=f"answer-{selected.id}")
        if st.button("Check answer", key=f"check-{selected.id}"):
            st.session_state[f"checked-{selected.id}"] = True
            st.session_state[f"chosen-{selected.id}"] = answer.id
        if st.session_state.get(f"checked-{selected.id}", False):
            chosen = st.session_state.get(f"chosen-{selected.id}")
            marking = check_mcq_answer(
                selected_option_id=chosen,
                correct_option_id=selected.correct_option_id,
                review_status=selected.review_status,
            )
            if not marking["markable"]:
                st.warning(marking["message"])
            elif marking["status"] == "provisional_key":
                st.info(marking["message"])
                st.caption(marking["caveat"])
            else:
                st.success(marking["message"]) if marking["correct"] else st.error(marking["message"])
            st.markdown("**Explanation**")
            st.write(selected.explanation)
            if selected.source_url:
                st.markdown(f"[Source / further reading]({selected.source_url})")
    st.divider()
    st.subheader("OSCE and viva cases")
    cases = load_cases()
    if cases:
        case = st.selectbox("Choose a case", cases, format_func=lambda item: item.title)
        st.caption(f"Case content status: {case.review_status.replace('_', ' ')}")
        st.markdown(f"**Scenario**\n\n{case.scenario}")
        st.markdown("**Your tasks**")
        for task in case.tasks:
            st.write("• " + task)
        with st.expander("Examiner discussion points"):
            for point in case.discussion_points:
                st.write("• " + point)

    st.divider()
    st.subheader("Short-answer and MEQ practice")
    written_assessments = load_assessments()
    if not written_assessments:
        st.info("No reviewed short-answer or MEQ assessments have been added yet.")
    for assessment in written_assessments:
        with st.expander(
            str(assessment.get("prompt", "Written assessment"))
            + " · " + assessment.get("assessment_type", "assessment").upper()
            + " · " + str(assessment.get("source_page", "?")),
        ):
            st.caption(
                str(assessment.get("source_title", "Past paper"))
                + " · Editorial status: " + assessment.get("review_status", "draft")
            )
            if assessment.get("scenario"):
                st.write(assessment["scenario"])
            with st.form("written-practice-" + assessment["id"]):
                written_answers = {}
                for part in assessment.get("parts", []):
                    st.markdown("**" + part["prompt"] + "**")
                    written_answers[part["id"]] = st.text_area(
                        "Your answer",
                        key="written-answer-" + assessment["id"] + "-" + part["id"],
                        height=110,
                    )
                submitted_written = st.form_submit_button("Check written answer")
                submitted_ai_written = st.form_submit_button("AI-assisted rubric review")
            if submitted_written or submitted_ai_written:
                st.session_state["written-answers-" + assessment["id"]] = written_answers
                st.session_state.pop("written-ai-result-" + assessment["id"], None)
                if submitted_written:
                    result = check_assessment_answers(assessment, written_answers)
                    st.session_state["written-result-" + assessment["id"]] = result
                if submitted_ai_written:
                    st.session_state.pop("written-result-" + assessment["id"], None)
                    try:
                        ai_result = grade_assessment_answers(assessment, written_answers)
                        st.session_state["written-ai-result-" + assessment["id"]] = ai_result
                    except GenerationNotConfigured as exc:
                        st.error(str(exc))
                    except (AnswerGradingError, ValueError) as exc:
                        st.error("AI review could not be safely completed: " + str(exc))
            result = st.session_state.get("written-result-" + assessment["id"])
            if result:
                st.metric(
                    "Automated rubric screen",
                    str(result["marks_awarded"]) + " / " + str(result["marks_available"]) + " marks",
                    str(result["percentage"]) + "%",
                )
                st.warning(
                    "Provisional keyword-based marking only. The checker cannot judge clinical meaning "
                    "or recognize every equivalent phrase. Review all unmatched points manually."
                )
                for part_result in result["parts"]:
                    st.markdown("**" + part_result["prompt"] + "**")
                    st.write(
                        str(part_result.get("marks_awarded", 0))
                        + " / " + str(part_result.get("marks_available", 0)) + " marks"
                    )
                    for point in part_result.get("points", []):
                        status = "Matched" if point["marks_awarded"] else "Needs manual check"
                        st.write(
                            status + ": " + point["point"]
                            + " (" + str(point["marks_awarded"])
                            + "/" + str(point["marks_available"]) + ")"
                        )
                st.caption("This score is a study aid, not an official examination mark.")

            ai_result = st.session_state.get("written-ai-result-" + assessment["id"])
            if ai_result:
                st.warning(ai_result["warning"])
                st.metric(
                    "AI-suggested marks — provisional",
                    str(ai_result["marks_awarded"]) + " / " + str(ai_result["marks_available"]),
                    str(ai_result["percentage"]) + "%",
                )
                for part_result in ai_result["parts"]:
                    st.markdown("**" + part_result["prompt"] + "**")
                    st.caption("Model confidence: " + part_result["confidence"])
                    for uncertainty in part_result["uncertainties"]:
                        st.write("Uncertainty: " + uncertainty)
                    for point in part_result["points"]:
                        st.write(
                            str(point["marks_awarded"]) + "/" + str(point["marks_available"])
                            + " · " + point["point"]
                        )
                        st.caption(point["reason"])
                        if point["evidence_from_answer"]:
                            st.caption("Answer evidence: " + point["evidence_from_answer"])
                        if point["uncertainty"] != "none":
                            st.warning("Uncertainty: " + point["uncertainty"])
                st.caption(
                    "AI suggestions are not saved as official grades. A human examiner must "
                    "check the clinical reasoning and decide the final mark."
                )
elif page == "Flashcards":
    st.subheader("Create a flashcard")
    with st.form("new_card"):
        card_id = st.text_input("Unique card ID", placeholder="uro-001")
        card_specialty = st.text_input("Specialty ID", value="urology")
        card_topic = st.text_input("Topic ID", placeholder="acute-retention")
        prompt = st.text_area("Prompt / front")
        answer_text = st.text_area("Answer / back")
        source_url = st.text_input("Source URL (optional)")
        submitted = st.form_submit_button("Save flashcard")
    if submitted:
        if not all(value.strip() for value in (card_id, card_specialty, card_topic, prompt, answer_text)):
            st.error("Complete the ID, specialty, topic, prompt, and answer.")
        else:
            try:
                save_flashcard({
                    "id": card_id.strip(),
                    "specialty_id": card_specialty.strip(),
                    "topic_id": card_topic.strip(),
                    "prompt": prompt.strip(),
                    "answer": answer_text.strip(),
                    "source_url": source_url.strip() or None,
                }, learner_id=learner_id)
                st.success("Flashcard saved. It is now in your review queue.")
            except ValueError as exc:
                st.error(str(exc))
    st.metric("Cards due today", stats["due_cards"])
    cards = due_cards(learner_id=learner_id)
    if not cards:
        st.info("No cards due. Add a card above to start a review habit.")
    for card in cards:
        with st.expander(card["prompt"]):
            st.write(card["answer"])
            st.caption(f"Topic: {card['topic_id']} · Due: {card['due_date']}")
            grade = st.select_slider("Recall quality (0 = forgot, 5 = effortless)",
                                     options=[0, 1, 2, 3, 4, 5], value=3,
                                     key=f"grade-{card['id']}")
            if st.button("Record review", key=f"review-{card['id']}"):
                state = ReviewState(card_id=card["id"], repetitions=card["repetitions"],
                                    interval_days=card["interval_days"],
                                    ease_factor=card["ease_factor"], due_date=card["due_date"])
                updated = schedule_review(state, grade)
                record_review(card["id"], grade, updated, learner_id=learner_id)
                st.success(f"Review saved. Next due: {updated.due_date}")
                st.rerun()
elif page == "Progress":
    st.subheader("Learner progress")
    p1, p2, p3, p4 = st.columns(4)
    bank_stats = question_bank_stats(learner_id=learner_id)
    p1.metric("Topics tracked", stats["topics_tracked"])
    p2.metric("Topics mastered", stats["topics_mastered"])
    p3.metric("Reviews completed", stats["reviews_completed"])
    p4.metric("Question accuracy", f'{bank_stats["accuracy_percent"]}%')
    st.markdown("#### Question performance by topic")
    topic_results = question_topic_performance(learner_id=learner_id)
    if topic_results:
        st.dataframe(topic_results, use_container_width=True, hide_index=True)
    else:
        st.info("Complete reviewed question-bank items to see topic-level accuracy.")
    with st.form("topic_progress"):
        topic_ids = [row["topic_id"] for row in flatten_topics(curriculum)]
        chosen_topic = st.selectbox("Topic", topic_ids)
        status = st.selectbox("Status", ["not_started", "learning", "reviewing", "mastered"])
        confidence = st.slider("Confidence", 0, 5, 2)
        progress_submit = st.form_submit_button("Update progress")
    if progress_submit:
        set_topic_progress(chosen_topic, status, confidence, learner_id=learner_id)
        st.success("Progress updated.")
    progress_rows = topic_progress(learner_id=learner_id)
    if progress_rows:
        st.dataframe(progress_rows, use_container_width=True, hide_index=True)
elif page == "AI Studio":
    st.subheader("Evidence-grounded exam-card generator")
    status = provider_status()
    if status["configured"]:
        st.success(f"AI authoring configured · {status['model']} · PubMed evidence retrieval")
    else:
        st.warning(
            "Local Ollama authoring is not configured. Start Ollama and set OLLAMA_BASE_URL "
            "and USIPHU_OLLAMA_MODEL in the server environment."
        )
    st.caption(
        "Generation retrieves PubMed abstracts and asks the configured model to draft cards. "
        "Every result remains a draft and must be checked against full sources and local protocols."
    )
    topic_choices = [
        (row["specialty_id"], row["topic_id"], row["specialty"], row["topic"])
        for row in flatten_topics(curriculum)
    ]
    selected_topic = st.selectbox(
        "Choose a curriculum topic",
        topic_choices,
        format_func=lambda item: f"{item[2]} · {item[3]}",
        key="generator-topic",
    )
    exam_format = st.selectbox(
        "Examination format",
        ["mixed", "mcq", "short_answer", "clinical_case", "osce", "viva", "emq"],
        format_func=lambda value: {
            "mixed": "Mixed assessment", "mcq": "Single-best-answer MCQ",
            "short_answer": "Short answer", "clinical_case": "Clinical case",
            "osce": "OSCE station", "viva": "Viva / oral examination",
            "emq": "Extended matching questions",
        }[value],
    )
    evidence_limit = st.slider("PubMed records per learning objective", 1, 10, 5)
    if st.button(
        "Generate evidence-grounded draft cards",
        key="generate-evidence-grounded-cards",
        disabled=not status["configured"],
    ):
        try:
            with st.spinner("Searching PubMed and drafting cards..."):
                result = generate_topic_cards(
                    selected_topic[0], selected_topic[1], evidence_limit=evidence_limit,
                    exam_format=exam_format,
                )
            st.session_state["generated_card_result"] = result
        except GenerationNotConfigured as exc:
            st.error(str(exc))
        except KeyError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Generation failed safely; no card was saved: {exc}")

    generated = st.session_state.get("generated_card_result")
    if generated:
        st.write(
            f"Objectives: {generated['total_objectives']} · "
            f"Drafts passing automated checks: {generated['draft_cards']} · "
            f"Evidence/quality gated: {generated['rejected_or_evidence_gated']}"
        )
        accepted = [
            item["card"] for item in generated["results"]
            if item.get("valid") and item.get("card")
        ]
        if accepted and st.button("Save accepted cards to draft review", key="save-generated-drafts"):
            saved = save_generated_drafts(accepted, learner_id=learner_id)
            st.success(f"Saved {saved} new draft(s). They are not in your flashcard review queue.")
        for item in generated["results"]:
            card = item.get("card")
            heading = card["prompt"] if card else item.get("reason", item.get("status", "Generation result"))
            with st.expander(f"{item.get('status', 'result')}: {heading}", expanded=bool(card)):
                if card:
                    st.write(card["answer"])
                    st.caption(
                        f"{card['card_type']} · {card.get('difficulty', 'difficulty not supplied')} · "
                        "DRAFT — clinical and exam review required"
                    )
                    if card.get("station_tasks"):
                        st.markdown("**Candidate tasks**")
                        for task in card["station_tasks"]:
                            st.write("• " + task)
                    if card.get("marking_criteria"):
                        st.markdown("**Marking criteria**")
                        for criterion in card["marking_criteria"]:
                            st.write("• " + criterion)
                    if card.get("viva_questions"):
                        st.markdown("**Viva questions**")
                        for item in card["viva_questions"]:
                            st.write("**" + item.get("question", "Question") + "**")
                            st.write(item.get("expected_answer", ""))
                    if card.get("emq_items"):
                        st.markdown("**Extended matching items**")
                        for item in card["emq_items"]:
                            st.write(item["stem"] + " → " + item["correct_option_id"])
                    if card.get("options"):
                        for option in card["options"]:
                            prefix = "✓ " if option["id"] == card.get("correct_option_id") else "• "
                            st.write(prefix + option["text"])
                    packet = item.get("review_packet") or card.get("review_packet")
                    if packet:
                        with st.expander("Clinical and examination review checklist"):
                            st.caption(packet["automated_validation_scope"])
                            st.markdown("**Clinical and educational checks**")
                            for check in packet["common_checks"]:
                                st.write("• " + check)
                            st.markdown("**Assessment-format checks**")
                            for check in packet["format_checks"]:
                                st.write("• " + check)
                            st.markdown("**Specialty safety checks**")
                            for check in packet["specialty_safety_checks"]:
                                st.write("• " + check)
                            st.warning("Human clinical review and faculty exam validation are required. No automatic approval.")
                    st.markdown("**Evidence sources**")
                    for source in card.get("evidence_sources", []):
                        st.markdown(
                            f"- [{source['source_title']}]({source['source_url']}) "
                            f"({source['source_date']}; {source['evidence_tier']})"
                        )
                    for claim in card.get("evidence_claims", []):
                        st.caption(f"Evidence claim: {claim['claim']}")
                else:
                    st.warning(item.get("reason", "; ".join(item.get("errors", []))))
                    for source in item.get("evidence", []):
                        st.markdown(f"- [{source['source_title']}]({source['source_url']})")

    st.divider()
    st.subheader("Saved generated drafts")
    drafts = generated_drafts(learner_id=learner_id)
    st.caption(f"{len(drafts)} draft(s) stored separately from the approved flashcard queue.")
    for draft in drafts:
        with st.expander(draft["prompt"]):
            st.write(draft["answer"])
            st.caption("DRAFT — not approved for learner flashcard review")
            packet = draft.get("review_packet")
            if packet:
                st.markdown("**Review requirements**")
                for check in packet["specialty_safety_checks"]:
                    st.write("• " + check)
                for check in packet["format_checks"]:
                    st.write("• " + check)
            for source in draft.get("evidence_sources", []):
                st.markdown(f"- [{source['source_title']}]({source['source_url']})")

elif page == "Pilot Dashboard":
    report = build_pilot_validation_report()
    totals = report["totals"]
    st.subheader("Past-paper pilot validation")
    st.write(
        "Measure what the extraction and review workflow actually achieves on uploaded papers. "
        "Only saved human checks count as transcription validation; AI suggestions never count as verified answers."
    )
    st.caption("Pilot sample targets: 50 MCQs and 10 MEQ pages. These are review targets, not accuracy claims.")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Source papers", totals["source_files"])
    k2.metric("MCQ candidates", totals["mcq_candidates"])
    k3.metric("MEQ pages", totals["meq_pages"])
    k4.metric("AI evidence reviews", totals["ai_review_runs"])

    mcq_target = report["targets"]["mcq_review_target"]
    meq_target = report["targets"]["meq_review_target"]
    p1, p2 = st.columns(2)
    mcq_progress = min(1.0, totals["mcq_transcription_checked"] / mcq_target) if mcq_target else 0.0
    meq_progress = min(1.0, totals["meq_transcription_checked"] / meq_target) if meq_target else 0.0
    p1.progress(
        mcq_progress,
        text=f"MCQ source checks: {totals['mcq_transcription_checked']} / {mcq_target}",
    )
    p2.progress(
        meq_progress,
        text=f"MEQ page checks: {totals['meq_transcription_checked']} / {meq_target}",
    )

    st.markdown("#### Extraction transcription validation")
    t1, t2, t3, t4 = st.columns(4)
    transcription = report["transcription"]
    t1.metric("MCQs checked", transcription["mcq_checked"])
    t2.metric("MCQs confirmed unchanged", transcription["mcq_confirmed_as_extracted"])
    t3.metric("MCQs corrected", transcription["mcq_corrected"])
    t4.metric(
        "MCQ unchanged rate",
        f"{transcription['mcq_confirmation_rate_percent']}%"
        if transcription["mcq_confirmation_rate_percent"] is not None else "Not measured",
    )
    w1, w2, w3 = st.columns(3)
    w1.metric("Written items checked", transcription["written_checked"])
    w2.metric("Written items corrected", transcription["written_corrected"])
    w3.metric(
        "Written unchanged rate",
        f"{transcription['written_confirmation_rate_percent']}%"
        if transcription["written_confirmation_rate_percent"] is not None else "Not measured",
    )
    st.caption(
        "A saved unchanged transcription means a reviewer confirmed it against the original paper. "
        "A correction means the reviewer changed the extracted text. Unreviewed candidates are excluded."
    )

    st.markdown("#### Answer-key review outcomes")
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Human-verified keys", totals["answer_verified"])
    a2.metric("AI reviews contradicting existing key", totals["ai_key_contradictions"])
    a3.metric("Reviewed, awaiting approval", totals["reviewed_pending_approval"])
    a4.metric("Approved candidates", totals["approved_candidates"])
    agree1, agree2, agree3 = st.columns(3)
    agree1.metric("Human decisions compared with AI", totals["reviewer_ai_comparisons"])
    agree2.metric("Human/AI suggestion agreement", totals["reviewer_ai_agreements"])
    agree3.metric("Human/AI suggestion disagreement", totals["reviewer_ai_disagreements"])
    st.caption(
        "Agreement compares a human-verified answer with the AI's proposed option; it is not a measure of correctness."
    )
    verdict_rows = [
        {"AI evidence verdict": key.replace("_", " ").title(), "Reviews": value}
        for key, value in report["ai_evidence_verdict_counts"].items()
    ]
    key_rows = [
        {"Existing key assessment": key.replace("_", " ").title(), "Reviews": value}
        for key, value in report["existing_key_assessment_counts"].items()
    ]
    if verdict_rows or key_rows:
        v1, v2 = st.columns(2)
        with v1:
            st.markdown("**Online evidence verdicts**")
            if verdict_rows:
                st.dataframe(verdict_rows, use_container_width=True, hide_index=True)
            else:
                st.info("No AI evidence reviews recorded yet.")
        with v2:
            st.markdown("**Assessment of the existing paper key**")
            if key_rows:
                st.dataframe(key_rows, use_container_width=True, hide_index=True)
            else:
                st.info("No answer-key comparisons recorded yet.")
    else:
        st.info("Run the AI open-access evidence comparison in Review Editor to populate evidence metrics.")

    st.markdown("#### Retrieved source coverage")
    quality = report["evidence_quality"]
    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Unique articles", quality["unique_articles"])
    e2.metric("Full-text articles", quality["full_text_articles"])
    e3.metric("Abstract-only articles", quality["abstract_only_articles"])
    e4.metric(
        "Full-text share",
        f"{quality['full_text_percent']}%" if quality["full_text_percent"] is not None else "Not measured",
    )
    st.caption(quality["interpretation"])
    st.write(
        f"Metadata complete (title, URL, date and journal): {quality['metadata_complete_articles']} · "
        f"Publication date available: {quality['dated_articles']} · "
        f"Mean unique articles per AI review: {quality['mean_articles_per_ai_review']}"
    )

    st.markdown("#### Per-paper pilot results")
    if report["source_rows"]:
        st.dataframe(report["source_rows"], use_container_width=True, hide_index=True)
    else:
        st.info("No uploaded source papers have been extracted yet. Add the two pilot papers in Question Bank.")
    with st.expander("Candidate-level audit trail"):
        if report["candidate_rows"]:
            st.dataframe(report["candidate_rows"], use_container_width=True, hide_index=True)
        else:
            st.info("Candidate-level review details will appear after extraction.")

    with st.expander("How to interpret these metrics and current limitations"):
        for limitation in report["limitations"]:
            st.write("• " + limitation)
        st.write(
            "The dashboard does not score clinical evidence quality, independently determine the correct "
            "medical answer, or validate segmentation automatically. It reports recorded workflow activity."
        )
    st.download_button(
        "Download pilot validation report (JSON)",
        data=json.dumps(report, ensure_ascii=False, indent=2),
        file_name="usiphu-pilot-validation-report.json",
        mime="application/json",
        type="secondary",
    )

elif page == "Review Editor":
    st.subheader("Question review editor")
    st.write("A dedicated editorial workspace for extracted MCQs, short-answer questions and modified essay questions.")
    mcq_candidates = [item for item in list_review_candidates() if item.get("question_type") == "single_best_answer"]
    written_candidates = list_non_mcq_candidates()
    all_candidates = [
        item for item in mcq_candidates if item.get("review_state") != "approved"
    ] + [
        item for item in written_candidates if item.get("review_state") != "approved"
    ]
    mcq_pending = sum(item.get("question_type") == "single_best_answer" for item in all_candidates)
    short_pending = sum(item.get("assessment_type") == "short_answer" for item in all_candidates)
    meq_pending = sum(item.get("assessment_type") == "meq" for item in all_candidates)
    m1, m2, m3 = st.columns(3)
    m1.metric("MCQs", mcq_pending)
    m2.metric("Short answers", short_pending)
    m3.metric("MEQ pages", meq_pending)
    st.caption("Every item retains its source and page. Nothing is published into the learner bank until a reviewer saves and explicitly approves it.")
    if not all_candidates:
        st.info("No extracted candidates are waiting. Upload a paper in Question Bank and run extraction first.")
    else:
        type_filter = st.selectbox(
            "Candidate type",
            ["All types", "MCQ", "Short answer", "MEQ"],
            key="editor-type-filter",
        )
        filtered_candidates = [
            item for item in all_candidates
            if type_filter == "All types"
            or (type_filter == "MCQ" and item.get("question_type") == "single_best_answer")
            or (type_filter == "Short answer" and item.get("assessment_type") == "short_answer")
            or (type_filter == "MEQ" and item.get("assessment_type") == "meq")
        ]
        source_filter = st.selectbox(
            "Source paper",
            ["All sources", *sorted({item.get("source_title") or item.get("source_filename") or "Source" for item in filtered_candidates})],
            key="editor-source-filter",
        )
        filtered_candidates = [
            item for item in filtered_candidates
            if source_filter == "All sources"
            or (item.get("source_title") or item.get("source_filename") or "Source") == source_filter
        ]
        if filtered_candidates:
            labels = {
                item["candidate_id"]: (
                    str(item.get("source_title") or item.get("source_filename") or "Source")
                    + " · p." + str(item.get("source_page", "?"))
                    + " · " + item["candidate_id"]
                    + " · " + ("MCQ" if item.get("question_type") == "single_best_answer" else item.get("assessment_type", "candidate").replace("_", " ").upper())
                )
                for item in filtered_candidates
            }
            selected_id = st.selectbox(
                "Select candidate",
                list(labels),
                format_func=lambda value: labels[value],
                key="editor-candidate",
            )
            selected = next(item for item in filtered_candidates if item["candidate_id"] == selected_id)
            with st.expander("Original extracted content and provenance", expanded=True):
                st.caption(
                    str(selected.get("source_filename") or "Source file")
                    + " · pages " + str(selected.get("source_page", "?"))
                    + ("–" + str(selected.get("source_page_end")) if selected.get("source_page_end") != selected.get("source_page") else "")
                )
                st.text(selected.get("raw_text") or selected.get("stem_extracted") or "")
                source_record = next(
                    (item for item in list_sources() if item.get("source_id") == selected.get("source_id")),
                    None,
                )
                if source_record:
                    original_path = DEFAULT_SOURCE_DIR / source_record["stored_filename"]
                    if original_path.is_file():
                        st.download_button(
                            "Download original source paper",
                            data=original_path.read_bytes(),
                            file_name=source_record.get("original_filename", "source-paper"),
                            mime="application/pdf" if original_path.suffix.lower() == ".pdf" else "application/octet-stream",
                            key="download-review-source-" + selected_id,
                        )
                if selected.get("original_extracted_stem") is not None:
                    st.caption("First machine-extracted transcription (kept for audit):")
                    st.text(selected.get("original_extracted_stem", ""))
            specialty_by_id = {item.id: item for item in curriculum.specialties}
            specialty_ids = list(specialty_by_id)
            default_specialty = selected.get("specialty_id")
            if default_specialty not in specialty_by_id:
                label = str(selected.get("specialty_label", "")).casefold()
                default_specialty = next(
                    (item.id for item in curriculum.specialties if item.title.casefold() == label),
                    specialty_ids[0],
                )
            current_topics = [
                topic.id
                for domain in specialty_by_id[default_specialty].domains
                for topic in domain.topics
            ]
            default_topic = selected.get("topic_id")
            if default_topic not in current_topics:
                default_topic = current_topics[0]
            if selected.get("question_type") == "single_best_answer":
                existing_options = {str(item.get("id", "")).lower(): item.get("text", "") for item in selected.get("options", [])}
                stem_widget_key = "dedicated-stem-" + selected_id
                if stem_widget_key not in st.session_state:
                    st.session_state[stem_widget_key] = selected.get("stem_extracted") or ""
                for option_id in ["a", "b", "c", "d", "e"]:
                    option_widget_key = "dedicated-option-" + selected_id + "-" + option_id
                    if option_widget_key not in st.session_state:
                        st.session_state[option_widget_key] = existing_options.get(option_id, "")

                ai_review_state_key = "mcq-ai-review-" + selected_id
                if st.button(
                    "AI check extraction and compare answers with open-access sources",
                    key="run-ai-mcq-review-" + selected_id,
                    help="Checks the transcription and compares every answer option with retrieved open-access medical sources. Suggestions remain unverified.",
                ):
                    try:
                        st.session_state[ai_review_state_key] = review_mcq_candidate(selected)
                        if reviewer_access:
                            try:
                                record_ai_review(selected_id, st.session_state[ai_review_state_key])
                            except (OSError, ValueError, KeyError) as audit_error:
                                st.warning("AI review completed but its audit record could not be saved: " + str(audit_error))
                        else:
                            st.info("AI review is available as a session preview; reviewer access is required to save it to the shared audit history.")
                    except GenerationNotConfigured as exc:
                        st.error(str(exc))
                    except (QuestionReviewError, ValueError) as exc:
                        st.error("AI source review could not be safely completed: " + str(exc))
                ai_review = st.session_state.get(ai_review_state_key)
                if ai_review:
                    with st.expander("AI source-check suggestions — not verified", expanded=True):
                        st.warning(ai_review["warning"])
                        transcription_review = ai_review["transcription"]
                        st.markdown("**Transcription check**")
                        st.caption("AI confidence: " + transcription_review["confidence"])
                        for issue in transcription_review["issues"]:
                            st.write("• " + issue)
                        st.text_area(
                            "Suggested corrected stem",
                            value=transcription_review["suggested_stem"],
                            height=100,
                            disabled=True,
                            key="ai-suggested-stem-display-" + selected_id,
                        )
                        for option in transcription_review["suggested_options"]:
                            st.write(option["id"].upper() + ". " + option["text"])
                        answer_review = ai_review["answer_review"]
                        st.markdown("**Answer-key check**")
                        suggestion = answer_review["suggested_option_id"]
                        st.write(
                            "Suggested option: " + (suggestion.upper() if suggestion else "No defensible suggestion")
                        )
                        st.caption(
                            "Basis: " + answer_review["basis"].replace("_", " ")
                            + " · confidence: " + answer_review["confidence"]
                        )
                        if answer_review["source_evidence"]:
                            st.write("Printed source evidence: " + answer_review["source_evidence"])
                        if answer_review["rationale"]:
                            st.write(answer_review["rationale"])
                        for uncertainty in answer_review["uncertainties"]:
                            st.warning(uncertainty)
                        if st.button(
                            "Use suggested transcription in editor",
                            key="apply-ai-mcq-transcription-" + selected_id,
                        ):
                            st.session_state[stem_widget_key] = transcription_review["suggested_stem"]
                            for option in transcription_review["suggested_options"]:
                                st.session_state[
                                    "dedicated-option-" + selected_id + "-" + option["id"]
                                ] = option["text"]
                            st.rerun()
                    internet_review = ai_review.get("internet_evidence_review", {})
                    with st.expander("Open-access internet evidence comparison", expanded=True):
                        st.warning(
                            "This is an AI evidence summary, not a verified answer key. "
                            "Sources are retrieved from Europe PMC / PubMed Central and may not include "
                            "all relevant guidelines or local protocols."
                        )
                        verdict_labels = {
                            "supported": "Evidence supports a best answer",
                            "contradicted": "Evidence contradicts the proposed answer",
                            "mixed": "Evidence is conflicting",
                            "insufficient_evidence": "Insufficient open-access evidence",
                        }
                        st.markdown("**Overall finding:** " + verdict_labels.get(
                            internet_review.get("verdict"), "Evidence review unavailable"
                        ))
                        existing_key = internet_review.get("existing_key_option_id")
                        existing_assessment = internet_review.get("existing_key_assessment", "uncertain")
                        st.write(
                            "Existing paper key: "
                            + (str(existing_key).upper() if existing_key else "not supplied")
                            + " · Evidence assessment: " + str(existing_assessment).replace("_", " ")
                        )
                        proposed = internet_review.get("proposed_option_id")
                        st.write(
                            "Evidence-based AI suggestion: "
                            + (str(proposed).upper() if proposed else "No defensible option")
                        )
                        if internet_review.get("summary"):
                            st.write(internet_review["summary"])
                        if proposed and proposed in [item.get("id") for item in selected.get("options", [])]:
                            if st.button(
                                "Select evidence-suggested option " + proposed.upper() + " in answer editor (still unverified)",
                                key="apply-internet-answer-" + selected_id,
                            ):
                                st.session_state["dedicated-answer-key-" + selected_id] = proposed
                                st.rerun()
                        for option_review in internet_review.get("option_assessments", []):
                            st.markdown(
                                "**Option " + option_review["option_id"].upper() + " — "
                                + option_review["assessment"].replace("_", " ").title() + "**"
                            )
                            if option_review.get("reasoning"):
                                st.write(option_review["reasoning"])
                            for citation in option_review.get("citations", []):
                                st.markdown(
                                    "> " + citation["quote"] + "\n\n"
                                    + "[" + citation["source_title"] + "](" + citation["source_url"] + ")"
                                    + " · " + str(citation.get("source_date", "date unavailable"))
                                )
                        if internet_review.get("conflicts"):
                            st.markdown("**Conflicts and limitations**")
                            for conflict in internet_review["conflicts"]:
                                st.write("• " + conflict)
                        if internet_review.get("sources"):
                            st.markdown("**Retrieved open-access sources**")
                            for source in internet_review["sources"]:
                                st.markdown(
                                    "- [" + source["source_title"] + "](" + source["source_url"] + ")"
                                    + " · " + str(source.get("source_date", "date unavailable"))
                                    + " · " + str(source.get("journal") or "Journal not supplied")
                                    + " · " + ("full text" if source.get("full_text_available") else "abstract only")
                                )
                                if source.get("license"):
                                    st.caption("Licence: " + source["license"])
                        else:
                            st.info(
                                "No relevant open-access full-text article was retrieved. "
                                "The internet comparison did not verify the answer."
                            )
                with st.form("dedicated-mcq-editor-" + selected_id):
                    stem = st.text_area("Question stem", height=140, key=stem_widget_key)
                    option_values = {}
                    option_columns = st.columns(2)
                    for index, option_id in enumerate(["a", "b", "c", "d", "e"]):
                        option_values[option_id] = option_columns[index % 2].text_input(
                            "Option " + option_id.upper(),
                            key="dedicated-option-" + selected_id + "-" + option_id,
                        )
                    available_options = [key for key, value in option_values.items() if value.strip()]
                    prior_key = selected.get("correct_option_id")
                    answer_choices = ["Not verified", *available_options]
                    answer_widget_key = "dedicated-answer-key-" + selected_id
                    if answer_widget_key not in st.session_state:
                        st.session_state[answer_widget_key] = (
                            prior_key if prior_key in available_options else "Not verified"
                        )
                    answer = st.selectbox(
                        "Answer key",
                        answer_choices,
                        format_func=lambda value: "Not verified" if value == "Not verified" else value.upper(),
                        key=answer_widget_key,
                    )
                    specialty_id = st.selectbox(
                        "Specialty", specialty_ids,
                        index=specialty_ids.index(default_specialty),
                        format_func=lambda value: specialty_by_id[value].title,
                    )
                    topic_rows = [
                        (topic.id, domain.title, topic.title)
                        for domain in specialty_by_id[specialty_id].domains
                        for topic in domain.topics
                    ]
                    topic_ids = [row[0] for row in topic_rows]
                    topic_id = st.selectbox(
                        "Curriculum topic", topic_ids,
                        index=topic_ids.index(default_topic) if default_topic in topic_ids else 0,
                        format_func=lambda value: next(row[1] + " · " + row[2] for row in topic_rows if row[0] == value),
                    )
                    explanation = st.text_area("Explanation / rationale", value=selected.get("explanation") or "")
                    reviewer = st.text_input("Reviewer", value=selected.get("reviewer") or "")
                    verified = st.checkbox(
                        "I independently verified the answer against the source or a reliable reference.",
                        value=bool(selected.get("answer_verified_by_reviewer")),
                    )
                    action = st.radio("Action", ["Save review draft", "Approve into question bank"], horizontal=True)
                    submitted = st.form_submit_button("Save MCQ review", type="primary")
                if submitted:
                    if not reviewer_access:
                        st.error("Your account is not authorized to review shared content. Configure USIPHU_REVIEWER_SUBJECTS.")
                    else:
                        try:
                            options = [{"id": key, "text": value.strip()} for key, value in option_values.items() if value.strip()]
                            save_candidate_review(
                                selected_id, stem=stem, options=options,
                                specialty_id=specialty_id, topic_id=topic_id,
                                correct_option_id=None if answer == "Not verified" else answer,
                                explanation=explanation, reviewer=reviewer,
                                answer_verified=verified,
                            )
                            if action == "Approve into question bank":
                                promoted = approve_candidate(selected_id)
                                st.success("Promoted " + promoted["id"] + " as an editorial draft.")
                            else:
                                st.success("Review draft saved; not yet added to the learner bank.")
                            st.rerun()
                        except (ValueError, KeyError) as exc:
                            st.error(str(exc))
            else:
                is_meq = selected.get("assessment_type") == "meq"
                old_parts = selected.get("review_parts") or []
                with st.form("dedicated-written-editor-" + selected_id):
                    prompt = st.text_input(
                        "Case title" if is_meq else "Question prompt",
                        value=selected.get("review_prompt") or (
                            "Modified essay question" if is_meq else selected.get("stem_extracted", "")
                        ),
                    )
                    corrected_source_text = st.text_area(
                        "Corrected source transcription (keep wording faithful to the paper)",
                        value=selected.get("reviewed_source_text") or selected.get("raw_text", ""),
                        height=220,
                    )
                    scenario = st.text_area(
                        "Clinical scenario / source context",
                        value=selected.get("review_scenario") or (selected.get("raw_text", "") if is_meq else ""),
                        height=170,
                    )
                    specialty_id = st.selectbox(
                        "Specialty", specialty_ids,
                        index=specialty_ids.index(default_specialty),
                        format_func=lambda value: specialty_by_id[value].title,
                    )
                    topic_rows = [
                        (topic.id, domain.title, topic.title)
                        for domain in specialty_by_id[specialty_id].domains
                        for topic in domain.topics
                    ]
                    topic_ids = [row[0] for row in topic_rows]
                    topic_id = st.selectbox(
                        "Curriculum topic", topic_ids,
                        index=topic_ids.index(default_topic) if default_topic in topic_ids else 0,
                        format_func=lambda value: next(row[1] + " · " + row[2] for row in topic_rows if row[0] == value),
                    )
                    part_count = st.number_input(
                        "Number of answer parts",
                        min_value=1, max_value=8,
                        value=min(8, max(1, len(old_parts) or 1)),
                        step=1,
                    )
                    parts_to_save = []
                    for part_index in range(int(part_count)):
                        old_part = old_parts[part_index] if part_index < len(old_parts) else {}
                        with st.expander("Part " + str(part_index + 1), expanded=True):
                            part_prompt = st.text_area(
                                "Part prompt",
                                value=old_part.get("prompt") or (
                                    selected.get("stem_extracted", "") if not is_meq and part_index == 0
                                    else "Part " + str(part_index + 1) + " — edit this prompt"
                                ),
                                key="editor-part-prompt-" + selected_id + "-" + str(part_index),
                            )
                            old_rubric = old_part.get("marking_points", [])
                            rubric_default = "\n".join(
                                str(point.get("point", "")) + " | "
                                + "; ".join(point.get("acceptable_terms", [])) + " | "
                                + str(point.get("marks", 1))
                                for point in old_rubric
                            )
                            rubric_text = st.text_area(
                                "Marking rubric (one line per point: description | accepted phrases separated by ; | marks)",
                                value=rubric_default,
                                height=110,
                                key="editor-rubric-" + selected_id + "-" + str(part_index),
                            )
                        points = []
                        for line in rubric_text.splitlines():
                            if not line.strip():
                                continue
                            columns = [value.strip() for value in line.split("|")]
                            if len(columns) != 3:
                                continue
                            try:
                                marks = int(columns[2])
                            except ValueError:
                                marks = 1
                            points.append({
                                "point": columns[0],
                                "acceptable_terms": [term.strip() for term in columns[1].split(";") if term.strip()],
                                "marks": marks,
                            })
                        parts_to_save.append({
                            "id": "part-" + str(part_index + 1),
                            "prompt": part_prompt,
                            "marking_points": points,
                        })
                    reviewer = st.text_input("Reviewer", value=selected.get("reviewer") or "")
                    rubric_verified = st.checkbox(
                        "I checked the marking points and acceptable variants against a reliable source.",
                        value=bool(selected.get("rubric_verified_by_reviewer")),
                    )
                    action = st.radio("Action", ["Save review draft", "Approve assessment"], horizontal=True)
                    submitted = st.form_submit_button("Save assessment review", type="primary")
                if submitted:
                    if not reviewer_access:
                        st.error("Your account is not authorized to review shared content. Configure USIPHU_REVIEWER_SUBJECTS.")
                    else:
                        try:
                            saved = save_non_mcq_review(
                                selected_id,
                                assessment_type=selected["assessment_type"],
                                prompt=prompt,
                                scenario=scenario,
                                parts=parts_to_save,
                                specialty_id=specialty_id,
                                topic_id=topic_id,
                                reviewer=reviewer,
                                rubric_verified=rubric_verified,
                                corrected_source_text=corrected_source_text,
                                approve=action == "Approve assessment",
                            )
                            st.success(
                                "Assessment promoted to the practice checker." if action == "Approve assessment"
                                else "Assessment review draft saved; not yet in the learner practice bank."
                            )
                            st.rerun()
                        except (ValueError, KeyError) as exc:
                            st.error(str(exc))
        else:
            st.info("No candidates match this filter. Change the type/source or upload another paper.")
    st.divider()
    st.subheader("Reviewer guidance")
    st.caption(
        "Check every transcription against the downloaded original paper. AI may flag parsing "
        "mismatches and suggest an MCQ answer, but it cannot verify the official key. "
        "Original extraction is retained; human confirmation is required before approval."
    )

elif page == "Question Bank":
    st.subheader("Medical question bank")
    bank_questions = load_questions()
    bank_stats = question_bank_stats(learner_id=learner_id)
    q1, q2, q3 = st.columns(3)
    q1.metric("Questions available", len(bank_questions))
    q2.metric("Your attempts", bank_stats["attempts"])
    q3.metric("Your accuracy", f'{bank_stats["accuracy_percent"]}%')
    draft_total = sum(item.review_status == "draft" for item in bank_questions)
    if draft_total:
        st.warning(
            f"{draft_total} of {len(bank_questions)} questions are editorial drafts. "
            "They are usable for testing the workflow, not approved exam material."
        )

    specialties = sorted({item.specialty_id for item in bank_questions})
    bank_ids = sorted({item.bank_id for item in bank_questions})
    f1, f2, f3 = st.columns(3)
    specialty_filter = f1.selectbox("Specialty", ["All", *specialties], key="qb-specialty")
    specialty_questions = [
        item for item in bank_questions
        if specialty_filter == "All" or item.specialty_id == specialty_filter
    ]
    topics = sorted({item.topic_id for item in specialty_questions})
    topic_filter = f2.selectbox("Topic", ["All", *topics], key="qb-topic")
    bank_filter = f3.selectbox("Question bank", ["All", *bank_ids], key="qb-bank")
    f4, f5, f6 = st.columns(3)
    difficulty_filter = f4.selectbox(
        "Difficulty", ["All", "easy", "moderate", "hard"], key="qb-difficulty"
    )
    status_filter = f5.selectbox(
        "Editorial status", ["All", "draft", "clinically_reviewed", "exam_validated"],
        key="qb-status",
    )
    type_filter = f6.selectbox(
        "Question format",
        ["All", "single_best_answer", "extended_matching", "short_answer"],
        format_func=lambda value: {
            "All": "All formats",
            "single_best_answer": "Single best answer",
            "extended_matching": "Extended matching",
            "short_answer": "Short answer",
        }[value],
        key="qb-type",
    )
    search_term = st.text_input(
        "Search question text, tags or source", placeholder="e.g. hydronephrosis, vascular, past paper",
        key="qb-search",
    )
    filtered_questions = filter_questions(
        bank_questions,
        specialty_id=None if specialty_filter == "All" else specialty_filter,
        topic_id=None if topic_filter == "All" else topic_filter,
        difficulty=None if difficulty_filter == "All" else difficulty_filter,
        review_status=None if status_filter == "All" else status_filter,
        question_type=None if type_filter == "All" else type_filter,
        bank_id=None if bank_filter == "All" else bank_filter,
    )
    if search_term.strip():
        term = search_term.casefold().strip()
        filtered_questions = [
            item for item in filtered_questions
            if term in " ".join([
                item.stem, item.topic_id, item.specialty_id, item.source_title or "",
                " ".join(item.tags),
            ]).casefold()
        ]
    st.caption(f"{len(filtered_questions)} questions match these filters.")

    if filtered_questions:
        session_mode = st.radio(
            "How do you want to practise?",
            ["Practice one question", "Mock exam"],
            horizontal=True,
            key="qb-session-mode",
        )
        if session_mode == "Practice one question":
            selected_question = st.selectbox(
                "Choose a question",
                filtered_questions,
                format_func=lambda item: f"{item.id} · {item.stem[:100]}",
                key="qb-selected-question",
            )
            st.caption(
                f"{selected_question.specialty_id} / {selected_question.topic_id} · "
                f"{selected_question.difficulty.title()} · "
                f"{selected_question.review_status.replace('_', ' ').title()} · "
                f"Bank: {selected_question.bank_id}"
            )
            if selected_question.tags:
                st.caption("Tags: " + " · ".join(selected_question.tags))
            if selected_question.review_status == "draft":
                st.info("This item is an editorial draft. Its answer and explanation have not been clinically approved.")
            with st.container(border=True):
                st.markdown(f"#### {selected_question.stem}")
                result_key = f"qb-result-{selected_question.id}"
                previous_result = st.session_state.get(result_key)
                selected_option = st.radio(
                    "Select the single best answer",
                    selected_question.options,
                    format_func=lambda option: f"{option.id.upper()}. {option.text}",
                    key=f"qb-answer-{selected_question.id}",
                    disabled=previous_result is not None,
                )
                if st.button(
                    "Submit answer", type="primary",
                    key=f"qb-submit-{selected_question.id}",
                    disabled=previous_result is not None,
                ):
                    trusted_key = selected_question.review_status in {
                        "clinically_reviewed", "exam_validated",
                    }
                    if trusted_key:
                        correct = selected_option.id == selected_question.correct_option_id
                        record_question_attempt(
                            selected_question.id, selected_option.id, correct,
                            learner_id=learner_id,
                        )
                        st.session_state[result_key] = {
                            "selected": selected_option.id, "correct": correct,
                            "scored": True,
                        }
                    else:
                        st.session_state[result_key] = {
                            "selected": selected_option.id, "scored": False,
                        }
                result = st.session_state.get(result_key)
                if result:
                    if not result.get("scored"):
                        st.warning(
                            "Response not scored or added to accuracy statistics. "
                            "This question's answer key is still an editorial draft; "
                            "the key and explanation remain hidden until human review."
                        )
                    else:
                        if result["correct"]:
                            st.success("Correct answer")
                        else:
                            st.error("Incorrect answer")
                        correct_option = next(
                            item for item in selected_question.options
                            if item.id == selected_question.correct_option_id
                        )
                        st.markdown(f"**Correct answer:** {correct_option.text}")
                        st.markdown("**Explanation**")
                        st.write(selected_question.explanation)
                        if selected_question.source_url:
                            st.markdown(
                                f"[{selected_question.source_title or 'Source'}]({selected_question.source_url})"
                            )
                    if st.button("Retry this question", key=f"qb-retry-{selected_question.id}"):
                        del st.session_state[result_key]
                        st.rerun()
        else:
            st.caption("Mock exam mode is currently untimed. Answers and explanations stay hidden until submission.")
            exam_col1, exam_col2 = st.columns(2)
            exam_count = exam_col1.number_input(
                "Number of questions", min_value=1, max_value=len(filtered_questions),
                value=min(10, len(filtered_questions)), step=1, key="qb-exam-count",
            )
            random_order = exam_col2.toggle("Randomize order", value=True, key="qb-exam-random")
            if st.button("Start mock exam", type="primary", key="qb-start-exam"):
                exam_questions = list(filtered_questions)
                if random_order:
                    random.shuffle(exam_questions)
                exam_questions = exam_questions[:int(exam_count)]
                st.session_state["qb-exam"] = {
                    "ids": [item.id for item in exam_questions],
                    "answers": {},
                    "submitted": False,
                    "run_id": datetime.now(UTC).isoformat(),
                }
                st.rerun()

            exam = st.session_state.get("qb-exam")
            if exam:
                question_lookup = {item.id: item for item in bank_questions}
                exam_questions = [
                    question_lookup[item_id] for item_id in exam["ids"]
                    if item_id in question_lookup
                ]
                st.divider()
                st.markdown(f"#### Mock exam · {len(exam_questions)} questions")
                if not exam["submitted"]:
                    for number, item in enumerate(exam_questions, start=1):
                        st.markdown(f"**Question {number}**")
                        st.write(item.stem)
                        chosen = st.radio(
                            f"Answer {number}",
                            [None, *item.options],
                            format_func=lambda option: (
                                "— Choose an answer —"
                                if option is None else f"{option.id.upper()}. {option.text}"
                            ),
                            key=f"qb-exam-{exam['run_id']}-{item.id}",
                            index=0,
                        )
                        if chosen is not None:
                            exam["answers"][item.id] = chosen.id
                    st.session_state["qb-exam"] = exam
                    if st.button("Submit mock exam", type="primary", use_container_width=True):
                        for item in exam_questions:
                            selected_id = exam["answers"].get(item.id)
                            trusted_key = item.review_status in {
                                "clinically_reviewed", "exam_validated",
                            }
                            if selected_id and trusted_key:
                                record_question_attempt(
                                    item.id,
                                    selected_id,
                                    selected_id == item.correct_option_id,
                                    learner_id=learner_id,
                                    session_id=exam["run_id"],
                                )
                        exam["submitted"] = True
                        st.session_state["qb-exam"] = exam
                        st.rerun()
                else:
                    scoreable_questions = [
                        item for item in exam_questions
                        if item.review_status in {"clinically_reviewed", "exam_validated"}
                    ]
                    correct_total = sum(
                        exam["answers"].get(item.id) == item.correct_option_id
                        for item in scoreable_questions
                    )
                    answered_total = len(exam["answers"])
                    scoreable_total = len(scoreable_questions)
                    if scoreable_total:
                        percentage = round(100 * correct_total / scoreable_total)
                        st.metric(
                            "Mock exam result",
                            f"{correct_total}/{scoreable_total} · {percentage}%",
                        )
                    else:
                        st.info("No questions in this mock exam have a clinically reviewed or exam-validated answer key, so no score was calculated.")
                    st.caption(
                        f"{answered_total} of {len(exam_questions)} questions answered · "
                        f"{scoreable_total} questions eligible for scoring"
                    )
                    for number, item in enumerate(exam_questions, start=1):
                        selected_id = exam["answers"].get(item.id)
                        st.markdown(f"**Question {number}**")
                        st.write(item.stem)
                        if selected_id:
                            selected_text = next(option.text for option in item.options if option.id == selected_id)
                            st.write(f"Your answer: {selected_text}")
                        else:
                            st.write("Your answer: Not answered")
                        trusted_key = item.review_status in {
                            "clinically_reviewed", "exam_validated",
                        }
                        if trusted_key:
                            correct = selected_id == item.correct_option_id
                            st.markdown(
                                f"**{'Correct' if correct else 'Review this answer'}**"
                            )
                            correct_option = next(
                                option for option in item.options
                                if option.id == item.correct_option_id
                            )
                            st.write(f"Correct answer: {correct_option.text}")
                            st.caption(item.explanation)
                            if item.source_url:
                                st.markdown(f"[{item.source_title or 'Source'}]({item.source_url})")
                        else:
                            st.warning(
                                "Unscored: the answer key is still an editorial draft. "
                                "The stored key and explanation are hidden pending human review."
                            )
                        st.divider()
                    if st.button("Close exam review", key="qb-close-exam"):
                        st.session_state.pop("qb-exam", None)
                        st.rerun()
    else:
        st.info("No questions match the selected filters. Try broadening your search.")

    st.divider()
    st.markdown("#### Recent question attempts")
    history = question_attempt_history(learner_id=learner_id)
    if history:
        st.dataframe(
            [{
                "Question": item["question_id"],
                "Selected option": item["selected_option_id"],
                "Result": "Correct" if item["is_correct"] else "Incorrect",
                "Attempted at": item["attempted_at"],
            } for item in history],
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Your submitted answers will appear here.")

    st.divider()
    st.caption("For detailed MCQ, short-answer and MEQ editing, use the dedicated Review Editor in the sidebar.")

    st.subheader("Add examination papers and question sources")
    st.write(
        "Upload past papers whenever you find them. USIPHU keeps the original file and "
        "automatically extracts selectable text into a review queue when the format supports it."
    )
    st.caption(
        "Accepted: PDF, DOCX, DOC, TXT, PNG and JPG · Maximum 50 MB per file. "
        "PDF, DOCX and TXT files are extracted automatically when readable text is available. "
        "Scanned PDFs and images need OCR/manual extraction. Extracted candidates are never auto-approved."
    )
    with st.form("question-source-upload"):
        source_files = st.file_uploader(
            "Choose one or more papers / source files",
            type=["pdf", "docx", "doc", "txt", "png", "jpg", "jpeg"],
            accept_multiple_files=True,
            help="You can add several files at once and return later to add more.",
        )
        source_title = st.text_input("Collection / paper title (optional)")
        source_specialty = st.selectbox(
            "Main specialty",
            ["Unassigned", "Urology", "Vascular Surgery", "Neurosurgery", "Cardiothoracic Surgery",
             "General Surgery", "Pediatrics", "Radiology", "Medicine", "Emergency Medicine", "Other"],
        )
        source_year = st.text_input("Exam year (if known)", placeholder="e.g. 2024")
        source_notes = st.text_area(
            "Notes (optional)", placeholder="University, course, paper number, source/permission details..."
        )
        upload_sources = st.form_submit_button(
            "Save files to source inbox", type="primary", disabled=not source_files
        )
    if upload_sources:
        saved_count = 0
        for uploaded_file in source_files:
            try:
                saved = save_source(
                    uploaded_file.name,
                    uploaded_file.getvalue(),
                    title=source_title or None,
                    specialty=source_specialty,
                    exam_year=source_year,
                    notes=source_notes,
                )
                saved_count += 1
                try:
                    extracted = extract_source(saved["source_id"])
                    count = extracted["summary"]["question_candidates"] + extracted["summary"]["meq_page_candidates"]
                    st.success(
                        f"Saved and extracted {saved['original_filename']}: "
                        f"{count} candidate(s) awaiting review."
                    )
                except Exception as exc:
                    st.warning(
                        f"Saved {saved['original_filename']}, but automatic extraction "
                        f"needs attention: {exc}"
                    )
            except ValueError as exc:
                st.warning(f"{uploaded_file.name}: {exc}")
        if saved_count:
            st.success(f"{saved_count} source file(s) added. Extraction results are saved for review where supported.")
            st.rerun()

    source_records = list_sources()
    st.markdown("#### Source inbox")
    st.caption(f"{len(source_records)} source file(s) stored · newest first")
    if source_records:
        st.dataframe(
            [{
                "Title": item["title"],
                "Original file": item["original_filename"],
                "Specialty": item["specialty"],
                "Year": item["exam_year"] or "—",
                "Status": item["status"].replace("_", " ").title(),
                "Size (MB)": round(item["size_bytes"] / (1024 * 1024), 2),
                "Added": item["uploaded_at"][:10],
            } for item in source_records],
            use_container_width=True,
            hide_index=True,
        )
        for item in source_records:
            with st.expander(f"{item['title']} · {item['original_filename']}"):
                st.write(f"**Specialty:** {item['specialty']}")
                st.write(f"**Exam year:** {item['exam_year'] or 'Not supplied'}")
                st.write(f"**Status:** {item['status'].replace('_', ' ').title()}")
                if item.get("notes"):
                    st.write(item["notes"])
                st.caption(f"Source ID: {item['source_id']} · SHA-256: {item['sha256']}")
                extraction = load_extraction(item["source_id"])
                if extraction:
                    summary = extraction["summary"]
                    st.info(
                        f"{summary['question_candidates']} question candidate(s) · "
                        f"{summary['meq_page_candidates']} MEQ page(s) · "
                        "all remain unreviewed"
                    )
                    st.download_button(
                        "Download extracted candidates (JSON)",
                        data=json.dumps(extraction, ensure_ascii=False, indent=2),
                        file_name=f"{item['source_id']}-candidates.json",
                        mime="application/json",
                        key=f"download-extraction-{item['source_id']}",
                    )
                    candidates = [
                        *extraction.get("mcq_candidates", []),
                        *extraction.get("meq_page_candidates", []),
                    ]
                    for candidate in candidates[:10]:
                        with st.expander(
                            f"Page {candidate['source_page']} · "
                            f"{candidate.get('question_type', 'MEQ').replace('_', ' ').title()} · "
                            f"{candidate['candidate_id']}"
                        ):
                            st.text(candidate.get("raw_text", candidate.get("stem_extracted", "")))
                            if candidate.get("options"):
                                for option in candidate["options"]:
                                    st.write(f"{option['id'].upper()}. {option['text']}")
                    if len(candidates) > 10:
                        st.caption(f"Previewing 10 of {len(candidates)} extracted candidates.")
                if st.button("Run / retry extraction", key=f"extract-source-{item['source_id']}"):
                    try:
                        result = extract_source(item["source_id"])
                        st.success(
                            f"Extraction complete: "
                            f"{result['summary']['question_candidates'] + result['summary']['meq_page_candidates']} "
                            "candidate(s) awaiting review."
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Extraction could not complete: {exc}")
    else:
        st.info("No source files yet. Upload your first paper above.")

st.divider()
st.caption(
    "Educational use only. Verify clinical information against current guidelines and local protocols. "
    "Editorial drafts are not clinically approved."
)
