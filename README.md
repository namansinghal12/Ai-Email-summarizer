# AI Email Summarizer & Assistant 📬

A production-ready, clean, modular Python application that connects to your personal Gmail account, retrieves unread emails, cleanses and processes them with Google Gemini AI, and presents structured insights in a premium Streamlit dashboard.

## 🚀 Features

*   **Secure OAuth 2.0 Authentication**: Seamlessly authenticate your Gmail account with secure local token caching and token auto-refresh.
*   **Intelligent Text Cleaning**: Strips out HTML tags, CSS styling, tracking pixel beacons, quoted reply threads, and email signatures before forwarding to AI.
*   **Structured AI Analysis via Gemini**:
    *   **Summarization**: Brief one-sentence summaries alongside detailed analytical summaries.
    *   **Priority Classification**: Automatic "High", "Medium", or "Low" priority categorization.
    *   **Importance Score**: urgencies predicted on a scale of 0 to 100.
    *   **Category Classification**: Automatically maps to Work, College, Finance, Shopping, Travel, Promotions, Personal, or Spam.
    *   **Deadline Extraction**: Highlights action items and detects calendar deadlines.
    *   **Sentiment Analysis**: Identifies Positive, Neutral, or Negative sentiments.
    *   **Draft Reply Generator**: Automatically drafts a context-appropriate, professional email reply.
*   **Premium Streamlit Dashboard**:
    *   Responsive, modern interface with real-time global searching, category filters, and detailed email viewer tab panels.
    *   **Daily AI Digest**: Combines all retrieved emails into a single executive digest.
    *   **Voice Summaries**: Converts summaries to voiceovers directly in your browser using the HTML5 Web Speech API.
    *   **Export Formats**: Download individual summaries or daily digests as structured JSON, CSV, or styled PDF reports.
    *   **Smart Notifications**: Pop-up toast notifications warn you when High Priority emails are processed.
    *   **Gmail Label Syncing**: Automatically tags processed messages in Gmail with `AI-Summarized` and `AI-High-Priority`.

---

## 📁 Project Structure

```
AI_Email_Summarizer/
├── app.py                   # Streamlit dashboard UI and state controller
├── gmail_service.py         # Gmail API authorization and message endpoints
├── summarizer.py            # Google Gemini AI models and structured prompts
├── email_parser.py          # MIME decoding, html-strip, and signature cleaner
├── utils.py                 # Logging setups, PDF reports, and text-to-speech scripts
├── config.py                # Environment loaders, paths, and constants
├── requirements.txt         # Project library dependencies
├── README.md                # Project documentation and guide
├── .env.example             # Template for API keys
├── .gitignore               # Excludes secrets, tokens, and logs
├── credentials/             # Google Cloud OAuth credentials folder
│   ├── credentials.json     # (Downloaded from GCP Console - user provided)
│   └── token.json           # (Generated on first login)
├── data/                    # Local storage (stores summaries cache)
└── logs/                    # Event and error logs
```

---

## 🛠️ Installation & Setup

### 1. Prerequisites
Ensure you have **Python 3.12+** installed on your system.

### 2. Clone the Project & Install Dependencies
Navigate to the directory and install required Python packages:
```bash
pip install -r requirements.txt
```

### 3. Setup Google Cloud Console & Gmail API
To use the Gmail API, you need to create a project in Google Cloud:
1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
2.  Create a new project (e.g., `AI-Email-Summarizer`).
3.  Go to the **API Library** and search for **Gmail API**. Click **Enable**.
4.  Navigate to **OAuth consent screen**:
    *   Choose **User Type**: **External** (or Internal if you are on a Google Workspace domain).
    *   Fill out the app registration details.
    *   In the **Scopes** step, add `/auth/gmail.modify` to allow the app to read, mark as read, and label your emails.
    *   In the **Test Users** step, add the Gmail address you want to summarize. **Crucial**: If your app status is "Testing", only these users can log in!
5.  Go to **Credentials**:
    *   Click **Create Credentials** -> **OAuth client ID**.
    *   Select Application type: **Desktop App**.
    *   Give it a name (e.g., `Desktop Summarizer`).
    *   Click **Create**, and then download the JSON file.
6.  Rename the downloaded JSON file to `credentials.json` and place it inside the `credentials/` folder in the project root:
    ```
    credentials/credentials.json
    ```

### 4. Setup Gemini API Key
1.  Obtain an API key from [Google AI Studio](https://aistudio.google.com/).
2.  Copy `.env.example` to a new file named `.env`:
    ```bash
    cp .env.example .env
    ```
3.  Edit `.env` and fill in your Gemini API key:
    ```env
    GEMINI_API_KEY=AIzaSyYourKeyHere...
    ```

---

## 🏃 Running the Application

Launch the Streamlit web application:
```bash
streamlit run app.py
```

### OAuth Login Flow
1.  When you open the web application, check the sidebar. Under **Gmail Account**, it will display **Not Connected**.
2.  Click the **🔌 Connect Gmail Account** button.
3.  A browser window will open automatically, prompting you to log in with your Google account.
4.  If Google shows a "Google hasn't verified this app" warning page, click **Advanced** -> **Go to AI-Email-Summarizer (unsafe)** (this is standard for self-signed developer projects).
5.  Allow the requested permissions and click **Continue**.
6.  Once approved, you will see a success message in the browser. You can close the tab.
7.  The Streamlit app sidebar will reload and display **Connected to Gmail** (a permanent token is now cached at `credentials/token.json`).

### Summarizing Emails
1.  Select your **Email Filter** (e.g. `Unread`, `Today`, `Starred`) and **Max Emails** count in the sidebar.
2.  Click **🔄 Fetch & Analyze Emails**.
3.  A progress bar will track downloading, parsing, and Gemini AI processing.
4.  Once completed:
    *   The left column will list the processed emails with priority badges and category tags.
    *   Select an email to view its AI summary, detailed summaries, action items, sentiment indices, and drafted suggested reply in the tabs.
    *   Use the download buttons to save summaries as CSV, JSON, or PDF.
    *   Use the **Read Summary Aloud** button to read details out loud.
    *   Processed emails are labeled with `AI-Summarized` (and `AI-High-Priority` if applicable) in your Gmail account.

---

## 🛡️ Logging & Security
*   **Secrets protection**: Secrets, tokens (`token.json`), and downloaded GCP configurations (`credentials.json`) are ignored by Git in `.gitignore`.
*   **Local Caching**: Summarized emails are cached in `data/summaries_cache.json` to prevent unnecessary Gemini API calls when the app reloads.
*   **Logging**: Detailed activity (OAuth refresh, Gmail API calls, processing speeds, errors) is logged in `logs/app.log`.

---

## 🔮 Future Improvements
1.  **Direct Email Replies**: Enable a "Send Reply" button inside Streamlit to directly reply to the email using the generated draft via Gmail API.
2.  **Advanced Scheduling**: Set up cron jobs to run the summarizer every morning and email the Daily AI Digest directly to the user's phone.
3.  **Vector Store Integration**: Feed summarized emails into a vector store (e.g., ChromaDB) to perform semantic search queries (e.g., "Find all emails related to the contract negotiations in 2025").
