import logging
from logging.handlers import RotatingFileHandler
import html
from fpdf import FPDF
from config import LOG_FILE

def setup_logger() -> logging.Logger:
    """Sets up a rotating logger that logs events to both console and log file."""
    logger = logging.getLogger("AI_Email_Summarizer")
    if logger.handlers:
        return logger  # Logger is already set up

    logger.setLevel(logging.INFO)

    # Log formatter
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File Handler (5 MB max size, keeps 5 backup files)
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

logger = setup_logger()

class PDFReport(FPDF):
    """Custom FPDF class to design a premium styled summary PDF report."""
    def header(self):
        # Draw header banner
        self.set_fill_color(30, 41, 59) # Slate Dark Blue
        self.rect(0, 0, 210, 30, 'F')
        
        self.set_text_color(255, 255, 255)
        self.set_font("helvetica", "B", 16)
        self.cell(0, 10, "AI EMAIL SUMMARIZER REPORT", ln=True, align="C")
        
        self.set_font("helvetica", "I", 9)
        self.cell(0, 5, "Powered by Gemini AI & Streamlit", ln=True, align="C")
        self.ln(15)

    def footer(self):
        self.set_y(-15)
        self.set_text_color(128, 128, 128)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

def export_summary_to_pdf(email_data: dict, summary_data: dict) -> bytes:
    """Generates a styled PDF from the email details and Gemini summarization."""
    try:
        pdf = PDFReport()
        pdf.alias_nb_pages()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=20)
        
        # Colors definition
        primary_color = (30, 41, 59)   # Slate Blue
        text_color = (55, 65, 81)       # Charcoal
        accent_color = (79, 70, 229)    # Indigo
        
        # Email Details Section
        pdf.set_text_color(*accent_color)
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(0, 8, "EMAIL DETAILS", ln=True)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)
        
        # Meta info
        pdf.set_text_color(*text_color)
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(30, 6, "From:")
        pdf.set_font("helvetica", "", 10)
        pdf.cell(0, 6, email_data.get("sender", "Unknown"), ln=True)
        
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(30, 6, "Subject:")
        pdf.set_font("helvetica", "", 10)
        pdf.cell(0, 6, email_data.get("subject", "(No Subject)"), ln=True)
        
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(30, 6, "Date:")
        pdf.set_font("helvetica", "", 10)
        pdf.cell(0, 6, str(email_data.get("date", "")), ln=True)
        
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(30, 6, "Category:")
        pdf.set_font("helvetica", "", 10)
        pdf.cell(0, 6, f"{summary_data.get('category', 'N/A')} (Importance: {summary_data.get('importance_score', 'N/A')}/100)", ln=True)
        
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(30, 6, "Priority:")
        pdf.set_font("helvetica", "", 10)
        pdf.cell(0, 6, summary_data.get("priority", "N/A"), ln=True)
        
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(30, 6, "Deadline:")
        pdf.set_font("helvetica", "", 10)
        pdf.cell(0, 6, summary_data.get("deadline", "None") or "None", ln=True)
        
        pdf.ln(6)
        
        # One Sentence Summary Section
        pdf.set_text_color(*accent_color)
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(0, 8, "SUMMARY", ln=True)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)
        
        pdf.set_text_color(*text_color)
        pdf.set_font("helvetica", "I", 10)
        pdf.multi_cell(0, 6, f"\"{summary_data.get('summary', '')}\"")
        pdf.ln(4)
        
        # Detailed Summary
        pdf.set_text_color(*text_color)
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(0, 6, "Detailed Analysis:", ln=True)
        pdf.set_font("helvetica", "", 10)
        pdf.multi_cell(0, 6, summary_data.get("detailed_summary", ""))
        pdf.ln(6)
        
        # Action Items Section
        action_items = summary_data.get("action_items", [])
        if action_items:
            pdf.set_text_color(*accent_color)
            pdf.set_font("helvetica", "B", 12)
            pdf.cell(0, 8, "ACTION ITEMS", ln=True)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(3)
            
            pdf.set_text_color(*text_color)
            pdf.set_font("helvetica", "", 10)
            for item in action_items:
                pdf.cell(10, 6, chr(149), align="C") # bullet character
                pdf.multi_cell(0, 6, item)
            pdf.ln(6)
            
        # Suggested Reply Section
        reply = summary_data.get("suggested_reply", "")
        if reply:
            pdf.set_text_color(*accent_color)
            pdf.set_font("helvetica", "B", 12)
            pdf.cell(0, 8, "SUGGESTED REPLY DRAFT", ln=True)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(3)
            
            pdf.set_fill_color(243, 244, 246) # Light grey box
            pdf.set_text_color(*text_color)
            pdf.set_font("courier", "", 9)
            
            # Use multi_cell with background fill
            pdf.multi_cell(0, 5, reply, fill=True)
            pdf.ln(4)
            
        # Output as bytes
        return bytes(pdf.output())
    except Exception as e:
        logger.error(f"Failed to generate PDF summary report: {e}", exc_info=True)
        return b""

def get_tts_html(text: str) -> str:
    """Returns self-contained HTML/JS button to read text using Web Speech API."""
    escaped_text = html.escape(text.replace('"', '\\"').replace('\n', ' '))
    return f"""
    <div style="margin-top: 10px; margin-bottom: 10px;">
        <button id="tts-btn" onclick="toggleSpeech()" style="
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-family: sans-serif;
            font-weight: bold;
            font-size: 14px;
            box-shadow: 0 4px 6px rgba(50,50,93,0.11), 0 1px 3px rgba(0,0,0,0.08);
            transition: all 0.15s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        ">
            <span>🔊 Read Summary Aloud</span>
        </button>
    </div>
    <script>
        var speech = null;
        function toggleSpeech() {{
            if (window.speechSynthesis.speaking) {{
                window.speechSynthesis.cancel();
                document.getElementById('tts-btn').innerHTML = '<span>🔊 Read Summary Aloud</span>';
            }} else {{
                speech = new SpeechSynthesisUtterance("{escaped_text}");
                speech.onend = function() {{
                    document.getElementById('tts-btn').innerHTML = '<span>🔊 Read Summary Aloud</span>';
                }};
                window.speechSynthesis.speak(speech);
                document.getElementById('tts-btn').innerHTML = '<span>⏹️ Stop Reading</span>';
            }}
        }}
    </script>
    """
