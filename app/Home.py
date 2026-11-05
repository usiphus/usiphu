if not AUTH_REQUIRED or admin_access or reviewer_access:
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
                        extracted_items = [
                            *extracted.get("mcq_candidates", []),
                            *extracted.get("meq_page_candidates", []),
                        ]
                        for candidate in extracted_items:
                            enqueue_assessment_for_review(
                                candidate["candidate_id"],
                                candidate.get("question_type", "extracted_candidate"),
                                {**candidate, "source_id": extracted.get("source_id"),
                                 "source_title": extracted.get("source_title"),
                                 "source_filename": extracted.get("source_filename")},
                            )
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

else:
    st.info("The Source Inbox is restricted to administrators and faculty reviewers.")

st.divider()
st.caption(
    "Educational use only. Verify clinical information against current guidelines and local protocols. "
    "Editorial drafts are not clinically approved."
)
