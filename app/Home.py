"""Streamlit learning workspace for USIPHU."""
import os
import random
from datetime import datetime, timezone

import streamlit as st

from usiphu.ai_provider import (
    GenerationNotConfigured,
    generate_topic_cards,
    provider_status,
)
from usiphu.curriculum import coverage_summary, flatten_topics, load_curriculum
from usiphu.models import ReviewState
from usiphu.practice import load_cases, load_questions
from usiphu.resources import discover_resources
from usiphu.scheduler import schedule_review
from usiphu.question_history import question_performance, record_question_attempts
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

st.set_page_config(page_title="USIPHU", page_icon="🩺", layout="wide")

st.markdown(
    """
    <style>
      .block-container {max-width: 1440px; padding-top: 1.6rem; padding-bottom: 3rem;}
      [data-testid="stSidebar"] {border-right: 1px solid rgba(128,128,128,.18);}
      .usiphu-eyebrow {font-size:.76rem; letter-spacing:.12em; text-transform:uppercase;
        color:#6b8f91; font-weight:700; margin-bottom:.25rem;}
      .usiphu-hero {padding:1.35rem 1.5rem; border-radius:18px;
        background:linear-gradient(120deg,rgba(34,110,112,.13),rgba(81,129,155,.08));
        border:1px solid rgba(70,130,135,.18); margin-bottom:1rem;}
      .usiphu-hero h1 {margin:.1rem 0 .35rem 0; font-size:2rem;}
      .usiphu-muted {color:var(--text-color); opacity:.68; font-size:.92rem;}
      div[data-testid="stMetric"] {background:rgba(128,128,128,.055);
        padding:.8rem 1rem; border:1px solid rgba(128,128,128,.13); border-radius:14px;}
      div.stButton > button {border-radius:10px;}
      div[data-testid="stExpander"] {border-radius:12px;}
    </style>
    """,
    unsafe_allow_html=True,
)

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
else:
    learner_id = "local"

initialize()
curriculum = load_curriculum()
coverage = coverage_summary(curriculum)
stats = dashboard_stats(learner_id=learner_id)
questions = load_questions()
cases = load_cases()
question_stats = question_performance(learner_id=learner_id)

PAGES = [
    "Overview",
    "Curriculum",
    "Question Bank",
    "Clinical Cases",
    "Resources",
    "Flashcards",
    "My Progress",
    "AI Draft Studio",
]

with st.sidebar:
    st.markdown("## 🩺 USIPHU")
    st.caption("Medical learning workspace")
    page = st.radio("Workspace", PAGES, label_visibility="collapsed")
    st.divider()
    st.caption(f"{coverage['specialties']} specialties · {coverage['topics']} mapped topics")
    st.caption(f"{len(questions)} question-bank items · {len(cases)} clinical cases")
    if AUTH_REQUIRED:
        st.caption(f"Signed in: {st.user.get('email', 'learner')}")
        st.button("Sign out", on_click=st.logout)
    else:
        st.warning("Local learner mode")

PAGE_META = {
    "Overview": ("Your learning workspace", "A single place for curriculum, questions, cases and revision."),
    "Curriculum": ("Curriculum explorer", "Browse the mapped specialties, domains, topics and learning objectives."),
    "Question Bank": ("Question bank", "Filter questions, practise by topic, or assemble a mock examination."),
    "Clinical Cases": ("Clinical cases", "Work through structured scenarios and OSCE/viva discussion points."),
    "Resources": ("Resource finder", "Discover guidelines, primary literature and trusted learning resources."),
    "Flashcards": ("Flashcards", "Create cards and review what is due using spaced repetition."),
    "My Progress": ("Your progress", "Track topic confidence, question accuracy and revision activity."),
    "AI Draft Studio": ("AI draft studio", "Generate source-linked educational drafts for human clinical review."),
}
title, subtitle = PAGE_META[page]
st.markdown(f'<div class="usiphu-eyebrow">Medical learning · Suez curriculum workspace</div>', unsafe_allow_html=True)
st.title(title)
st.caption(subtitle)

if page == "Overview":
    st.markdown(
        '<div class="usiphu-hero"><h1>Study with a plan.</h1>'
        '<div class="usiphu-muted">Move from learning objectives to questions, clinical reasoning and revision — without losing the source of the material.</div></div>',
        unsafe_allow_html=True,
    )
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Specialties", coverage["specialties"])
    m2.metric("Mapped topics", coverage["topics"])
    m3.metric("Questions", len(questions))
    m4.metric("Cards due", stats["due_cards"])
    reviewed_questions = question_stats["attempted"]
    accuracy = question_stats["accuracy"]
    st.subheader("Your study snapshot")
    left, right = st.columns([1.15, 1])
    with left:
        st.markdown("#### Continue learning")
        st.info("Choose a starting point below. Your existing curriculum, question bank, cases and flashcards remain available.")
        shortcuts = [
            ("Question Bank", "Practise by specialty and topic"),
            ("Curriculum", "Find the learning objectives behind a topic"),
            ("Clinical Cases", "Apply knowledge to a clinical scenario"),
            ("Flashcards", "Review cards due today"),
        ]
        for label, description in shortcuts:
            st.markdown(f"**{label}**  \n{description}")
    with right:
        st.markdown("#### Activity")
        a1, a2 = st.columns(2)
        a1.metric("Questions attempted", reviewed_questions)
        a2.metric("Question accuracy", f"{accuracy:.0f}%" if reviewed_questions else "—")
        st.metric("Flashcard reviews", stats["reviews_completed"])
        st.metric("Topics mastered", stats["topics_mastered"])
    st.subheader("Curriculum quality")
    st.progress(coverage["objective_coverage_percent"] / 100)
    st.caption(
        f"{coverage['topics_sourced']} sourced · {coverage['topics_reviewed']} clinically reviewed · "
        f"{coverage['topics_exam_validated']} exam validated. A mapped topic is not automatically syllabus-complete."
    )
    draft_questions = sum(q.review_status == "draft" for q in questions)
    if draft_questions:
        st.warning(f"{draft_questions} question(s) are editorial drafts. They are useful for interface testing and study development, but are not clinically approved.")

elif page == "Curriculum":
    st.subheader("Explore the curriculum")
    st.write(
        f"{coverage['domains']} domains · {coverage['topics']} topics · "
        f"{coverage['objectives']} learning objectives"
    )
    st.progress(
        coverage["objective_coverage_percent"] / 100,
        text=f"{coverage['objective_coverage_percent']}% of mapped topics have objectives",
    )
    search = st.text_input("Search specialties, domains or topics", placeholder="e.g. urinary retention")
    rows = flatten_topics(curriculum)
    if search.strip():
        term = search.casefold()
        rows = [row for row in rows if term in " ".join(row.values()).casefold()]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    with st.expander("Browse learning objectives"):
        for specialty_item in curriculum.specialties:
            with st.expander(specialty_item.title):
                for domain in specialty_item.domains:
                    st.markdown(f"**{domain.title}**")
                    for topic_item in domain.topics:
                        st.markdown(f"- **{topic_item.title}**")
                        for objective in topic_item.objectives:
                            st.caption(f"  {objective.level.title()}: {objective.text}")

elif page == "Question Bank":
    draft_count = sum(q.review_status == "draft" for q in questions)
    if draft_count:
        st.warning(
            f"{draft_count} of {len(questions)} questions are still editorial drafts. "
            "Draft questions are clearly labelled and must not be treated as faculty-approved exam content."
        )
    with st.expander("Find questions", expanded=True):
        f1, f2, f3 = st.columns(3)
        specialties = ["All specialties"] + sorted({q.specialty_id for q in questions})
        selected_specialty = f1.selectbox("Specialty", specialties)
        difficulties = ["All levels"] + sorted({q.difficulty for q in questions})
        selected_difficulty = f2.selectbox("Difficulty", difficulties)
        statuses = ["All statuses"] + sorted({q.review_status for q in questions})
        selected_status = f3.selectbox("Editorial status", statuses)
        search_term = st.text_input("Search question text or topic", placeholder="Search the question bank")
    filtered = [
        q for q in questions
        if (selected_specialty == "All specialties" or q.specialty_id == selected_specialty)
        and (selected_difficulty == "All levels" or q.difficulty == selected_difficulty)
        and (selected_status == "All statuses" or q.review_status == selected_status)
        and (
            not search_term.strip()
            or search_term.casefold() in f"{q.stem} {q.topic_id} {q.specialty_id}".casefold()
        )
    ]
    st.caption(f"Showing {len(filtered)} of {len(questions)} questions")
    if filtered:
        with st.expander("Question catalogue", expanded=False):
            for q in filtered:
                st.markdown(f"**{q.specialty_id.replace('-', ' ').title()} · {q.topic_id.replace('-', ' ').title()}**")
                st.write(q.stem)
                st.caption(f"{q.difficulty.title()} · {q.review_status.replace('_', ' ').title()} · ID: {q.id}")
                st.divider()

        st.subheader("Build a practice session")
        mode = st.radio("Session type", ["Study mode", "Mock exam"], horizontal=True)
        c1, c2 = st.columns(2)
        count = c1.number_input("Number of questions", min_value=1, max_value=max(1, len(filtered)), value=min(5, len(filtered)), step=1)
        shuffle = c2.toggle("Randomize question order", value=True)
        if st.button("Start session", type="primary", use_container_width=True):
            selected = list(filtered)
            if shuffle:
                random.shuffle(selected)
            selected = selected[: int(count)]
            st.session_state["qb_run"] = {
                "ids": [q.id for q in selected],
                "mode": mode,
                "answers": {},
                "submitted": False,
                "recorded": False,
                "index": 0,
                "run_id": datetime.now(timezone.utc).isoformat(),
            }
            st.rerun()

        run = st.session_state.get("qb_run")
        if run and run["ids"]:
            lookup = {q.id: q for q in questions}
            session_questions = [lookup[qid] for qid in run["ids"] if qid in lookup]
            st.divider()
            st.markdown(f"#### Active session · {run['mode']}")
            if run["mode"] == "Study mode":
                index = min(run["index"], len(session_questions) - 1)
                q = session_questions[index]
                st.progress((index + 1) / len(session_questions), text=f"Question {index + 1} of {len(session_questions)}")
                st.caption(f"{q.specialty_id.replace('-', ' ').title()} · {q.topic_id.replace('-', ' ').title()} · {q.difficulty.title()} · {q.review_status.replace('_', ' ').title()}")
                st.markdown(f"### {q.stem}")
                prior = run["answers"].get(q.id)
                option_ids = [o.id for o in q.options]
                current_index = option_ids.index(prior) if prior in option_ids else None
                chosen = st.radio(
                    "Choose the single best answer",
                    q.options,
                    index=current_index,
                    format_func=lambda option: f"{option.id.upper()}. {option.text}",
                    key=f"qb-{run['run_id']}-{q.id}",
                    disabled=prior is not None,
                )
                if prior is None and st.button("Check answer", type="primary", key=f"qb-check-{q.id}"):
                    run["answers"][q.id] = chosen.id
                    record_question_attempts(
                        [{"question_id": q.id, "selected_option_id": chosen.id,
                          "is_correct": chosen.id == q.correct_option_id, "mode": "practice"}],
                        learner_id=learner_id,
                    )
                    st.session_state["qb_run"] = run
                    st.rerun()
                if prior is not None:
                    if prior == q.correct_option_id:
                        st.success("Correct")
                    else:
                        st.error(f"Not quite. Correct answer: {next(o.text for o in q.options if o.id == q.correct_option_id)}")
                    st.markdown("**Explanation**")
                    st.write(q.explanation)
                    if q.source_url:
                        st.markdown(f"[Source / further reading]({q.source_url})")
                    nav1, nav2, nav3 = st.columns([1, 1, 2])
                    if nav1.button("Previous", disabled=index == 0):
                        run["index"] = index - 1
                        st.session_state["qb_run"] = run
                        st.rerun()
                    if nav2.button("Next", disabled=index >= len(session_questions) - 1):
                        run["index"] = index + 1
                        st.session_state["qb_run"] = run
                        st.rerun()
                    if nav3.button("Finish session", type="secondary"):
                        st.session_state.pop("qb_run", None)
                        st.rerun()
            else:
                if not run["submitted"]:
                    st.caption("Answers and explanations stay hidden until you submit the whole exam.")
                    for i, q in enumerate(session_questions, start=1):
                        st.markdown(f"**{i}. {q.stem}**")
                        chosen = st.radio(
                            f"Answer question {i}",
                            q.options,
                            format_func=lambda option: f"{option.id.upper()}. {option.text}",
                            key=f"qb-exam-{run['run_id']}-{q.id}",
                            index=None,
                        )
                        if chosen:
                            run["answers"][q.id] = chosen.id
                    st.session_state["qb_run"] = run
                    if st.button("Submit mock exam", type="primary", use_container_width=True):
                        attempts = []
                        for q in session_questions:
                            selected_id = run["answers"].get(q.id)
                            if selected_id:
                                attempts.append({
                                    "question_id": q.id,
                                    "selected_option_id": selected_id,
                                    "is_correct": selected_id == q.correct_option_id,
                                    "mode": "exam",
                                })
                        if attempts:
                            record_question_attempts(attempts, learner_id=learner_id)
                        run["submitted"] = True
                        run["recorded"] = True
                        st.session_state["qb_run"] = run
                        st.rerun()
                else:
                    answered = len(run["answers"])
                    correct_count = sum(
                        run["answers"].get(q.id) == q.correct_option_id
                        for q in session_questions
                    )
                    score = round(100 * correct_count / len(session_questions)) if session_questions else 0
                    st.metric("Mock exam score", f"{correct_count}/{len(session_questions)} · {score}%")
                    st.caption(f"{answered} of {len(session_questions)} answered")
                    for i, q in enumerate(session_questions, start=1):
                        selected_id = run["answers"].get(q.id)
                        is_correct = selected_id == q.correct_option_id
                        st.markdown(f"**{i}. {'✓' if is_correct else '✗'} {q.stem}**")
                        if not selected_id:
                            st.warning("Not answered")
                        else:
                            chosen_text = next(o.text for o in q.options if o.id == selected_id)
                            st.write(f"Your answer: {chosen_text}")
                        correct_text = next(o.text for o in q.options if o.id == q.correct_option_id)
                        st.write(f"Correct answer: {correct_text}")
                        st.caption(q.explanation)
                        if q.source_url:
                            st.markdown(f"[Source]({q.source_url})")
                        st.divider()
                    if st.button("Close exam review", type="primary"):
                        st.session_state.pop("qb_run", None)
                        st.rerun()
    else:
        st.info("No questions match these filters. Try changing the specialty, difficulty or editorial status.")

elif page == "Clinical Cases":
    case_specialties = ["All specialties"] + sorted({case.specialty_id for case in cases})
    selected_case_specialty = st.selectbox("Filter by specialty", case_specialties)
    visible_cases = [case for case in cases if selected_case_specialty == "All specialties" or case.specialty_id == selected_case_specialty]
    if visible_cases:
        chosen_case = st.selectbox("Choose a case", visible_cases, format_func=lambda item: item.title)
        st.caption(f"{chosen_case.specialty_id.replace('-', ' ').title()} · {chosen_case.topic_id.replace('-', ' ').title()} · {chosen_case.review_status.replace('_', ' ').title()}")
        if chosen_case.review_status == "draft":
            st.warning("Editorial draft — clinical review required.")
        st.markdown("### Clinical scenario")
        st.write(chosen_case.scenario)
        st.markdown("### Your tasks")
        for i, task in enumerate(chosen_case.tasks, start=1):
            st.markdown(f"{i}. {task}")
        with st.expander("Reveal examiner discussion points"):
            for point in chosen_case.discussion_points:
                st.markdown(f"- {point}")
        if chosen_case.source_url:
            st.markdown(f"[Source / guideline]({chosen_case.source_url})")
    else:
        st.info("No cases are available for this specialty yet.")

elif page == "Resources":
    st.subheader("Search medical learning resources")
    with st.form("resource-search"):
        topic = st.text_input("Topic", placeholder="e.g. acute urinary retention")
        specialty = st.text_input("Specialty (optional)", placeholder="e.g. Urology")
        search_resources = st.form_submit_button("Find resources", type="primary")
    if search_resources and topic.strip():
        for resource in discover_resources(topic.strip(), specialty.strip() or None):
            with st.container(border=True):
                st.markdown(f"**[{resource['name']}]({resource['url']})** · {resource['kind']}")
                st.caption(resource["note"])
    elif search_resources:
        st.warning("Enter a topic to search.")

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
            st.error("Complete the ID, specialty, topic, prompt and answer.")
        else:
            try:
                save_flashcard({
                    "id": card_id.strip(), "specialty_id": card_specialty.strip(),
                    "topic_id": card_topic.strip(), "prompt": prompt.strip(),
                    "answer": answer_text.strip(), "source_url": source_url.strip() or None,
                }, learner_id=learner_id)
                st.success("Flashcard saved to your review queue.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    st.divider()
    c1, c2 = st.columns(2)
    c1.metric("Cards in your library", stats["flashcards"])
    c2.metric("Cards due today", stats["due_cards"])
    cards = due_cards(learner_id=learner_id)
    if not cards:
        st.success("No cards due today. You're up to date.")
    for card in cards:
        with st.expander(card["prompt"]):
            st.write(card["answer"])
            st.caption(f"Topic: {card['topic_id']} · Due: {card['due_date']}")
            grade = st.select_slider(
                "Recall quality (0 = forgot, 5 = effortless)",
                options=[0, 1, 2, 3, 4, 5], value=3, key=f"grade-{card['id']}",
            )
            if st.button("Record review", key=f"review-{card['id']}"):
                state = ReviewState(
                    card_id=card["id"], repetitions=card["repetitions"],
                    interval_days=card["interval_days"], ease_factor=card["ease_factor"],
                    due_date=card["due_date"],
                )
                updated = schedule_review(state, grade)
                record_review(card["id"], grade, updated, learner_id=learner_id)
                st.success(f"Review saved. Next due: {updated.due_date}")
                st.rerun()

elif page == "My Progress":
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Questions attempted", question_stats["attempted"])
    p2.metric("Question accuracy", f"{question_stats['accuracy']:.1f}%" if question_stats["attempted"] else "—")
    p3.metric("Flashcard reviews", stats["reviews_completed"])
    p4.metric("Topics mastered", stats["topics_mastered"])
    st.subheader("Question performance by topic")
    if question_stats["by_topic"]:
        st.dataframe(question_stats["by_topic"], use_container_width=True, hide_index=True)
    else:
        st.info("Complete a few practice questions or mock exams to see your topic-level performance.")
    st.subheader("Curriculum confidence")
    with st.form("topic_progress"):
        topic_rows = flatten_topics(curriculum)
        topic_lookup = {row["topic_id"]: row for row in topic_rows}
        topic_ids = list(topic_lookup)
        chosen_topic = st.selectbox(
            "Topic", topic_ids,
            format_func=lambda value: f"{topic_lookup[value]['specialty']} · {topic_lookup[value]['topic']}",
        )
        status = st.selectbox("Status", ["not_started", "learning", "reviewing", "mastered"])
        confidence = st.slider("Confidence", 0, 5, 2)
        progress_submit = st.form_submit_button("Update progress")
    if progress_submit:
        set_topic_progress(chosen_topic, status, confidence, learner_id=learner_id)
        st.success("Progress updated.")
    progress_rows = topic_progress(learner_id=learner_id)
    if progress_rows:
        st.dataframe(progress_rows, use_container_width=True, hide_index=True)

elif page == "AI Draft Studio":
    status = provider_status()
    if status["configured"]:
        st.success(f"Local AI authoring configured · {status['model']} · PubMed evidence retrieval")
    else:
        st.warning(
            "Local Ollama authoring is not configured. Start Ollama and set OLLAMA_BASE_URL "
            "and USIPHU_OLLAMA_MODEL in the server environment."
        )
    st.caption(
        "Generated content remains an editorial draft. Automated checks do not establish "
        "clinical accuracy, guideline currency or faculty approval."
    )
    topic_choices = [
        (row["specialty_id"], row["topic_id"], row["specialty"], row["topic"])
        for row in flatten_topics(curriculum)
    ]
    selected_topic = st.selectbox(
        "Curriculum topic", topic_choices,
        format_func=lambda item: f"{item[2]} · {item[3]}",
        key="generator-topic",
    )
    evidence_limit = st.slider("PubMed records per learning objective", 1, 10, 5)
    if st.button(
        "Generate evidence-grounded draft cards",
        type="primary",
        disabled=not status["configured"],
        key="generate-evidence-grounded-cards",
    ):
        try:
            with st.spinner("Searching PubMed and drafting cards..."):
                st.session_state["generated_card_result"] = generate_topic_cards(
                    selected_topic[0], selected_topic[1], evidence_limit=evidence_limit
                )
        except (GenerationNotConfigured, KeyError) as exc:
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
            st.success(f"Saved {saved} new draft(s). They remain outside the learner flashcard queue.")
        for item in generated["results"]:
            card = item.get("card")
            heading = card["prompt"] if card else item.get("reason", item.get("status", "Generation result"))
            with st.expander(f"{item.get('status', 'result')}: {heading}", expanded=bool(card)):
                if card:
                    st.write(card["answer"])
                    st.caption(
                        f"{card['card_type']} · {card.get('difficulty', 'not supplied')} · "
                        "DRAFT — clinical and exam review required"
                    )
                    for option in card.get("options", []):
                        prefix = "✓ " if option["id"] == card.get("correct_option_id") else "• "
                        st.write(prefix + option["text"])
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
    drafts = generated_drafts(learner_id=learner_id)
    st.subheader(f"Saved generated drafts ({len(drafts)})")
    for draft in drafts:
        with st.expander(draft["prompt"]):
            st.write(draft["answer"])
            st.caption("DRAFT — not approved for learner flashcard review")
            for source in draft.get("evidence_sources", []):
                st.markdown(f"- [{source['source_title']}]({source['source_url']})")

st.divider()
st.caption(
    "Educational use only. Verify clinical information against current guidelines and local protocols. "
    "Editorial drafts are not clinically approved."
)
