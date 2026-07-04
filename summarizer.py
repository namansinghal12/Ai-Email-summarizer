import json
import time
from google import genai
from google.genai import types
from config import DEFAULT_GEMINI_MODEL, GEMINI_API_KEY
from utils import logger

# Default structure for graceful error fallback
DEFAULT_ANALYSIS = {
    "summary": "Failed to summarize email content.",
    "detailed_summary": "An error occurred during Gemini API processing.",
    "priority": "Medium",
    "importance_score": 50,
    "category": "Personal",
    "deadline": None,
    "action_items": [],
    "sentiment": "Neutral",
    "suggested_reply": "Thank you for your email. I will review this and get back to you shortly."
}

GEMINI_CLIENT = None


def configure_gemini(api_key: str = None) -> bool:
    """Configures the Google GenAI client with the provided API key."""
    global GEMINI_CLIENT

    key_to_use = api_key or GEMINI_API_KEY
    if not key_to_use:
        logger.warning("No Gemini API key provided. Summarizer will not function.")
        return False
    try:
        GEMINI_CLIENT = genai.Client(api_key=key_to_use)
        return True
    except Exception as e:
        logger.error(f"Error configuring Gemini SDK: {e}", exc_info=True)
        return False

def call_gemini_with_retry(prompt, generation_config=None, max_retries=3):
    """Executes a Gemini API call with exponential backoff on failure."""
    if not GEMINI_CLIENT:
        raise RuntimeError("Gemini client is not configured")

    wait_time = 2.0
    for attempt in range(max_retries):
        try:
            start_time = time.time()
            response = GEMINI_CLIENT.models.generate_content(
                model=DEFAULT_GEMINI_MODEL,
                contents=prompt,
                config=generation_config,
            )
            processing_time = time.time() - start_time
            logger.info(f"Gemini API request succeeded in {processing_time:.2f}s (Attempt {attempt + 1})")
            return response
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Gemini API call failed after {max_retries} attempts: {e}")
                raise e
            logger.warning(f"Gemini API call failed: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
            wait_time *= 2.0

def summarize_email(email_text: str, subject: str, sender: str, api_key: str = None) -> dict:
    """Sends cleaned email to Gemini for structured JSON analysis & response generation."""
    if not configure_gemini(api_key):
        return DEFAULT_ANALYSIS
        
    # Trim content to avoid exceeding context limits for very long emails (though gemini limits are huge)
    truncated_text = email_text[:20000] if email_text else "(Empty Email Body)"
    
    prompt = f"""You are an elite email administrator and executive assistant.
Analyze the following email and generate a structured JSON analysis.

Email Details:
Sender: {sender}
Subject: {subject}
Body:
{truncated_text}

You must return a JSON object with these EXACT keys:
1. "summary": A one-sentence, high-level summary of the core message (max 20 words).
2. "detailed_summary": A detailed, concise paragraph explaining the context, background, and major details.
3. "priority": Categorize as "High", "Medium", or "Low".
4. "importance_score": An integer score from 0 to 100 reflecting the email's urgency and importance.
   - High Priority (75-100): Needs immediate action, relates to contracts, job offers, finances, deadlines, or direct queries from management/clients.
   - Medium Priority (35-74): General work discussions, updates, actions that can wait a day, or important notifications.
   - Low Priority (0-34): Newsletters, promotions, automatic alerts, spam, social updates.
5. "category": Categorize into one of: "Work", "College", "Finance", "Shopping", "Travel", "Promotions", "Personal", "Spam".
6. "deadline": Extract any specific due date or deadline mentioned (e.g. YYYY-MM-DD or 'Monday at 10 AM'). If no deadline is mentioned, return null.
7. "action_items": A list of clear, actionable tasks for the recipient. If none, return an empty list [].
8. "sentiment": One of "Positive", "Neutral", "Negative".
9. "suggested_reply": A professional, polite, and contextual response draft that the recipient can copy-paste to reply to this email. Keep it concise.

Return ONLY the JSON. Do not wrap the JSON output in markdown formatting (like ```json ... ```). Output must start with '{{' and end with '}}'.
"""
    
    try:
        response = call_gemini_with_retry(
            prompt=prompt,
            generation_config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        
        # Load and validate JSON response
        result_json = json.loads(response.text.strip())
        
        # Ensure all required keys exist by merging with DEFAULT_ANALYSIS
        validated_analysis = {}
        for key, val in DEFAULT_ANALYSIS.items():
            validated_analysis[key] = result_json.get(key, val)
            
        return validated_analysis
        
    except json.JSONDecodeError as jde:
        logger.error(f"Failed to parse JSON response from Gemini: {jde}. Raw response: {response.text}")
        return DEFAULT_ANALYSIS
    except Exception as e:
        logger.error(f"Error in summarize_email: {e}", exc_info=True)
        return DEFAULT_ANALYSIS

def generate_daily_digest(emails_list: list, api_key: str = None) -> str:
    """Takes a list of summarized emails and generates a single structured Daily AI Digest."""
    if not emails_list:
        return "No unread emails to summarize for today's digest."
        
    if not configure_gemini(api_key):
        return "Gemini API key is required to generate the Daily Digest."
        
    # Compile unread emails summary data
    compiled_emails = []
    for idx, item in enumerate(emails_list):
        email_meta = item.get("email", {})
        summary_meta = item.get("summary", {})
        
        compiled_emails.append(
            f"Email #{idx+1}:\n"
            f"- From: {email_meta.get('sender')}\n"
            f"- Subject: {email_meta.get('subject')}\n"
            f"- Priority: {summary_meta.get('priority')} (Score: {summary_meta.get('importance_score')}/100)\n"
            f"- Category: {summary_meta.get('category')}\n"
            f"- Brief Summary: {summary_meta.get('summary')}\n"
            f"- Actions: {', '.join(summary_meta.get('action_items', [])) or 'None'}\n"
        )
        
    emails_text = "\n".join(compiled_emails)
    
    prompt = f"""You are a professional administrative assistant.
Review the following list of summarized emails received today and compile a single, beautiful "Daily AI Digest".

Emails List:
{emails_text}

Format the output strictly as elegant Markdown with the following sections:
1. 📬 Executive Summary: A short 2-3 sentence overview of the day's inbox activity, highlights, and general volume.
2. ⚠️ High Priority Alerts: Bullet point alerts for any High Priority emails or key upcoming deadlines.
3. 📁 Categorized Breakdown: A summary grouping what's happening under Work, Finance, Promotions, etc.
4. 📋 Summary Table: A clean markdown table mapping [Sender] | [Subject] | [Priority] | [Key Action Item].

Make it look premium, structured, and easy to read at a glance.
"""
    
    try:
        response = call_gemini_with_retry(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Error generating Daily Digest: {e}", exc_info=True)
        return f"Failed to generate Daily Digest. Error: {e}"
