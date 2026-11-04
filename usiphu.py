import os
import sqlite3
from pathlib import Path
import streamlit as st
import ollama

# Try importing FPDF for PDF exports
try:
    from fpdf import FPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# Try importing Whisper for local speech-to-text
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

# --- 1. PAGE CONFIGURATION & PRISTINE CSS DESIGN SYSTEM ---
st.set_page_config(
    page_title="Usiphu — AI Clinical Tutor",
    page_icon="🩺",
    layout="wide"
)

# Pristine Custom Theme & Component Injection
st.markdown("""
    <style>
    /* Global Page Styling */
    .stApp {
        background-color: #0d1117;
        color: #c9d1d9;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Top & Side Padding Optimization */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 3rem !important;
        max-width: 95% !important;
    }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #161b22 !important;
        border-right: 1px solid #30363d !important;
    }

    /* Headers */
    h1, h2, h3 {
        color: #f0f6fc !important;
        font-weight: 600 !important;
        letter-spacing: -0.5px !important;
    }

    /* Custom Metric Cards */
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
        color: #58a6ff !important;
    }
    
    div[data-testid="stMetricLabel"] {
        font-size: 0.85rem !important;
        color: #8b949e !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Buttons */
    .stButton button {
        border-radius: 8px !important;
        border: 1px solid #30363d !important;
        font-weight: 500 !important;
        transition: all 0.2s ease-in-out !important;
    }
    
    .stButton button[kind="primary"] {
        background-color: #238636 !important;
        color: #ffffff !important;
        border: none !important;
    }
    
    .stButton button[kind="primary"]:hover {
        background-color: #2ea043 !important;
        box-shadow: 0px 4px 12px rgba(46, 160, 67, 0.3) !important;
    }

    /* Text Inputs & Text Areas */
    .stTextArea textarea, .stTextInput input, div[data-baseweb="select"] {
        background-color: #1f242c !important;
        border: 1px solid #30363d !important;
        border-radius: 8px !important;
        color: #f0f6fc !important;
    }

    /* Expanders */
    .streamlit-expanderHeader {
        background-color: #161b22 !important;
        border-radius: 8px !important;
        border: 1px solid #30363d !important;
        color: #58a6ff !important;
        font-weight: 600 !important;
    }

    /* Code & Data Editor Container */
    .stCodeBlock {
        border-radius: 8px !important;
        border: 1px solid #30363d !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. SQLITE DATABASE SETUP & HELPERS ---
DB_FILE = "usiphu.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cases_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            specialty TEXT,
            case_content TEXT,
            user_differential TEXT,
            ai_critique TEXT,
            confidence_rating TEXT DEFAULT 'Unrated'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anki_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            specialty TEXT,
            front TEXT UNIQUE,
            back TEXT,
            tags TEXT
        )
    """)
    try:
        cursor.execute("ALTER TABLE cases_log ADD COLUMN confidence_rating TEXT DEFAULT 'Unrated'")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def log_new_case(specialty, case_content):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO cases_log (specialty, case_content) VALUES (?, ?)", (specialty, case_content))
    case_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return case_id

def auto_save_differential_draft(case_id, user_diff):
    if case_id:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE cases_log SET user_differential = ? WHERE id = ?", (user_diff, case_id))
        conn.commit()
        conn.close()

def save_differential_and_critique(case_id, user_diff, critique):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE cases_log SET user_differential = ?, ai_critique = ? WHERE id = ?", (user_diff, critique, case_id))
    conn.commit()
    conn.close()

def update_case_confidence(case_id, rating):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE cases_log SET confidence_rating = ? WHERE id = ?", (rating, case_id))
    conn.commit()
    conn.close()

def save_anki_cards_to_db(cards_list, specialty):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    added_count, duplicate_count = 0, 0
    for card in cards_list:
        front = card.get('Front', '').strip()
        back = card.get('Back', '').strip()
        tags = card.get('Tags', '').strip()
        if front and back:
            try:
                cursor.execute("INSERT OR IGNORE INTO anki_cards (specialty, front, back, tags) VALUES (?, ?, ?, ?)", (specialty, front, back, tags))
                if cursor.rowcount > 0:
                    added_count += 1
                else:
                    duplicate_count += 1
            except sqlite3.IntegrityError:
                duplicate_count += 1
    conn.commit()
    conn.close()
    return added_count, duplicate_count

def get_saved_anki_card_count():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM anki_cards")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_all_saved_anki_cards():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, timestamp, specialty, front, back, tags FROM anki_cards ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def search_saved_anki_cards(keyword, specialty_filter="All Specialties"):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    search_term = f"%{keyword}%"
    if specialty_filter == "All Specialties":
        cursor.execute("SELECT id, timestamp, specialty, front, back, tags FROM anki_cards WHERE specialty LIKE ? OR front LIKE ? OR back LIKE ? OR tags LIKE ? ORDER BY id DESC", (search_term, search_term, search_term, search_term))
    else:
        cursor.execute("SELECT id, timestamp, specialty, front, back, tags FROM anki_cards WHERE specialty = ? AND (front LIKE ? OR back LIKE ? OR tags LIKE ?) ORDER BY id DESC", (specialty_filter, search_term, search_term, search_term))
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_saved_anki_card(card_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM anki_cards WHERE id = ?", (card_id,))
    conn.commit()
    conn.close()

def delete_multiple_anki_cards(card_ids):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.executemany("DELETE FROM anki_cards WHERE id = ?", [(cid,) for cid in card_ids])
    conn.commit()
    conn.close()

def purge_duplicate_anki_cards():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM anki_cards WHERE id NOT IN (SELECT MIN(id) FROM anki_cards GROUP BY front)")
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_count

def get_persistent_stats():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM cases_log")
    total_cases = cursor.fetchone()[0]
    cursor.execute("SELECT specialty, COUNT(*) FROM cases_log GROUP BY specialty")
    specialty_rows = cursor.fetchall()
    specialty_breakdown = {row[0]: row[1] for row in specialty_rows}
    conn.close()
    return total_cases, specialty_breakdown

def get_mastery_stats():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT confidence_rating, COUNT(*) FROM cases_log GROUP BY confidence_rating")
    rows = cursor.fetchall()
    conn.close()
    stats = {"Again": 0, "Good": 0, "Easy": 0, "Unrated": 0}
    for rating, count in rows:
        if rating in stats:
            stats[rating] = count
        else:
            stats["Unrated"] += count
    return stats

def get_all_cases_from_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, timestamp, specialty, case_content, user_differential, ai_critique, confidence_rating FROM cases_log ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def search_cases_in_db(keyword):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    search_term = f"%{keyword}%"
    cursor.execute("SELECT id, timestamp, specialty, case_content, user_differential, ai_critique, confidence_rating FROM cases_log WHERE specialty LIKE ? OR case_content LIKE ? OR user_differential LIKE ? OR ai_critique LIKE ? ORDER BY id DESC", (search_term, search_term, search_term, search_term))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_filtered_cases_by_criteria(specialty_filter, rating_filter):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    query = "SELECT id, timestamp, specialty, case_content, user_differential, ai_critique, confidence_rating FROM cases_log WHERE 1=1"
    params = []
    if specialty_filter != "All Specialties":
        query += " AND specialty = ?"
        params.append(specialty_filter)
    if rating_filter == "Needs Review (Again)":
        query += " AND confidence_rating = 'Again'"
    elif rating_filter == "Good (Moderate)":
        query += " AND confidence_rating = 'Good'"
    elif rating_filter == "Easy (Mastered)":
        query += " AND confidence_rating = 'Easy'"
    elif rating_filter == "Unrated":
        query += " AND confidence_rating = 'Unrated'"
    query += " ORDER BY id DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_distinct_specialties():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT specialty FROM cases_log ORDER BY specialty")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def get_distinct_anki_specialties():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT specialty FROM anki_cards ORDER BY specialty")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def generate_markdown_export():
    cases = get_all_cases_from_db()
    md = "# 🩺 Usiphu Clinical Study Guide\n\nGenerated from your personal Usiphu Case Archive.\n\n---\n\n"
    for case_id, timestamp, specialty, content, diff, critique, rating in cases:
        md += f"## Case #{case_id} — {specialty} ({timestamp}) [Mastery: {rating}]\n\n{content}\n\n"
        md += f"### 🧠 Your Submitted Differential\n{diff if diff else 'None recorded.'}\n\n"
        md += f"### 🩺 AI Attending Critique\n{critique if critique else 'None recorded.'}\n\n---\n\n"
    return md

def generate_pdf_export():
    if not PDF_AVAILABLE:
        return None
    cases = get_all_cases_from_db()
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", style='B', size=16)
    pdf.cell(200, 10, txt="Usiphu Clinical Study Guide", ln=True, align='C')
    pdf.ln(10)
    for case_id, timestamp, specialty, content, diff, critique, rating in cases:
        pdf.set_font("Arial", style='B', size=12)
        pdf.cell(200, 8, txt=f"Case #{case_id}: {specialty} ({timestamp}) - Mastery: {rating}", ln=True)
        pdf.set_font("Arial", size=9)
        clean_content = content.replace("### ", "").replace("## ", "").replace("*", "")
        pdf.multi_cell(0, 5, txt=clean_content)
        pdf.ln(4)
        pdf.set_font("Arial", style='B', size=10)
        pdf.cell(200, 6, txt="Your Differential Diagnosis:", ln=True)
        pdf.set_font("Arial", size=9)
        pdf.multi_cell(0, 5, txt=str(diff or "None recorded."))
        pdf.ln(4)
        pdf.set_font("Arial", style='B', size=10)
        pdf.cell(200, 6, txt="AI Attending Critique:", ln=True)
        pdf.set_font("Arial", size=9)
        pdf.multi_cell(0, 5, txt=str(critique or "None recorded."))
        pdf.ln(8)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(8)
    return pdf.output(dest='S').encode('latin-1', errors='replace')

init_db()

# --- 3. HEALTH CHECK & MODEL CACHING ---
def check_ollama_status(target_model):
    try:
        response = ollama.list()
        models = [m.get('model', '') for m in response.get('models', [])]
        is_pulled = any(target_model in m for m in models)
        return True, is_pulled, models
    except Exception as e:
        return False, False, str(e)

@st.cache_resource
def get_whisper_model():
    if WHISPER_AVAILABLE:
        return whisper.load_model("base")
    return None

@st.cache_resource
def get_rag_engine():
    data_path = Path("./data")
    if data_path.exists() and any(data_path.iterdir()):
        try:
            from llama_index.core import Settings, SimpleDirectoryReader, VectorStoreIndex
            from llama_index.llms.ollama import Ollama
            from llama_index.embeddings.ollama import OllamaEmbedding
            Settings.llm = Ollama(model="llama3.2", request_timeout=60.0)
            Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")
            docs = SimpleDirectoryReader("./data").load_data()
            index = VectorStoreIndex.from_documents(docs)
            return index.as_query_engine()
        except Exception as e:
            print(f"RAG initialization note: {e}")
    return None

whisper_model = get_whisper_model()
rag_engine = get_rag_engine()

# --- 4. INITIALIZE SESSION STATE ---
for key in ['messages', 'current_case_id', 'case_data', 'diff_graded', 'diff_critique', 'user_diff_input']:
    if key not in st.session_state:
        st.session_state[key] = [] if key == 'messages' else None if key == 'current_case_id' else "" if key in ['diff_critique', 'user_diff_input'] else False

if 'flashcard_index' not in st.session_state: st.session_state['flashcard_index'] = 0
if 'card_flipped' not in st.session_state: st.session_state['card_flipped'] = False
if 'selected_flashcard_specialty' not in st.session_state: st.session_state['selected_flashcard_specialty'] = "All Specialties"
if 'selected_flashcard_rating' not in st.session_state: st.session_state['selected_flashcard_rating'] = "All Ratings"
if 'editable_anki_cards' not in st.session_state: st.session_state['editable_anki_cards'] = []

# --- 5. SIDEBAR DESIGN SYSTEM ---
with st.sidebar:
    st.markdown("<h2 style='text-align: center; color: #58a6ff;'>🩺 Usiphu MD</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #8b949e; font-size: 0.85rem;'>Offline Clinical Intelligence Engine</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    speed_mode = st.toggle("⚡ Fast Generation (llama3.2)", value=True)
    model_name = "llama3.2" if speed_mode else st.selectbox("Ollama Engine", ["llama3.1:8b", "mistral"], index=0)
    
    is_online, is_pulled, details = check_ollama_status(model_name)
    if is_online:
        st.success(f"🟢 **Online** (`{model_name}`)")
    else:
        st.error("🔴 **Offline** (Run `ollama serve`)")

    st.markdown("---")
    nav_mode = st.radio("Navigation", ["Clinical Workspace", "Flashcard Review", "Anki Deck Exporter", "Anki Card Bank", "Case Archive"])
    
    st.markdown("---")
    st.markdown("<h4 style='color: #f0f6fc;'>📊 Engine Analytics</h4>", unsafe_allow_html=True)
    total_cases, specialty_breakdown = get_persistent_stats()
    saved_anki_count = get_saved_anki_card_count()
    
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.metric("Total Cases", total_cases)
    with col_s2:
        st.metric("Anki Cards", saved_anki_count)

    st.markdown("---")
    st.markdown("<h4 style='color: #f0f6fc;'>⚙️ Case Generator</h4>", unsafe_allow_html=True)
    extended_specialties = [
        "Cardiology", "Pulmonology", "Neurology", "Emergency Medicine", 
        "Infectious Disease", "Endocrinology", "Gastroenterology", 
        "Nephrology", "Hematology & Oncology", "Rheumatology", 
        "Critical Care", "General Surgery", "Obstetrics & Gynecology", 
        "Pediatrics", "Psychiatry", "Dermatology"
    ]
    specialty = st.selectbox("Medical Specialty", extended_specialties)

    if st.button("🔄 Generate New Case", type="primary", use_container_width=True):
        if not is_online:
            st.error("Ollama server is offline.")
        else:
            with st.spinner(f"Synthesizing {specialty} case..."):
                context_text = ""
                if rag_engine:
                    try:
                        rag_response = rag_engine.query(f"Provide diagnostic guidelines for {specialty}")
                        context_text = f"\nGuidelines Context:\n{str(rag_response)}\n"
                    except Exception:
                        pass

                prompt = f"""
                You are a senior medical attending. Create a high-yield clinical case vignette for medical board prep in {specialty}.
                {context_text}
                Format clearly with these exact headers:
                
                ### 📋 Patient Presentation
                (Include brief HPI, relevant vitals, and exam findings)
                
                ### ❓ Question & Options
                (A single best-answer multiple-choice board question with options A, B, C, D)
                
                ### 💡 Correct Answer & Explanation
                (State the correct answer clearly, explain why it's correct, and why others are incorrect)
                """
                try:
                    response = ollama.chat(model=model_name, messages=[{"role": "user", "content": prompt}])
                    full_case = response['message']['content']
                    new_id = log_new_case(specialty, full_case)
                    
                    st.session_state['current_case_id'] = new_id
                    st.session_state['case_data'] = full_case
                    st.session_state['diff_graded'] = False
                    st.session_state['diff_critique'] = ""
                    st.session_state['user_diff_input'] = ""
                    st.session_state['messages'] = [
                        {"role": "assistant", "content": f"New **{specialty}** case loaded (ID: {new_id}). Submit your differential diagnosis below!"}
                    ]
                except Exception as e:
                    st.error(f"Error: {e}")

# --- 6. VIEW ROUTING ---
if nav_mode == "Clinical Workspace":
    st.title("🩺 Clinical Workspace")
    st.caption("Active Reasoning, Local Voice Dictation & Real-Time Auto-Saving")

    if st.session_state['case_data']:
        case_parts = st.session_state['case_data'].split("### ❓ Question & Options")
        presentation_part = case_parts[0]
        remaining_part = case_parts[1] if len(case_parts) > 1 else ""
        question_parts = remaining_part.split("### 💡 Correct Answer & Explanation")
        question_part = question_parts[0]
        explanation_part = question_parts[1] if len(question_parts) > 1 else ""

        st.markdown(presentation_part)
        st.markdown("---")
        st.subheader("🧠 Differential Diagnosis & Diagnostic Plan")
        
        if WHISPER_AVAILABLE and whisper_model:
            audio_value = st.audio_input("🎙️ Dictate Differential (Whisper Voice-to-Text)")
            if audio_value is not None:
                with st.spinner("Transcribing audio..."):
                    audio_path = "temp_voice.wav"
                    with open(audio_path, "wb") as f:
                        f.write(audio_value.getbuffer())
                    transcript = whisper_model.transcribe(audio_path)
                    spoken = transcript["text"].strip()
                    if spoken:
                        st.session_state['user_diff_input'] += f"\n{spoken}"
                        auto_save_differential_draft(st.session_state['current_case_id'], st.session_state['user_diff_input'])
                    if os.path.exists(audio_path):
                        os.remove(audio_path)

        user_diff = st.text_area(
            "Your Clinical Reasoning:",
            value=st.session_state['user_diff_input'],
            placeholder="1. Primary Diagnosis: ...\n2. Differential Alternatives: ...\n3. Next Diagnostic/Management Steps: ...",
            key="diff_text_box"
        )
        
        if user_diff != st.session_state['user_diff_input']:
            st.session_state['user_diff_input'] = user_diff
            auto_save_differential_draft(st.session_state['current_case_id'], user_diff)
        
        col_act1, col_act2 = st.columns([2, 1])
        with col_act1:
            if st.button("Submit for AI Attending Critique", type="secondary", use_container_width=True):
                if user_diff.strip():
                    with st.spinner("Evaluating clinical reasoning..."):
                        critique_prompt = f"You are a senior medical attending. Case: {presentation_part}\nResident Differential: {user_diff}\nProvide a concise, high-yield critique of their reasoning."
                        critique_res = ollama.chat(model=model_name, messages=[{"role": "user", "content": critique_prompt}])
                        critique_text = critique_res['message']['content']
                        st.session_state['diff_critique'] = critique_text
                        st.session_state['diff_graded'] = True
                        if st.session_state['current_case_id']:
                            save_differential_and_critique(st.session_state['current_case_id'], user_diff, critique_text)
                else:
                    st.warning("Please enter your differential first.")
        with col_act2:
            st.caption("💾 *Draft auto-saved to SQLite database.*")

        if st.session_state.get('diff_graded', False):
            st.success("✅ Differential Graded by Attending AI")
            st.markdown(st.session_state['diff_critique'])
            
            st.markdown("---")
            st.subheader("❓ Board Question & Options")
            st.markdown("### ❓ Question & Options" + question_part)
            
            st.markdown("---")
            st.subheader("💡 Answer & Explanation")
            with st.expander("Reveal Explanation", expanded=True):
                st.markdown(explanation_part)
    else:
        st.info("👈 Click **'🔄 Generate New Case'** in the sidebar to begin your clinical study session.")

    st.markdown("---")
    st.subheader("💬 Clinical Attending Chat")
    for msg in st.session_state['messages']:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt_input := st.chat_input("Ask about pathophysiology, lab results, or contraindications..."):
        st.session_state['messages'].append({"role": "user", "content": prompt_input})
        with st.chat_message("user"):
            st.markdown(prompt_input)
        with st.chat_message("assistant"):
            with st.spinner("Consulting literature..."):
                history = [{"role": m["role"], "content": m["content"]} for m in st.session_state['messages']]
                stream_res = ollama.chat(model=model_name, messages=history, stream=True)
                box = st.empty()
                ans = ""
                for chunk in stream_res:
                    ans += chunk['message']['content']
                    box.markdown(ans + "▌")
                box.markdown(ans)
                st.session_state['messages'].append({"role": "assistant", "content": ans})

elif nav_mode == "Flashcard Review":
    st.title("📇 Flashcard Review Mode")
    st.caption("Spaced-repetition review of active cases.")
    
    distinct_specs = get_distinct_specialties()
    if not distinct_specs:
        st.info("No cases archived yet.")
    else:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            selected_spec = st.selectbox("Specialty Filter", ["All Specialties"] + distinct_specs)
        with col_f2:
            selected_rating = st.selectbox("Mastery Status", ["All Ratings", "Needs Review (Again)", "Good (Moderate)", "Easy (Mastered)", "Unrated"])
        
        filtered_cases = get_filtered_cases_by_criteria(selected_spec, selected_rating)
        
        if not filtered_cases:
            st.warning("No cards match your filter criteria.")
        else:
            total_cards = len(filtered_cases)
            if st.session_state['flashcard_index'] >= total_cards:
                st.session_state['flashcard_index'] = 0
                
            card = filtered_cases[st.session_state['flashcard_index']]
            case_id, timestamp, spec_tag, content, diff, critique, rating = card
            
            parts = content.split("### ❓ Question & Options")
            front_text = parts[0]
            rem = parts[1] if len(parts) > 1 else ""
            q_parts = rem.split("### 💡 Correct Answer & Explanation")
            q_text = q_parts[0]
            exp_text = q_parts[1] if len(q_parts) > 1 else ""

            col_p1, col_p2, col_p3 = st.columns([1, 2, 1])
            with col_p1:
                if st.button("⬅️ Previous"):
                    st.session_state['flashcard_index'] = (st.session_state['flashcard_index'] - 1) % total_cards
                    st.session_state['card_flipped'] = False
                    st.rerun()
            with col_p2:
                st.markdown(f"<div style='text-align:center; font-weight: 600;'>Card {st.session_state['flashcard_index'] + 1} of {total_cards} | [{spec_tag}]</div>", unsafe_allow_html=True)
            with col_p3:
                if st.button("Next ➡️"):
                    st.session_state['flashcard_index'] = (st.session_state['flashcard_index'] + 1) % total_cards
                    st.session_state['card_flipped'] = False
                    st.rerun()
                    
            st.markdown("---")
            st.subheader("📋 Patient Presentation")
            st.markdown(front_text)
            
            st.markdown("---")
            if not st.session_state['card_flipped']:
                if st.button("🔄 Flip Card (Reveal Answer)", type="primary", use_container_width=True):
                    st.session_state['card_flipped'] = True
                    st.rerun()
            else:
                if st.button("🔄 Flip Card Back", use_container_width=True):
                    st.session_state['card_flipped'] = False
                    st.rerun()
                    
                st.markdown("---")
                st.subheader("❓ Board Question & Explanation")
                st.markdown("### ❓ Question & Options" + q_text)
                st.markdown(exp_text)
                
                st.markdown("---")
                st.subheader("🎯 Rate Mastery")
                r1, r2, r3 = st.columns(3)
                with r1:
                    if st.button("🔴 Again", use_container_width=True):
                        update_case_confidence(case_id, "Again")
                        st.rerun()
                with r2:
                    if st.button("🟡 Good", use_container_width=True):
                        update_case_confidence(case_id, "Good")
                        st.rerun()
                with r3:
                    if st.button("🟢 Easy", use_container_width=True):
                        update_case_confidence(case_id, "Easy")
                        st.rerun()

elif nav_mode == "Anki Deck Exporter":
    st.title("📴 Multi-Source Anki Deck Exporter")
    st.caption("Generate pristine board cards, edit inline, and save to SQLite.")
    
    source_choice = st.selectbox(
        "Select Flashcard Generation Source:",
        [
            "Source A: Local RAG Knowledge Base (Your PDFs in `./data`)",
            "Source B: Open Anki Medical Decks (Community Open Decks)",
            "Source C: Free Medical Exam Prep Sites & Repositories",
            "Source D: Your Personal Usiphu Case Archive"
        ]
    )
    
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        export_specialty = st.selectbox("Target Specialty", ["Cardiology", "Pulmonology", "Neurology", "Emergency Medicine", "Infectious Disease", "General Internal Medicine", "Pediatrics", "Surgery", "Nephrology"])
    with col_e2:
        board_tag = st.selectbox("Board Exam Tagging", ["#USMLE_Step2_CK", "#USMLE_Step1", "#ABIM_Board_Review", "#General_Clinical_Pearls"])
        
    card_count = st.slider("Number of High-Yield Cards to Generate", min_value=5, max_value=25, value=10)

    if st.button("⚡ Generate Pristine Exam Cards", type="primary"):
        with st.spinner(f"Synthesizing board-exam flashcards for {export_specialty}..."):
            source_context = ""
            if "Source A" in source_choice and rag_engine:
                try:
                    res = rag_engine.query(f"Extract key clinical pearls, diagnostics, and treatments for {export_specialty}")
                    source_context = str(res)
                except Exception:
                    pass
            else:
                cases = get_all_cases_from_db()
                source_context = "\n".join([c[3] for c in cases[:10]])

            anki_prompt = f"""
            Generate exactly {card_count} pristine high-yield medical flashcards for {export_specialty}.
            Tag: {board_tag}
            Source Material: {source_context}
            Output strictly TSV format with three columns: [Front] \\t [Back] \\t [Tags]. No markdown headers.
            """
            try:
                resp = ollama.chat(model=model_name, messages=[{"role": "user", "content": anki_prompt}])
                raw_tsv = resp['message']['content'].strip()
                
                rows = []
                for line in raw_tsv.split("\n"):
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        rows.append({"Front": parts[0], "Back": parts[1], "Tags": parts[2]})
                    elif len(parts) == 2:
                        rows.append({"Front": parts[0], "Back": parts[1], "Tags": f"{board_tag} #{export_specialty.replace(' ', '_')} #HighYield"})
                
                st.session_state['editable_anki_cards'] = rows
                st.success(f"Generated {len(rows)} pristine exam cards!")
            except Exception as e:
                st.error(f"Generation error: {e}")

    if st.session_state['editable_anki_cards']:
        st.markdown("---")
        st.subheader("📝 Pristine Card Preview & Editor")
        
        import pandas as pd
        df_cards = pd.DataFrame(st.session_state['editable_anki_cards'])
        edited_df = st.data_editor(df_cards, num_rows="dynamic", use_container_width=True, key="anki_editor")
        current_edited_cards = edited_df.to_dict(orient="records")
        
        col_db1, col_db2 = st.columns(2)
        with col_db1:
            if st.button("💾 Save Unique Cards to SQLite", type="secondary", use_container_width=True):
                added, dupes = save_anki_cards_to_db(current_edited_cards, export_specialty)
                st.success(f"Saved **{added}** new card(s) to SQLite! Skipped **{dupes}** duplicate(s).")
        with col_db2:
            st.metric("Cards in Bank", get_saved_anki_card_count())
            
        tsv_output = ""
        for index, row in edited_df.iterrows():
            if pd.notna(row['Front']) and pd.notna(row['Back']):
                tags = row['Tags'] if pd.notna(row['Tags']) else f"{board_tag} #{export_specialty.replace(' ', '_')}"
                tsv_output += f"{row['Front']}\t{row['Back']}\t{tags}\n"
        
        st.download_button("📥 Download Anki Deck (.txt)", tsv_output, f"usiphu_exam_deck_{export_specialty.lower().replace(' ', '_')}.txt", "text/plain", use_container_width=True)

elif nav_mode == "Anki Card Bank":
    st.title("📚 Persistent Anki Card Bank")
    st.caption("Search, view, batch delete, and export saved SQLite flashcards.")
    
    distinct_anki_specs = get_distinct_anki_specialties()
    col_b1, col_b2 = st.columns([2, 1])
    with col_b1:
        search_query = st.text_input("🔍 Search Card Bank:", value="")
    with col_b2:
        bank_spec_filter = st.selectbox("Filter Specialty", ["All Specialties"] + distinct_anki_specs)
        
    saved_cards = search_saved_anki_cards(search_query.strip(), bank_spec_filter) if search_query.strip() else (get_all_saved_anki_cards() if bank_spec_filter == "All Specialties" else search_saved_anki_cards("", bank_spec_filter))
    st.write(f"Found **{len(saved_cards)}** saved card(s).")
    
    if saved_cards:
        st.markdown("---")
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            if st.button("🧹 Purge Duplicates", type="secondary", use_container_width=True):
                purged_count = purge_duplicate_anki_cards()
                st.success(f"Purged **{purged_count}** duplicate card(s)!")
                st.rerun()
        with col_m2:
            st.metric("Total Cards in SQLite", get_saved_anki_card_count())
            
        import pandas as pd
        bank_rows = [{"Select": False, "ID": cid, "Specialty": spec, "Front": front, "Back": back, "Tags": tags, "Created": ts} for cid, ts, spec, front, back, tags in saved_cards]
        edited_bank_df = st.data_editor(pd.DataFrame(bank_rows), column_config={"Select": st.column_config.CheckboxColumn("Select", default=False), "ID": st.column_config.NumberColumn("ID", disabled=True)}, disabled=["ID", "Specialty", "Front", "Back", "Tags", "Created"], hide_index=True, use_container_width=True, key="bank_batch_editor")
        
        selected_rows = edited_bank_df[edited_bank_df["Select"] == True]
        selected_ids = selected_rows["ID"].tolist()
        
        col_act1, col_act2 = st.columns(2)
        with col_act1:
            if st.button(f"🗑️ Delete Selected ({len(selected_ids)})", type="secondary", use_container_width=True, disabled=len(selected_ids) == 0):
                delete_multiple_anki_cards(selected_ids)
                st.success(f"Deleted {len(selected_ids)} card(s)!")
                st.rerun()
        with col_act2:
            target_export_rows = selected_rows if len(selected_ids) > 0 else edited_bank_df
            export_tsv = "".join([f"{r['Front']}\t{r['Back']}\t{r['Tags']}\n" for _, r in target_export_rows.iterrows()])
            st.download_button("📥 Export Selected to Anki", export_tsv, "usiphu_batch_anki_deck.txt", "text/plain", use_container_width=True)

else:
    st.title("📂 Case History Archive & Database Admin")
    st.caption("Manage persistent SQLite database backups, restores, and study guide exports.")
    
    st.subheader("💾 System Persistence Utilities")
    col_bk1, col_bk2 = st.columns(2)
    with col_bk1:
        st.markdown("**1. Backup Active Database**")
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "rb") as f:
                st.download_button("📥 Download Backup (usiphu.db)", f.read(), "usiphu_backup.db", "application/x-sqlite3", use_container_width=True)
    with col_bk2:
        st.markdown("**2. Restore Database from Backup**")
        uploaded_db = st.file_uploader("Upload Usiphu Backup (.db)", type=["db", "sqlite3"])
        if uploaded_db is not None and st.button("⚠️ Confirm & Overwrite Database", type="primary", use_container_width=True):
            with open(DB_FILE, "wb") as f:
                f.write(uploaded_db.getbuffer())
            st.success("✅ Database restored!")
            st.rerun()

    st.markdown("---")
    st.subheader("⚠️ Danger Zone: Factory Reset")
    with st.expander("🗑️ Wipe All Data & Reset Database", expanded=False):
        confirm_wipe = st.checkbox("I understand this will permanently delete all offline Usiphu data.")
        if st.button("🚨 Wipe Database & Reset", type="primary", disabled=not confirm_wipe):
            if os.path.exists(DB_FILE):
                os.remove(DB_FILE)
            init_db()
            for key in ['current_case_id', 'case_data', 'diff_graded', 'diff_critique', 'user_diff_input', 'editable_anki_cards', 'messages']:
                st.session_state[key] = [] if key in ['messages', 'editable_anki_cards'] else None if key == 'current_case_id' else "" if key in ['diff_critique', 'user_diff_input'] else False
            st.success("✅ Factory reset complete!")
            st.rerun()

    st.markdown("---")
    search_kw = st.text_input("🔍 Search Archive Keywords:", value="")
    archived = search_cases_in_db(search_kw.strip()) if search_kw.strip() else get_all_cases_from_db()
    st.write(f"Found **{len(archived)}** case(s).")
    
    if archived:
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("📥 Download Markdown Study Guide", generate_markdown_export(), "usiphu_guide.md", "text/markdown", use_container_width=True)
        with c2:
            if PDF_AVAILABLE:
                st.download_button("📥 Download PDF Study Guide", generate_pdf_export(), "usiphu_guide.pdf", "application/pdf", use_container_width=True)
