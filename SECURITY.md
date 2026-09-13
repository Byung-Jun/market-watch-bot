# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please do not disclose sensitive information in a public GitHub issue.

Instead, please contact the repository maintainer privately through GitHub.

When reporting a vulnerability, please include:

* A description of the issue
* Steps to reproduce the issue
* Potential impact
* Any relevant logs or screenshots, after removing sensitive information

## Secrets

API keys, Telegram bot tokens, passwords, and other credentials must never be committed to the repository.

The project expects credentials to be provided through environment variables or GitHub Actions Secrets.

If you believe a credential has been accidentally exposed, revoke or rotate it immediately.
