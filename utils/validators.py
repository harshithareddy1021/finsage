import re

def validate_username(username):
    if not username or len(username.strip()) < 3:
        return False, "Username must be at least 3 characters."
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        return False, "Username can only contain letters, numbers, and underscores."
    if len(username) > 30:
        return False, "Username must be under 30 characters."
    return True, ""

def validate_email(email):
    if not email:
        return False, "Email is required."
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        return False, "Please enter a valid email address."
    return True, ""

def validate_password(password):
    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters."
    if not re.search(r"[A-Za-z]", password):
        return False, "Password must contain at least one letter."
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one number."
    return True, ""

def validate_registration(username, email, password, confirm_password):
    errors = []
    ok, msg = validate_username(username)
    if not ok:
        errors.append(msg)
    ok, msg = validate_email(email)
    if not ok:
        errors.append(msg)
    ok, msg = validate_password(password)
    if not ok:
        errors.append(msg)
    if password != confirm_password:
        errors.append("Passwords do not match.")
    return len(errors) == 0, errors