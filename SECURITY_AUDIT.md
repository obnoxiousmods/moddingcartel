# Security Audit Report - moddingcartel
**Date:** 2026-02-13  
**Audited By:** GitHub Copilot Security Agent

## Executive Summary

Overall Security Posture: **MODERATE** with several critical and high-severity issues identified requiring immediate attention.

**Critical Issues: 2** | **High Issues: 3** | **Medium Issues: 3** | **Low Issues: 2**

---

## 1. AQL Query Injection Analysis ✅ GOOD

### Findings
All primary AQL queries properly use `bind_vars` for parameter binding:
- ✅ `database.py` lines 244-1038: All queries use parameterized bind_vars
- ✅ `admin.py` line 1067: Query uses parameterized bind_vars
- ✅ **NO SQL/AQL INJECTION VULNERABILITIES FOUND**

**Conclusion:** The application correctly uses ArangoDB's parameterized query system throughout. All user inputs are properly sanitized through bind variables.

---

## 2. Path Traversal Vulnerabilities ⚠️ CRITICAL

### Issue #1: Directory Scanning Vulnerabilities (HIGH)
**File:** `app/routes/admin.py` lines 510-582  
**Severity:** HIGH

**Problems:**
1. No path validation - could contain `..` to escape directory
2. Follows symbolic links to arbitrary locations
3. Weak max depth check doesn't prevent escaping base directory

**Recommendation:** Add path normalization, symlink detection, and boundary checking

---

### Issue #2: File Upload Path Traversal (CRITICAL)
**File:** `app/routes/uploader.py` lines 280-306  
**Severity:** CRITICAL

**Problem:** Filename from client (`file.filename`) used directly with `os.path.join()` without sanitization.

**Attack Vector:**
```
POST /uploader/upload
filename: "../../config/secrets.nsp"
Result: File written outside upload directory!
```

**Recommendation:** Sanitize filenames, remove path separators, validate final path

---

### Issue #3: Arbitrary File Download (CRITICAL)
**File:** `app/routes/api.py` lines 95-110  
**Severity:** CRITICAL

**Problem:** File path from database used directly without validation that it's within allowed directories.

**Attack Vector:** If database entry contains `/etc/passwd`, user can download it via API

**Recommendation:** Validate all file paths against allowed directory whitelist

---

## 3. Input Validation ⚠️ MEDIUM

### Issue #4: Weak Username Validation
**File:** `app/routes/auth.py` lines 153-157  
**Severity:** MEDIUM

**Problems:**
- No maximum length check (could cause storage issues)
- No character whitelist (allows unicode, special chars)

**Recommendation:** Add regex validation `^[a-zA-Z0-9_-]{3,32}$`

---

### Issue #5: File Extension Validation
**File:** `app/routes/uploader.py` lines 285-287  
**Severity:** MEDIUM

**Problem:** Uses simple string split vulnerable to double extension attacks

**Recommendation:** Use `os.path.splitext()` for correct extension detection

---

## 4. Authentication & Authorization ✅ MOSTLY GOOD

### Good Practices Observed:
- ✅ Argon2 password hashing (strong)
- ✅ Session management with Starlette middleware
- ✅ Role-based access control enforced
- ✅ API key authentication with hashing
- ✅ Active status checks for API keys

### Issue #6: Session-Only Authorization
**Severity:** MEDIUM

**Problem:** Admin checks rely solely on session variables without database verification for critical operations

**Recommendation:** Add database verification for sensitive admin operations

---

## 5. Sensitive Data Exposure ✅ GOOD

### Good Practices:
- ✅ Password hashes removed before template rendering
- ✅ API keys hashed before storage
- ✅ Comprehensive audit logging

### Issue #7: Verbose Error Messages (LOW)
**File:** `app/routes/api.py` line 114  
**Severity:** LOW

**Problem:** Exception details returned to client can reveal system internals

**Recommendation:** Use generic error messages, log details server-side only

---

## 6. Configuration Security

### Issue #8: Default Secret Key (LOW)
**File:** `app/config.py` line 25  
**Severity:** LOW

**Problem:** Default secret key is hardcoded and weak

**Recommendation:** Use environment variable or generate random key on first run

---

## Priority Action Items

### IMMEDIATE (Critical - Fix Today)
1. ✅ **Add Cloudflare IP header logging** - COMPLETED
2. 🔧 Add file upload path sanitization
3. 🔧 Add file download path validation

### URGENT (High - Fix This Week)
4. 🔧 Add directory scanning path validation
5. 🔧 Add input validation regexes
6. 🔧 Validate database file paths

### IMPORTANT (Medium - Fix This Sprint)
7. 🔧 Add database authorization verification
8. 🔧 Change default secret key handling
9. 🔧 Sanitize error messages

---

## Summary of Completed Security Improvements

### ✅ IP Address Logging Enhancement
**Completed:** 2026-02-13

**Changes:**
- Created `app/utils/ip_utils.py` with comprehensive IP extraction functions
- Updated all 10+ logging locations to capture both real IP and connection IP
- Added Cloudflare header support (CF-Connecting-IP, X-Forwarded-For)
- Enhanced log format to show "1.2.3.4 (via 5.6.7.8)" when behind proxy
- All activity logs, audit logs, and API usage logs now store:
  - `ip_address`: Real client IP (from CF headers if available)
  - `client_ip`: Direct connection IP
  - `forwarded_ip`: Proxy/CF IP when different from client

**Impact:** Enhanced security auditing and intrusion detection capabilities

---

## Conclusion

The application has a solid security foundation with proper password hashing, parameterized queries, and comprehensive logging. However, critical path traversal vulnerabilities in file operations must be addressed immediately to prevent unauthorized file access.

The completed Cloudflare IP logging enhancement significantly improves security auditing capabilities. Remaining fixes should be prioritized based on the severity ratings above.
