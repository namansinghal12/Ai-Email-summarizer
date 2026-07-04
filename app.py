import os
import json
import pandas as pd
import streamlit as st
import datetime
from pathlib import Path
from dateutil import parser as date_parser

import config
from utils import logger, export_summary_to_pdf, get_tts_html
from gmail_service import (
    get_gmail_service, 
    fetch_emails, 
    get_message_detail, 
    apply_labels_to_email,
    mark_email_as_read
)
from summarizer import summarize_email, generate_daily_digest

# Page configuration
st.set_page_config(
    page_title="AI Email Summarizer",
    page_icon="📬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Cache file setup
CACHE_FILE = config.DATA_DIR / "summaries_cache.json"

def load_cache() -> dict:
    """Loads email summaries from local cache file."""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
    return {}

def save_cache(cache: dict):
    """Saves email summaries to local cache file."""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Error saving cache: {e}")

# Inject Custom CSS for premium design
st.markdown("""
<style>
    /* Styling Badges */
    .priority-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        text-align: center;
    }
    .badge-high {
        background-color: #fee2e2;
        color: #ef4444;
        border: 1px solid #fca5a5;
    }
    .badge-medium {
        background-color: #ffedd5;
        color: #f97316;
        border: 1px solid #fdbb2d;
    }
    .badge-low {
        background-color: #d1fae5;
        color: #10b981;
        border: 1px solid #6ee7b7;
    }
    .category-tag {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 500;
        background-color: #f1f5f9;
        color: #475569;
        border: 1px solid #cbd5e1;
        margin-left: 5px;
    }
    .sentiment-tag {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 500;
        margin-left: 5px;
    }
    .sent-positive {
        background-color: #d1fae5;
        color: #065f46;
    }
    .sent-neutral {
        background-color: #f3f4f6;
        color: #374151;
    }
    .sent-negative {
        background-color: #fee2e2;
        color: #991b1b;
    }
    /* Meta text styling */
    .email-meta {
        font-size: 12px;
        color: #64748b;
        margin-bottom: 2px;
    }
    /* App header gradient */
    .header-gradient {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        margin-bottom: 25px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "gmail_connected" not in st.session_state:
    st.session_state.gmail_connected = False
if "emails" not in st.session_state:
    st.session_state.emails = [] # Active list of emails displayed
if "selected_email_id" not in st.session_state:
    st.session_state.selected_email_id = None
if "api_key" not in st.session_state:
    st.session_state.api_key = config.GEMINI_API_KEY
if "daily_digest" not in st.session_state:
    st.session_state.daily_digest = ""

# Load cache
cache = load_cache()

# Header banner
st.markdown("""
<div class="header-gradient">
    <h1 style="margin: 0; font-size: 2.5rem; font-weight: 700;">📬 AI Email Summarizer & Assistant</h1>
    <p style="margin: 5px 0 0 0; opacity: 0.8; font-size: 1rem;">
        Authenticate with Gmail, download unread emails, and use Gemini AI to generate summaries, action items, and replies.
    </p>
</div>
""", unsafe_allow_html=True)

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/gmail-new.png", width=60)
    st.title("Settings & Actions")
    st.markdown("---")
    
    # 1. API Keys Status
    st.subheader("🔑 API Key Status")
    api_key_input = st.text_input(
        "Google Gemini API Key",
        value=st.session_state.api_key,
        type="password",
        help="Get an API key from Google AI Studio"
    )
    if api_key_input:
        st.session_state.api_key = api_key_input
        st.success("API Key Loaded!")
    else:
        st.warning("Please enter your Gemini API Key or set GEMINI_API_KEY in .env.")
        
    st.markdown("---")
    
    # 2. Gmail Auth Card
    st.subheader("📧 Gmail Account")
    
    # Verify if credentials file is present
    has_credentials = config.CREDENTIALS_FILE.exists()
    
    if not has_credentials:
        st.error("Missing `credentials.json`!")
        st.markdown(
            "Please create a project in Google Cloud Console, enable the Gmail API, "
            f"download the OAuth 2.0 Credentials file, rename it to `credentials.json`, "
            f"and place it inside the `credentials/` folder."
        )
    else:
        # Check if token file already exists
        has_token = config.TOKEN_FILE.exists()
        
        if has_token:
            st.success("Connected to Gmail")
            st.session_state.gmail_connected = True
        else:
            st.warning("Not Connected")
            if st.button("🔌 Connect Gmail Account", use_container_width=True):
                with st.spinner("Opening browser for OAuth login. Please authorize the app..."):
                    try:
                        # This starts local OAuth flow
                        get_gmail_service()
                        st.session_state.gmail_connected = True
                        st.success("Connected successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Authentication failed: {e}")
                        
    st.markdown("---")
    
    # 3. Settings Filters
    st.subheader("⚙️ Fetch Config")
    selected_filter = st.selectbox(
        "Email Filter",
        options=list(config.SUPPORTED_FILTERS.keys()),
        index=0,
        help="Select which filter query to run in Gmail"
    )
    
    max_emails = st.slider(
        "Max Emails to Fetch",
        min_value=5,
        max_value=50,
        value=config.DEFAULT_MAX_EMAILS,
        step=5
    )
    
    # 4. Actions
    st.subheader("🚀 Operations")
    
    fetch_btn = st.button(
        "🔄 Fetch & Analyze Emails", 
        type="primary", 
        use_container_width=True,
        disabled=not st.session_state.gmail_connected or not st.session_state.api_key
    )
    
    digest_btn = st.button(
        "📝 Generate Daily Digest", 
        use_container_width=True,
        disabled=len(st.session_state.emails) == 0 or not st.session_state.api_key
    )
    
    clear_cache_btn = st.button("🗑️ Clear Local Cache", use_container_width=True)

# Clear Cache Operation
if clear_cache_btn:
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
    st.session_state.emails = []
    st.session_state.selected_email_id = None
    st.session_state.daily_digest = ""
    st.success("Cache and local session cleared!")
    st.rerun()

# ==========================================
# GMAIL FETCH & GEMINI SUMMARIZATION
# ==========================================
if fetch_btn:
    with st.spinner("Connecting to Gmail and fetching emails..."):
        try:
            service = get_gmail_service()
            query = config.SUPPORTED_FILTERS[selected_filter]
            msg_list = fetch_emails(service, query, max_results=max_emails)
            
            if not msg_list:
                st.info("Inbox is clean! No unread emails matching this filter.")
                st.session_state.emails = []
            else:
                emails_processed = []
                progress_text = "Parsing and summarizing emails..."
                progress_bar = st.progress(0.0, text=progress_text)
                
                # Load cache again to make sure it's fresh
                cache = load_cache()
                cache_updated = False
                
                for idx, msg in enumerate(msg_list):
                    msg_id = msg["id"]
                    
                    # 1. Check Cache
                    if msg_id in cache:
                        emails_processed.append(cache[msg_id])
                    else:
                        # 2. Fetch from Gmail API
                        detail = get_message_detail(service, msg_id)
                        if detail:
                            # 3. Summarize using Gemini
                            logger.info(f"Summarizing email ID {msg_id} with Gemini...")
                            summary = summarize_email(
                                email_text=detail["body"],
                                subject=detail["subject"],
                                sender=detail["sender"],
                                api_key=st.session_state.api_key
                            )
                            
                            processed_item = {
                                "email": detail,
                                "summary": summary,
                                "fetched_at": datetime.datetime.now().isoformat()
                            }
                            
                            # 4. Auto Labels (Bonus Feature)
                            # Create and apply Gmail labels
                            label_names = ["AI-Summarized"]
                            if summary.get("priority") == "High":
                                label_names.append("AI-High-Priority")
                            apply_labels_to_email(service, msg_id, label_names)
                            
                            # Update Cache
                            cache[msg_id] = processed_item
                            cache_updated = True
                            emails_processed.append(processed_item)
                            
                    # Update progress bar
                    progress_bar.progress((idx + 1) / len(msg_list), text=f"Processed {idx+1}/{len(msg_list)} emails...")
                
                if cache_updated:
                    save_cache(cache)
                    
                st.session_state.emails = emails_processed
                # Reset selected email
                if emails_processed:
                    st.session_state.selected_email_id = emails_processed[0]["email"]["id"]
                
                progress_bar.empty()
                st.success(f"Successfully processed {len(emails_processed)} emails!")
                
                # Smart Notification Check (Bonus Feature)
                high_priority_count = sum(1 for e in emails_processed if e["summary"].get("priority") == "High")
                if high_priority_count > 0:
                    st.toast(f"🚨 {high_priority_count} High Priority emails detected!", icon="⚠️")
                    
        except Exception as e:
            st.error(f"Failed to fetch and analyze emails: {e}")
            logger.error(f"Fetch and analyze error: {e}", exc_info=True)

# Generate Daily Digest Operation
if digest_btn:
    with st.spinner("Summarizing all emails into a unified digest..."):
        try:
            digest = generate_daily_digest(st.session_state.emails, api_key=st.session_state.api_key)
            st.session_state.daily_digest = digest
            st.toast("Daily Digest Generated!", icon="📝")
        except Exception as e:
            st.error(f"Failed to generate Daily Digest: {e}")

# ==========================================
# MAIN PAGE DISPLAY
# ==========================================
# Load cached emails into session state if they aren't loaded yet
if not st.session_state.emails and cache:
    # Sort emails by dates descending if possible
    cached_list = list(cache.values())
    try:
        cached_list.sort(
            key=lambda x: date_parser.parse(x["email"]["date"]) if x["email"]["date"] else datetime.datetime.min, 
            reverse=True
        )
    except Exception:
        pass
    st.session_state.emails = cached_list
    if cached_list:
        st.session_state.selected_email_id = cached_list[0]["email"]["id"]

# Create Tabs for Dashboard
dashboard_tab, analytics_tab, digest_tab = st.tabs(["📬 Inbox & Summaries", "📊 Email Analytics", "📝 Daily Digest"])

# ==========================================
# TAB 1: INBOX & SUMMARIES
# ==========================================
with dashboard_tab:
    if not st.session_state.emails:
        st.info("No email data loaded. Please authenticate and click **Fetch & Analyze Emails** in the sidebar.")
        
        # Display instructions/features
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("#### ⚡ 1. OAuth Authentication")
            st.write("Securely log in to your personal Gmail account. We only access what is needed to parse and label processed emails.")
        with col2:
            st.markdown("#### 🤖 2. Gemini AI Processing")
            st.write("Generates summary sentences, identifies deadlines and action items, and drafts context-aware suggested replies in seconds.")
        with col3:
            st.markdown("#### 📊 3. Analytics & Export")
            st.write("Track priority distributions and export your records as structured JSON, clean tabular CSV, or modern styled PDF reports.")
    else:
        # 1. Search Bar
        search_query = st.text_input("🔍 Search emails (by Sender, Subject, Summary, Category, or Priority)", "").strip().lower()
        
        # Filter emails based on search query
        filtered_emails = []
        for e in st.session_state.emails:
            subject = e["email"].get("subject", "").lower()
            sender = e["email"].get("sender", "").lower()
            summary = e["summary"].get("summary", "").lower()
            detailed = e["summary"].get("detailed_summary", "").lower()
            category = e["summary"].get("category", "").lower()
            priority = e["summary"].get("priority", "").lower()
            
            if (search_query in subject or 
                search_query in sender or 
                search_query in summary or 
                search_query in detailed or 
                search_query in category or 
                search_query in priority):
                filtered_emails.append(e)
                
        if not filtered_emails:
            st.warning("No emails match your search filter.")
        else:
            # 2. Main columns split: Left Email Cards List, Right Summary details
            col_list, col_details = st.columns([2, 3])
            
            with col_list:
                st.subheader(f"Inbox Messages ({len(filtered_emails)})")
                
                # Check if current selected_email_id is still in filtered_emails, if not, choose first
                valid_ids = [e["email"]["id"] for e in filtered_emails]
                if st.session_state.selected_email_id not in valid_ids:
                    st.session_state.selected_email_id = valid_ids[0]
                    
                # Loop to render clean Streamlit-native list cards
                for item in filtered_emails:
                    email_id = item["email"]["id"]
                    subj = item["email"].get("subject", "(No Subject)")
                    snd = item["email"].get("sender", "Unknown")
                    
                    # Clean sender address to display short name
                    sender_name = snd.split("<")[0].strip() or snd
                    
                    priority = item["summary"].get("priority", "Medium")
                    category = item["summary"].get("category", "Personal")
                    
                    # Color class based on priority
                    p_class = "badge-low"
                    if priority == "High":
                        p_class = "badge-high"
                    elif priority == "Medium":
                        p_class = "badge-medium"
                        
                    is_selected = (email_id == st.session_state.selected_email_id)
                    
                    # Renders container with bold outline if selected
                    with st.container(border=True):
                        # Subject & Date
                        c_header, c_sel = st.columns([5, 1.2])
                        with c_header:
                            st.markdown(f"**{subj[:50]}...**" if len(subj) > 50 else f"**{subj}**")
                            st.markdown(f"<div class='email-meta'>From: {sender_name}</div>", unsafe_allow_html=True)
                            
                            # Row of badges
                            st.markdown(
                                f"<span class='priority-badge {p_class}'>{priority}</span>"
                                f"<span class='category-tag'>{category}</span>",
                                unsafe_allow_html=True
                            )
                        with c_sel:
                            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                            if is_selected:
                                st.button("Selected", key=f"sel_{email_id}", type="primary", disabled=True, use_container_width=True)
                            else:
                                if st.button("View", key=f"view_{email_id}", use_container_width=True):
                                    st.session_state.selected_email_id = email_id
                                    st.rerun()
            
            # 3. Details Panel on Right
            with col_details:
                # Find the selected email dictionary
                sel_email = next((e for e in st.session_state.emails if e["email"]["id"] == st.session_state.selected_email_id), None)
                
                if not sel_email:
                    st.info("Select an email from the left pane to view details.")
                else:
                    email_meta = sel_email["email"]
                    sum_meta = sel_email["summary"]
                    
                    st.subheader("🔍 Summary & Analysis")
                    
                    # Display email header metadata
                    st.markdown(f"### {email_meta.get('subject', '(No Subject)')}")
                    st.write(f"**From:** {email_meta.get('sender')}")
                    st.write(f"**To:** {email_meta.get('receiver')}")
                    st.write(f"**Date:** {email_meta.get('date')}")
                    if email_meta.get("attachments_count", 0) > 0:
                        st.write(f"📎 **Attachments:** {email_meta.get('attachments_count')} files")
                        
                    st.markdown("---")
                    
                    # Display analysis parameters as visual badges
                    p_val = sum_meta.get("priority", "Medium")
                    p_badge = "badge-low"
                    if p_val == "High":
                        p_badge = "badge-high"
                    elif p_val == "Medium":
                        p_badge = "badge-medium"
                        
                    sentiment = sum_meta.get("sentiment", "Neutral")
                    sent_badge = "sent-neutral"
                    if sentiment == "Positive":
                        sent_badge = "sent-positive"
                    elif sentiment == "Negative":
                        sent_badge = "sent-negative"
                        
                    # Row of Badges
                    st.markdown(
                        f"Priority: <span class='priority-badge {p_badge}'>{p_val}</span> | "
                        f"Category: <span class='category-tag'>{sum_meta.get('category', 'Personal')}</span> | "
                        f"Sentiment: <span class='sentiment-tag {sent_badge}'>{sentiment}</span>",
                        unsafe_allow_html=True
                    )
                    
                    # Importance Score Progress Bar
                    score = sum_meta.get("importance_score", 50)
                    st.markdown(f"**Importance Score: {score}/100**")
                    st.progress(score / 100)
                    
                    # Create Tabs for Summary details
                    sum_tabs = st.tabs(["💡 AI Summary", "📋 Action Items", "✉️ Draft Reply", "📝 Cleaned Body"])
                    
                    with sum_tabs[0]:
                        st.markdown(f"#### One Sentence Summary")
                        st.markdown(f"*{sum_meta.get('summary', 'No summary available.')}*")
                        
                        st.markdown("#### Detailed Summary")
                        st.write(sum_meta.get("detailed_summary", "No detailed summary available."))
                        
                        # TTS Button (Bonus Feature)
                        tts_text = f"Subject: {email_meta.get('subject')}. Summary: {sum_meta.get('summary')}. Detailed summary: {sum_meta.get('detailed_summary')}"
                        st.components.v1.html(get_tts_html(tts_text), height=60)
                        
                    with sum_tabs[1]:
                        # Deadline Warning Card
                        deadline = sum_meta.get("deadline")
                        if deadline:
                            st.warning(f"⏰ **Extracted Deadline**: {deadline}")
                        else:
                            st.info("No specific deadline mentioned in the email.")
                            
                        st.markdown("#### Action Items")
                        actions = sum_meta.get("action_items", [])
                        if actions:
                            for action in actions:
                                st.markdown(f"- {action}")
                        else:
                            st.write("No direct action items identified.")
                            
                    with sum_tabs[2]:
                        st.markdown("#### Suggested Reply Draft")
                        reply_text = sum_meta.get("suggested_reply", "")
                        if reply_text:
                            # st.code provides copy-to-clipboard button in Streamlit natively
                            st.code(reply_text, language="markdown")
                            
                            # Mark email as read checkbox button
                            col_read, _ = st.columns([2, 1])
                            with col_read:
                                if st.button("Mark Email as Read in Gmail", key=f"read_{email_meta['id']}", use_container_width=True):
                                    try:
                                        service = get_gmail_service()
                                        mark_email_as_read(service, email_meta["id"])
                                        st.success("Marked as read in Gmail!")
                                    except Exception as e:
                                        st.error(f"Could not update status: {e}")
                        else:
                            st.write("No reply draft generated.")
                            
                    with sum_tabs[3]:
                        st.markdown("#### Cleaned Email Body")
                        st.text_area(
                            label="Cleaned text content passed to Gemini AI",
                            value=email_meta.get("body", "(Empty Content)"),
                            height=300,
                            disabled=True
                        )
                    
                    # 4. Export Options
                    st.markdown("---")
                    st.subheader("📥 Export Summary")
                    col_csv, col_json, col_pdf = st.columns(3)
                    
                    # Prepare Export Data
                    export_dict = {
                        "email_id": email_meta["id"],
                        "sender": email_meta["sender"],
                        "subject": email_meta["subject"],
                        "date": email_meta["date"],
                        "priority": sum_meta["priority"],
                        "importance_score": sum_meta["importance_score"],
                        "category": sum_meta["category"],
                        "deadline": sum_meta["deadline"],
                        "sentiment": sum_meta["sentiment"],
                        "summary": sum_meta["summary"],
                        "detailed_summary": sum_meta["detailed_summary"],
                        "action_items": ", ".join(sum_meta["action_items"]),
                        "suggested_reply": sum_meta["suggested_reply"]
                    }
                    
                    # CSV Export
                    csv_df = pd.DataFrame([export_dict])
                    csv_data = csv_df.to_csv(index=False).encode('utf-8')
                    col_csv.download_button(
                        label="📄 Download CSV",
                        data=csv_data,
                        file_name=f"summary_{email_meta['id']}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                    
                    # JSON Export
                    json_data = json.dumps(export_dict, indent=4, ensure_ascii=False).encode('utf-8')
                    col_json.download_button(
                        label="💻 Download JSON",
                        data=json_data,
                        file_name=f"summary_{email_meta['id']}.json",
                        mime="application/json",
                        use_container_width=True
                    )
                    
                    # PDF Export
                    pdf_bytes = export_summary_to_pdf(email_meta, sum_meta)
                    col_pdf.download_button(
                        label="📕 Download PDF",
                        data=pdf_bytes,
                        file_name=f"summary_{email_meta['id']}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )

# ==========================================
# TAB 2: EMAIL ANALYTICS (Bonus Feature)
# ==========================================
with analytics_tab:
    if not st.session_state.emails:
        st.info("No email data loaded. Run Gmail fetch to view analytics.")
    else:
        st.subheader("📈 Inbox Insights")
        
        # Load data into pandas DataFrame
        records = []
        for e in st.session_state.emails:
            records.append({
                "sender": e["email"].get("sender", "Unknown"),
                "subject": e["email"].get("subject", ""),
                "date": e["email"].get("date", ""),
                "priority": e["summary"].get("priority", "Medium"),
                "importance_score": e["summary"].get("importance_score", 50),
                "category": e["summary"].get("category", "Personal"),
                "sentiment": e["summary"].get("sentiment", "Neutral")
            })
        df = pd.DataFrame(records)
        
        # Metrics row
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Emails Fetched", len(df))
        m2.metric("High Priority Count", len(df[df["priority"] == "High"]))
        m3.metric("Average Importance Score", f"{df['importance_score'].mean():.1f}/100")
        m4.metric("Unique Senders", df["sender"].nunique())
        
        st.markdown("---")
        
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.markdown("#### Category Distribution")
            cat_counts = df["category"].value_counts().reset_index()
            cat_counts.columns = ["Category", "Count"]
            st.bar_chart(data=cat_counts, x="Category", y="Count", color="#6366f1")
            
        with col_chart2:
            st.markdown("#### Priority Breakdown")
            pri_counts = df["priority"].value_counts().reset_index()
            pri_counts.columns = ["Priority", "Count"]
            st.bar_chart(data=pri_counts, x="Priority", y="Count", color="#f97316")
            
        st.markdown("---")
        
        col_chart3, col_chart4 = st.columns(2)
        
        with col_chart3:
            st.markdown("#### Sentiment Distribution")
            sent_counts = df["sentiment"].value_counts().reset_index()
            sent_counts.columns = ["Sentiment", "Count"]
            st.bar_chart(data=sent_counts, x="Sentiment", y="Count", color="#10b981")
            
        with col_chart4:
            st.markdown("#### Importance Scores Distribution")
            hist_df = df[["importance_score"]].copy()
            st.bar_chart(hist_df["importance_score"].value_counts().sort_index())

# ==========================================
# TAB 3: DAILY DIGEST (Bonus Feature)
# ==========================================
with digest_tab:
    if not st.session_state.emails:
        st.info("No email data loaded. Run Gmail fetch to enable the Daily Digest.")
    else:
        st.subheader("📝 Daily AI Digest")
        st.write("Generates a unified executive summary of all loaded emails.")
        
        if not st.session_state.daily_digest:
            st.info("Click the **Generate Daily Digest** button in the sidebar to generate.")
        else:
            # Display digest text in markdown
            st.markdown(st.session_state.daily_digest)
            
            st.markdown("---")
            # Export buttons for the digest
            col_d_txt, col_d_pdf = st.columns(2)
            
            col_d_txt.download_button(
                label="📥 Download Digest as Markdown",
                data=st.session_state.daily_digest.encode("utf-8"),
                file_name=f"daily_digest_{datetime.date.today().isoformat()}.md",
                mime="text/markdown",
                use_container_width=True
            )
            
            # Daily digest PDF generator
            try:
                pdf_digest = PDFReport()
                pdf_digest.alias_nb_pages()
                pdf_digest.add_page()
                pdf_digest.set_auto_page_break(auto=True, margin=20)
                pdf_digest.set_text_color(55, 65, 81)
                pdf_digest.set_font("helvetica", "B", 14)
                pdf_digest.cell(0, 10, f"DAILY DIGEST - {datetime.date.today().isoformat()}", ln=True, align="C")
                pdf_digest.ln(5)
                pdf_digest.set_font("helvetica", "", 10)
                
                # Replace non-printable characters for standard font PDF
                # Quick clean of markdown characters for standard FPDF rendering
                clean_digest = st.session_state.daily_digest.replace("📬", "").replace("⚠️", "").replace("📁", "").replace("📋", "").replace("🤖", "")
                pdf_digest.multi_cell(0, 6, clean_digest)
                
                col_d_pdf.download_button(
                    label="📕 Download Digest PDF",
                    data=bytes(pdf_digest.output()),
                    file_name=f"daily_digest_{datetime.date.today().isoformat()}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                logger.error(f"Failed to generate digest PDF: {e}")
