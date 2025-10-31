# Create: test_email_processing.py
from backend.gmail_service import parse_email_body
from backend.crm_service import upload_to_affinity

# Mock email content
test_email = """
Hi team,

Nova Credit upload to affinity

Notes: "These are promising AI companies we should track closely."

Best regards
"""

try:
    companies, notes = parse_email_body(test_email)
    print(f"Parsed companies: {companies}")
    print(f"Parsed notes: {notes}")
    
    # Test upload
    result = upload_to_affinity(companies, notes, [])
    print(f"Upload result: {result}")
except Exception as e:
    print(f"Error: {e}")