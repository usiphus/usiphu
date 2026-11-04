"""Streamlit interface for the Usiphu 2.0 learning workspace."""
import os

import streamlit as st

from usiphu.ai_provider import (
    GenerationNotConfigured,
    generate_topic_cards,
    provider_status,
)
from usiphu.coverage import coverage_report, load_coverage_register
from usiphu.curriculum import coverage_summary, flatten_topics, load_curriculum
from usiphu.models import ReviewState
from usiphu.practice import load_cases, load_questions
from usiphu.resources import discover_resources
from usiphu.scheduler import schedule_review
from usiphu.storage import (
    dashboard_stats,
    due_cards,
    generated_drafts,
    initialize,
    record_review,
    save_flashcard,
    save_generated_drafts,
    set_topic_progress,
    topic_progress,
)

st.set_page_config(page_title="Usiphu 2.0", page_icon="🩺", layout="wide")

AUTH_REQUIRED = os.getenv("USIPHU_AUTH_REQUIRED", "false").lower() == "true"
if AUTH_REQUIRED:
    if not st.user.is_logged_in:
        st.title("🩺 Usiphu 2.0")
        st.write("Sign in with your configured identity provider to access your learning workspace.")
        st.button("Sign in", on_click=st.login)
        st.stop()
    subject = st.user.get("sub")
    if not subject:
        st.error("The identity provider did not return a stable subject identifier.")
        st.stop()
    learner_id = f"{st.user.get('iss', 'oidc')}:{subject}"
    with st.sidebar:
        st.caption(f"Signed in: {st.user.get('email', 'learner')}")
        st.button("Sign out", on_click=st.logout)
else:
    learner_id = "local"
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

st.title("🩺 Usiphu")
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

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    ["🧭 Learn", "📚 Resources", "📝 Practice", "🗂️ Flashcards", "📈 Progress", "✨ AI Studio", "🏦 Question Bank"])
with tab1:
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
with tab2:
    st.subheader("Discover learning sources")
    topic = st.text_input("Topic", placeholder="e.g. acute urinary retention")
    specialty = st.text_input("Specialty (optional)", placeholder="e.g. Urology")
    if topic.strip():
        for resource in discover_resources(topic.strip(), specialty.strip() or None):
            st.markdown(f"**[{resource['name']}]({resource['url']})** · {resource['kind']}")
            st.caption(resource["note"])
with tab3:
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
            correct = chosen == selected.correct_option_id
            st.success("Correct") if correct else st.error("Not quite — review the explanation.")
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
with tab4:
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
with tab5:
    st.subheader("Learner progress")
    p1, p2, p3 = st.columns(3)
    p1.metric("Topics tracked", stats["topics_tracked"])
    p2.metric("Topics mastered", stats["topics_mastered"])
    p3.metric("Reviews completed", stats["reviews_completed"])
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
st.divider()
st.caption("Educational use only. Verify clinical information against current guidelines and local protocols.")



with tab6:
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

with tab7:
    st.subheader("Medical question bank")
    from usiphu.practice import filter_questions
    from usiphu.storage import (
        question_attempt_history, question_bank_stats, record_question_attempt,
    )

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
    f1, f2, f3, f4, f5 = st.columns(5)
    specialty_filter = f1.selectbox("Specialty", ["All", *specialties], key="qb-specialty")
    specialty_questions = [
        item for item in bank_questions
        if specialty_filter == "All" or item.specialty_id == specialty_filter
    ]
    topics = sorted({item.topic_id for item in specialty_questions})
    topic_filter = f2.selectbox("Topic", ["All", *topics], key="qb-topic")
    difficulty_filter = f3.selectbox(
        "Difficulty", ["All", "easy", "moderate", "hard"], key="qb-difficulty"
    )
    status_filter = f4.selectbox(
        "Editorial status", ["All", "draft", "clinically_reviewed", "exam_validated"],
        key="qb-status",
    )
    bank_filter = f5.selectbox("Question bank", ["All", *bank_ids], key="qb-bank")
    filtered_questions = filter_questions(
        bank_questions,
        specialty_id=None if specialty_filter == "All" else specialty_filter,
        topic_id=None if topic_filter == "All" else topic_filter,
        difficulty=None if difficulty_filter == "All" else difficulty_filter,
        review_status=None if status_filter == "All" else status_filter,
        bank_id=None if bank_filter == "All" else bank_filter,
    )
    st.caption(f"{len(filtered_questions)} questions match these filters.")
    if filtered_questions:
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
        with st.container(border=True):
            st.markdown(f"#### {selected_question.stem}")
            result_key = f"qb-result-{selected_question.id}"
            previous_result = st.session_state.get(result_key)
            selected_option = st.radio(
                "Select the single best answer",
                selected_question.options,
                format_func=lambda option: option.text,
                key=f"qb-answer-{selected_question.id}",
                disabled=previous_result is not None,
            )
            if st.button(
                "Submit answer", type="primary",
                key=f"qb-submit-{selected_question.id}",
                disabled=previous_result is not None,
            ):
                correct = selected_option.id == selected_question.correct_option_id
                record_question_attempt(
                    selected_question.id, selected_option.id, correct,
                    learner_id=learner_id,
                )
                st.session_state[result_key] = {
                    "selected": selected_option.id, "correct": correct,
                }
            result = st.session_state.get(result_key)
            if result:
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
                if selected_question.review_status == "draft":
                    st.caption("Editorial draft — clinical and examination review still required.")
                if st.button("Retry this question", key=f"qb-retry-{selected_question.id}"):
                    del st.session_state[result_key]
                    st.rerun()
    else:
        st.info("No questions match the selected filters.")

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
