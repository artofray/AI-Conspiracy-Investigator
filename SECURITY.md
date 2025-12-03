# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability, please:

1. **DO NOT** open a public issue
2. Email security@shadow-project.org with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes

## Response Timeline

- **24 hours**: Initial acknowledgment
- **72 hours**: Assessment and severity determination
- **7 days**: Fix development for critical issues
- **30 days**: Public disclosure (coordinated)

## Security Best Practices

When using SHADOW:

### API Keys
- Never commit API keys to version control
- Use environment variables
- Rotate keys regularly

### Data Security
- Store processed data securely
- Be mindful of PII in documents
- Use encryption for sensitive data

### Network Security
- Run behind a firewall
- Use HTTPS in production
- Limit API access

## Known Limitations

- SHADOW processes potentially sensitive documents
- Social media data may contain PII
- AI classifications are not legal determinations

## Bug Bounty

We currently do not have a formal bug bounty program, but we deeply appreciate security researchers who responsibly disclose vulnerabilities.

## Contact

security@shadow-project.org
