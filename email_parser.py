import re
import email
from email.header import decode_header
from bs4 import BeautifulSoup
from utils import logger

def decode_mime_header(header_value: str) -> str:
    """Decodes email headers that might be encoded in MIME format (e.g. UTF-8)."""
    if not header_value:
        return ""
    try:
        decoded_parts = decode_header(header_value)
        header_text = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                try:
                    header_text.append(part.decode(encoding or "utf-8", errors="replace"))
                except LookupError:
                    header_text.append(part.decode("utf-8", errors="replace"))
            else:
                header_text.append(str(part))
        return "".join(header_text)
    except Exception as e:
        logger.warning(f"Error decoding header '{header_value}': {e}")
        return str(header_value)

def clean_html(html_content: str) -> str:
    """Strips HTML, inline CSS, JS scripts, and tracking pixels using BeautifulSoup."""
    if not html_content:
        return ""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Remove styling and scripting
        for element in soup(["script", "style", "head", "meta", "title"]):
            element.decompose()
            
        # Detect and remove tracking pixels (typically 0px or 1px images)
        for img in soup.find_all("img"):
            width = img.get("width")
            height = img.get("height")
            src = img.get("src", "")
            # Check for standard tracking patterns or tiny dimensions
            if (width in ["0", "1"] or height in ["0", "1"]) or ("track" in src or "pixel" in src):
                img.decompose()
                
        # Extract text content
        text = soup.get_text(separator="\n")
        return text
    except Exception as e:
        logger.error(f"Error cleaning HTML: {e}")
        # Fallback to simple regex strip if BeautifulSoup fails
        text = re.sub(r'<[^>]+>', '', html_content)
        return text

def strip_quoted_replies(text: str) -> str:
    """Removes historical email reply chains (quoted text starting with > or reply headers)."""
    if not text:
        return ""
        
    lines = text.splitlines()
    cleaned_lines = []
    
    # Common headers indicating the start of a thread reply
    reply_header_patterns = [
        re.compile(r'^\s*On\s+.*\s+wrote:\s*$', re.IGNORECASE),
        re.compile(r'^\s*On\s+.*,\s+at\s+.*,\s+.*\s+wrote:.*$', re.IGNORECASE),
        re.compile(r'^\s*-----Original Message-----', re.IGNORECASE),
        re.compile(r'^\s*From:\s+.*$', re.IGNORECASE),
        re.compile(r'^\s*To:\s+.*$', re.IGNORECASE),
        re.compile(r'^\s*Sent:\s+.*$', re.IGNORECASE),
        re.compile(r'^\s*Date:\s+.*$', re.IGNORECASE),
        re.compile(r'^Subject:\s+.*$', re.IGNORECASE),
    ]
    
    for line in lines:
        stripped = line.strip()
        
        # Skip blockquote lines starting with '>'
        if stripped.startswith(">"):
            continue
            
        # Check if we hit a reply thread boundary
        is_boundary = False
        for pattern in reply_header_patterns:
            if pattern.match(line):
                is_boundary = True
                break
                
        if is_boundary:
            # We reached the beginning of the reply chain, stop parsing
            break
            
        cleaned_lines.append(line)
        
    return "\n".join(cleaned_lines)

def strip_signatures(text: str) -> str:
    """Detects and strips out email closures and signatures (e.g. 'Best regards, John')."""
    if not text:
        return ""
        
    # Standard signature separator '-- \n' or '--\n'
    if "-- \n" in text:
        text = text.split("-- \n", 1)[0]
    elif "--\n" in text:
        text = text.split("--\n", 1)[0]
        
    # Mobile signature pattern
    mobile_sig_pattern = re.compile(
        r'^\s*(Sent\s+from\s+my\s+(iPhone|iPad|Android|BlackBerry|Windows\s+Phone|mobile\s+device)|Get\s+Outlook\s+for\s+\w+).*$', 
        re.IGNORECASE
    )
    
    lines = text.splitlines()
    cleaned_lines = []
    
    closures = [
        "best regards", "kind regards", "sincerely", "thanks", "thank you", 
        "regards", "warm regards", "cheers", "yours truly", "best", "respectfully",
        "many thanks"
    ]
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Check for mobile signature
        if mobile_sig_pattern.match(stripped):
            break
            
        # Check for closures if they appear close to the end (max 4 remaining non-empty lines)
        stripped_lower = stripped.lower().rstrip(",. ")
        if stripped_lower in closures:
            remaining = [l for l in lines[i+1:] if l.strip()]
            if len(remaining) <= 4:
                # This is likely a signature block starting with a closure, stop adding
                break
                
        cleaned_lines.append(line)
        
    return "\n".join(cleaned_lines)

def normalize_whitespace(text: str) -> str:
    """Collapses multiple newlines and spaces, and trims margins."""
    if not text:
        return ""
    # Replace multiple spaces with a single space
    text = re.sub(r'[ \t]+', ' ', text)
    # Replace 3 or more consecutive newlines with 2 newlines (preserves paragraph breaks)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def clean_email_body(raw_body: str, is_html: bool = False) -> str:
    """Main pipeline function to clean the raw email body."""
    if not raw_body:
        return ""
        
    if is_html:
        cleaned_text = clean_html(raw_body)
    else:
        cleaned_text = raw_body
        
    # Process text content
    cleaned_text = strip_quoted_replies(cleaned_text)
    cleaned_text = strip_signatures(cleaned_text)
    cleaned_text = normalize_whitespace(cleaned_text)
    
    return cleaned_text

def parse_raw_email(msg_bytes: bytes) -> dict:
    """Parses raw email bytes into a structured dictionary of headers and cleaned body."""
    try:
        msg = email.message_from_bytes(msg_bytes)
        
        # Parse headers
        subject = decode_mime_header(msg.get("subject", "(No Subject)"))
        sender = decode_mime_header(msg.get("from", "Unknown"))
        receiver = decode_mime_header(msg.get("to", ""))
        date_str = msg.get("date", "")
        
        body_text = ""
        body_html = ""
        attachments_count = 0
        
        # Traverse parts
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                # Check for attachments
                if "attachment" in content_disposition:
                    attachments_count += 1
                    continue
                    
                # Extract text payloads
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        body_text += payload.decode(charset, errors="replace")
                elif content_type == "text/html" and "attachment" not in content_disposition:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        body_html += payload.decode(charset, errors="replace")
        else:
            content_type = msg.get_content_type()
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                decoded_payload = payload.decode(charset, errors="replace")
                if content_type == "text/html":
                    body_html = decoded_payload
                else:
                    body_text = decoded_payload
                    
        # Decide which body to clean
        if body_text.strip():
            cleaned_body = clean_email_body(body_text, is_html=False)
        elif body_html.strip():
            cleaned_body = clean_email_body(body_html, is_html=True)
        else:
            cleaned_body = ""
            
        return {
            "subject": subject,
            "sender": sender,
            "receiver": receiver,
            "date": date_str,
            "body": cleaned_body,
            "attachments_count": attachments_count
        }
    except Exception as e:
        logger.error(f"Error parsing email bytes: {e}", exc_info=True)
        return {
            "subject": "(Error Parsing Email)",
            "sender": "Unknown",
            "receiver": "",
            "date": "",
            "body": "",
            "attachments_count": 0
        }
