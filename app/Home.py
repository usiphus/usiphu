"""Streamlit interface for the Usiphu 2.0 learning workspace."""
import streamlit as st
from usiphu.curriculum import coverage_summary, flatten_topics, load_curriculum
from usiphu.practice import load_cases, load_questions
from usiphu.resources import discover_resources
from usiphu.storage import (dashboard_stats, due_cards, initialize, save_flashcard,
                            set_topic_progress, topic_progress)

st.set_page_config(page_title="Usiphu 2.0", page_icon="🩺", layout="wide")
initialize()
st.title("🩺 Usiphu 2.0")
st.caption("A structured workspace for medical learning, exam practice, and long-term retention.")
curriculum = load_curriculum()
stats = dashboard_stats()
coverage = coverage_summary(curriculum)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Specialties mapped", coverage["specialties"])
c2.metric("Curriculum topics", coverage["topics"])
c3.metric("Flashcards", stats["flashcards"])
c4.metric("Reviews completed", stats["reviews_completed"])

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Curriculum", "Find resources", "Practice", "Flashcards", "Progress"])
with tab1:
    st.subheader("Specialty curriculum")
    st.write(f"{coverage['domains']} domains · {coverage['topics']} topics · {coverage['objectives']} learning objectives")
    st.progress(coverage["objective_coverage_percent"] / 100,
                text=f"{coverage['objective_coverage_percent']}% of mapped topics have objectives")
    search = st.text_input("Search specialties, domains, and topics")
    rows = flatten_topics(curriculum)
    if search:
        rows = [r for r in rows if search.casefold() in " ".join(r.values()).casefold()]
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
    if questions:
        selected = st.selectbox("Choose a question", questions, format_func=lambda q: q.stem)
        answer = st.radio("Select your answer", selected.options, format_func=lambda o: o.text,
                          key=f"answer-{selected.id}")
        if st.button("Check answer", key=f"check-{selected.id}"):
            st.session_state[f"checked-{selected.id}"] = True
        if st.session_state.get(f"checked-{selected.id}", False):
            correct = answer.id == selected.correct_option_id
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
        if not all(x.strip() for x in (card_id, card_specialty, card_topic, prompt, answer_text)):
            st.error("Complete the ID, specialty, topic, prompt, and answer.")
        else:
            save_flashcard({"id": card_id.strip(), "specialty_id": card_specialty.strip(),
                            "topic_id": card_topic.strip(), "prompt": prompt.strip(),
                            "answer": answer_text.strip(), "source_url": source_url.strip() or None})
            st.success("Flashcard saved. It is now in your review queue.")
    st.metric("Cards due today", stats["due_cards"])
    for card in due_cards():
        with st.expander(card["prompt"]):
            st.write(card["answer"])
            st.caption(f"Topic: {card['topic_id']} · Due: {card['due_date']}")
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
        set_topic_progress(chosen_topic, status, confidence)
        st.success("Progress updated.")
    progress_rows = topic_progress()
    if progress_rows:
        st.dataframe(progress_rows, use_container_width=True, hide_index=True)
st.divider()
st.caption("Educational use only. Verify clinical information against current guidelines and local protocols.")
