# ResumePipeline

Automatic rejection email is disabled unless `EMAIL_AUTO_REJECT_SCORE_THRESHOLD` is set to a number from 0 to 100. When enabled, a rejection is sent only when at least one role was scored and every role's overall `match.<role_id>.score` is strictly below the threshold.

Configure SMTP in `ResumePipeline/.env`:

```dotenv
EMAIL_AUTO_REJECT_SCORE_THRESHOLD=40
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=465
EMAIL_SMTP_TLS=true
EMAIL_SMTP_USER=...
EMAIL_SMTP_PASSWORD=...
EMAIL_SENDER_NAME="Hiring Team"
EMAIL_ORG_NAME="Our Company"
EMAIL_DRY_RUN=false
```

`EMAIL_SMTP_TLS=true` uses implicit TLS; `false` uses STARTTLS. `EMAIL_DRY_RUN=true` logs rejection attempts without connecting to SMTP. The first email address extracted from the resume is used. Delivery state is stored with the resume: failed sends remain pending and are retried when the same inbound message is processed again; successful sends are not repeated.
