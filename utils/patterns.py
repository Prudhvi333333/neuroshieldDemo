# patterns.py
import re

# --- Category Keywords ---
KEYWORD_PATTERNS = {
    # ... (This section remains the same)
    "FINANCIAL": [
        "invoice", "payment", "due date", "subtotal", "tax", "total", "receipt",
        "balance", "credit", "debit", "bank statement"
    ],
    "LEGAL": [
        "agreement", "contract", "confidential", "terms and conditions",
        "liability", "party", "parties", "witness", "notary", "jurisdiction"
    ],
    "MEDICAL": [
        "patient", "diagnosis", "symptoms", "prescription", "medical record",
        "doctor", "clinic", "pharmacy", "treatment"
    ]
}

# --- Common Data Formats (Regex) ---
REGEX_PATTERNS = {
    # ... (This section remains the same)
    "Email Address": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    "Phone Number (U.S.)": r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
    "Date (YYYY-MM-DD or MM/DD/YYYY)": r'(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})',
    "Invoice Number": r'(?i)\b(invoice\s*#?|inv\s*#?|receipt\s*#?)\s*([A-Z0-9-]+)\b'
}


# ==============================================================================
# --- Sensitive Data / Secrets Patterns (Enhanced) ---
# WARNING: These are indicative and can have false positives.
# ==============================================================================
SECRET_PATTERNS = {
    # --- High-Confidence Patterns (Specific Prefixes/Formats) ---
    ##############################################################

    # Cloud Provider API Keys
    "Google API Key": r'AIza[0-9A-Za-z\-_]{35}',
    "AWS Access Key ID": r'(A3T[A-Z0-9]|AKIA|AGPA|AROA|ASCA|ASIA)[A-Z0-9]{16}',
    "Microsoft Azure Client Secret": r'[a-zA-Z0-9\.\-_~]{30,}', # Generic pattern, might be noisy

    # Service Provider Tokens
    "GitHub Token": r'ghp_[a-zA-Z0-9]{36}', # Personal Access Token
    "Stripe API Key": r'(sk|pk)_(test|live)_[0-9a-zA-Z]{24}',
    "Slack Token": r'xox[p|b|a|o|s|r]-[0-9]{12}-[0-9]{12}-[0-9]{12}-[a-z0-9]{32}',
    "Twilio API Key": r'SK[0-9a-fA-F]{32}',

    # Cryptographic Keys & Formats
    "Private Key Block": r'-----BEGIN ((RSA|OPENSSH|EC|PGP) )?PRIVATE KEY-----',
    "JWT (JSON Web Token)": r'ey[A-Za-z0-9-_=]+\.ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]+',

    # --- Keyword-Context Patterns (Generic High-Entropy String Near a Keyword) ---
    #############################################################################
    # This is a powerful catch-all. It looks for common secret-related keywords
    # followed by an assignment operator and then a string that looks like a secret.
    # It will find things like:
    #   password = "..."
    #   API_KEY: '...'
    #   "secret": "..."
    #
    # We will use this one pattern and report the specific keyword found.
    "Generic Secret (Keyword-Based)": r"""
        (?i)                                  # Case-insensitive mode
        (                                     # Start of capturing group for the keyword
            password|passwd|pwd|              # Password variations
            secret|token|auth|bearer|         # Token variations
            api_key|apikey|access_key|secret_key| # API Key variations
            client_id|client_secret           # OAuth variations
        )
        \s*                                   # Optional whitespace
        [=:]                                  # Assignment operator (equals or colon)
        \s*                                   # Optional whitespace
        ["']?                                 # Optional quote
        (                                     # Start of capturing group for the secret value
            [A-Za-z0-9\-_.~+/=]{16,64}         # A plausible secret: 16-64 chars from a specific set
        )
        ["']?                                 # Optional closing quote
    """,
}