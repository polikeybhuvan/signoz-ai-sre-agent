# Security Policy

## Project Status

AI SRE Agent is a prototype built for learning, experimentation, and demonstration. It is not intended for production use without additional security review and hardening.

## Supported Versions

This project does not currently maintain formal versioned releases.

| Version | Support |
|---|---|
| Latest code on `main` | Best-effort security fixes |
| Older commits and forks | Not guaranteed |

## Reporting a Vulnerability

Please do not report security vulnerabilities through public GitHub issues.

If private vulnerability reporting is enabled for this repository, please use GitHub's private reporting feature to contact the maintainer.

If private reporting is unavailable, contact the repository maintainer privately through their GitHub profile:

https://github.com/polikeybhuvan

When reporting a vulnerability, include:

- A description of the potential security issue.
- The affected file, component, or commit, if known.
- Steps to reproduce the issue.
- The potential impact and any relevant technical details.

Please do not include live API keys, passwords, access tokens, personal information, or other sensitive data in your report.

## Response and Disclosure

Reports will be reviewed on a best-effort basis. A response or fix timeline cannot be guaranteed.

Please allow the maintainer an opportunity to investigate and address a confirmed vulnerability before publicly disclosing technical details.

## Security Recommendations

Users running this project should:

- Store API keys in environment variables or a local `.env` file.
- Never commit credentials or other secrets to GitHub.
- Rotate credentials immediately if they are exposed.
- Keep dependencies updated and review changes before deploying.
- Validate AI-generated diagnoses before acting on them.
- Avoid exposing observability endpoints or sensitive telemetry to unauthorized users.
