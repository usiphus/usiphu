"""Streamlit interface for Usiphu 2.0."""
import streamlit as st
from usiphu.curriculum import coverage_summary, flatten_topics, load_curriculum
from usiphu.resources import discover_resources
from usiphu.storage import dashboard_stats, due_cards, initialize, save_flashcard

st.set_page_config(page_title="Usiphu 2.0", page_icon="🩺", layout="wide")
initialize()
st.title("🩺 Usiphu 2.0")
st.caption("Your structured workspace for medical learning, exam practice, and long-term retention.")
curriculum = load_curriculum()
stats = dashboard_stats()
coverage = coverage_summary(curriculum)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Specialties mapped", coverage["specialties"])
c2.metric("Curriculum topics", coverage["topics"])
c3.metric("Flashcards", stats["flashcards"])
c4.metric("Reviews completed", stats["reviews_completed"])

tab1, tab2, tab3, tab4 = st.tabs(["Curriculum", "Find resources", "Flashcards", "Progress"])
with tab1:
    st.subheader("Specialty curriculum")
    st.write(f"{coverage['domains']} domains · {coverage['topics']} topics · "
             f"{coverage['objectives']} learning objectives")
    st.progress(coverage["objective_coverage_percent"] / 100,
                text=f"{coverage['objective_coverage_percent']}% of mapped topics have objectives")
    search = st.text_input("Search specialties, domains, and topics")
    rows = flatten_topics(curriculum)
    if search:
        rows = [r for r in rows if search.casefold() in
                " ".join(r.values()).casefold()]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    with st.expander("Browse by specialty"):
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
    st.subheader("Create a flashcard")
    with st.form("new_card"):
        card_id = st.text_input("Unique card ID", placeholder="uro-001")
        card_specialty = st.text_input("Specialty ID", value="urology")
        card_topic = st.text_input("Topic ID", placeholder="acute-retention")
        prompt = st.text_area("Prompt / front")
        answer = st.text_area("Answer / back")
        source_url = st.text_input("Source URL (optional)")
        submitted = st.form_submit_button("Save flashcard")
    if submitted:
        if not all(x.strip() for x in (card_id, card_specialty, card_topic, prompt, answer)):
            st.error("Complete the ID, specialty, topic, prompt, and answer.")
        else:
            save_flashcard({"id": card_id.strip(), "specialty_id": card_specialty.strip(),
                            "topic_id": card_topic.strip(), "prompt": prompt.strip(),
                            "answer": answer.strip(), "source_url": source_url.strip() or None})
            st.success("Flashcard saved. It is now in your review queue.")
    st.metric("Cards due today", stats["due_cards"])
    cards = due_cards()
    if cards:
        for card in cards:
            with st.expander(card["prompt"]):
                st.write(card["answer"])
                st.caption(f"Topic: {card['topic_id']} · Due: {card['due_date']}")
    else:
        st.info("No cards due. Add a card above to start a review habit.")
with tab4:
    st.subheader("Learning activity")
    st.metric("Reviews completed", stats["reviews_completed"])
    st.metric("Cards due", stats["due_cards"])
    st.info("Topic mastery and cohort analytics are planned; this release tracks local review activity only.")
st.divider()
st.caption("Educational use only. Verify clinical information against current guidelines and local protocols.")
