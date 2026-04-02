This extractor allows you to automatically retrieve email contents and/or its attachments from Office 365.
It supports two connection methods and uses oAuth 2.0 for authentication.

### IMAP

Emails stay intact in your original inbox and can be queried using a standardized [IMAP query syntax](https://help.keboola.com/components/extractors/communication/email-imap/query-syntax).
Supports standard IMAP search keywords: FROM, SUBJECT, SINCE, BEFORE, UNSEEN, etc.

### Graph API

Uses Microsoft Graph API directly. Supports two filtering mechanisms:

**Graph API Filter** — OData `$filter` for exact matches. Can be combined with the Period from date field.

| Need | Example |
|---|---|
| Exact sender | `from/emailAddress/address eq 'someone@example.com'` |
| Exact subject | `subject eq 'Exact Subject Line'` |
| Has attachments | `hasAttachments eq true` |
| Combined | `from/emailAddress/address eq 'x@y.com' and subject eq 'text'` |

Note: `contains()` on subject/body is not supported by the messages endpoint and returns HTTP 400.

**Graph API Search (KQL)** — keyword and partial matching. Cannot be combined with Graph API Filter or Period from date — this is a [Microsoft Graph API limitation](https://learn.microsoft.com/en-us/graph/known-issues#some-limitations-apply-to-query-parameters). Returns up to 1,000 results.

| Need | Example |
|---|---|
| Subject keyword | `subject:weekly` |
| Subject exact phrase | `subject:"exact multi-word phrase"` |
| Sender (substring) | `from:someone@example.com` or `from:MSSecurity` |
| Date exact | `received:2026-03-17` |
| Date range | `received:2026-01-01..2026-01-31` |
| All combined | `from:sender subject:keyword received:2026-01-01..2026-03-18` |

Note: relative date keywords (`received:this week`, `received:today`) are not supported on the messages endpoint.
