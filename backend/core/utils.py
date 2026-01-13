import time
import re
import json

def get_time():
    return time.strftime("%Y%m%d-%H%M%S")

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name).replace(" ", "_")

def clean_string(s: str) -> str:
    """Remove control characters and normalize whitespace"""
    if not s: return ""
    s = str(s).replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    return "".join(c for c in s if c.isprintable() or ord(c) > 127).strip()

def create_sse_event(data: dict):
    return {"event": "message", "data": json.dumps(data)}

def robust_parse_json(text: str):
    """
    Attempt to parse JSON from a string that might contain markdown,
    extra text, or slight formatting errors.
    """
    if not text:
        return None

    # 1. Simple Load
    try:
        return json.loads(text)
    except:
        pass

    # 2. Markdown Cleanup
    cleaned = text
    if "```" in cleaned:
        # Find json block
        match = re.search(r'```(?:json)?\s*(.*?)\s*```', cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1)
        else:
            # Maybe it starts with ``` but no closing?
            cleaned = cleaned.replace("```json", "").replace("```", "")
    
    try:
        return json.loads(cleaned)
    except:
        pass

    # 3. Bracket Extraction (Object or Array)
    try:
        # Find first { or [
        start_idx = -1
        end_idx = -1
        first_curly = cleaned.find("{")
        first_square = cleaned.find("[")
        
        if first_curly != -1 and (first_square == -1 or first_curly < first_square):
            start_idx = first_curly
            # Find matching closing (naive: last })
            end_idx = cleaned.rfind("}")
        elif first_square != -1:
            start_idx = first_square
            end_idx = cleaned.rfind("]")
            
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            candidate = cleaned[start_idx:end_idx+1]
            return json.loads(candidate)
    except:
        pass

    # 4. Fallback: try to fix common trailing comma
    try:
        fixed = re.sub(r',\s*([}\]])', r'\1', cleaned)
        return json.loads(fixed)
    except:
        pass

    return None
