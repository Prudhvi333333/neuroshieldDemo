# Software Security Best Practices

## Secure Coding Principles

### Input Validation
All user input must be validated and sanitized:
- Whitelist validation over blacklist approaches
- Length and format restrictions
- Encoding and escaping special characters
- Server-side validation is mandatory

### Authentication and Authorization
Proper access control implementation:
- Strong password policies and hashing (bcrypt, Argon2)
- Session management with secure tokens
- Role-based access control (RBAC)
- Principle of least privilege

## Common Vulnerabilities

### Cross-Site Scripting (XSS)
XSS allows attackers to inject malicious scripts:
- **Reflected XSS** - Script reflected from user input
- **Stored XSS** - Script stored in database
- **DOM-based XSS** - Client-side script manipulation
- Prevention: Content Security Policy, output encoding

### Cross-Site Request Forgery (CSRF)
CSRF tricks users into performing unwanted actions:
- Anti-CSRF tokens in forms
- SameSite cookie attributes
- Referer header validation
- Double-submit cookie pattern

## API Security

### REST API Protection
Securing REST APIs requires:
- OAuth 2.0 or JWT for authentication
- Rate limiting and throttling
- Input validation and output filtering
- HTTPS encryption for all communications

### GraphQL Security
GraphQL-specific security considerations:
- Query depth limiting
- Query complexity analysis
- Disable introspection in production
- Field-level authorization

## Dependency Management

### Third-Party Libraries
Managing external dependencies:
- Regular security updates and patches
- Vulnerability scanning tools
- Software composition analysis (SCA)
- License compliance monitoring

### Supply Chain Security
Protecting the software supply chain:
- Code signing and verification
- Secure build pipelines
- Dependency pinning and lock files
- Container image scanning
