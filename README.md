# Email Content Extractor

This is a repository for both kds-team.ex-email-content and kds-team.ex-ms-outlook-email-content.
kds-team.ex-ms-outlook-email-content exists to support Office 365 version of MS Outlook.

This component allows you to extract email body and other metadata using IMAP protocol.

**Table of contents:**

[TOC]

# Functionality notes

NOTE: The default authority https://login.microsoftonline.com/common can be overwritten by authority parameter in image_parameters.

# Prerequisites


Have IMAP service enabled on your Email account. Please refer to your email provider for more information.

Note that for GMAIL you will need to use [App Password](https://support.google.com/accounts/answer/185833?hl=en)
or alternatively (not recommended) enable access for the ["less secure" apps](https://support.google.com/accounts/answer/6010255?hl=en). 

For MS Outlook in Office 365 suite, you will need to grant permission using oAuth.


Note that the app fetches emails from the root `INBOX` folder. If you use labels and filters in Gmail for instance, that move the messages to a different folder, 
please set the `imap_folder` configuration parameter.
 

# KBC Features


| **Feature**                | **Note**                                                                                                                   |
|----------------------------|----------------------------------------------------------------------------------------------------------------------------|
| Generic UI form            | Dynamic UI form                                                                                                            |             
| Row based configuration    | Allows execution of each row in parallel.                                                                                  |             
| Incremental loading        | Allows fetching data in new increments.                                                                                    |
| IMAP query syntax          | Filter emails using standard [IMAP query](docs/imap-search.md)                                                             |
| Download email contents    | Full body of email downloaded into the Storage column                                                                      |
| Download email attachments | All attachments downloaded by default into a file storage.                                                                 |
| Filter email attachments   | Download only attachments matching specified regex expression                                                              |
| Processors support         | Use processor to modify the outputs before saving to storage, e.g. process attachments to be stored in the Tabular Storage |


# Configuration

## Supported parameters:

 - `connection_method` -- `imap` (default) or `graph_api` (MS Outlook variant only)
 - `#password` -- IMAP password; not needed for `graph_api` connection method
 - `user_name` -- login / email address
 - `host` -- IMAP host (IMAP only)
 - `query` -- IMAP search query. E.g. `(FROM "email" SUBJECT "the subject" UNSEEN)`. More information [here](docs/imap-search.md). IMAP only.
 - `graph_filter` -- OData `$filter` expression for Graph API exact matching. Can be combined with `date_since`. Graph API only.
 - `graph_search` -- KQL search expression for Graph API keyword/partial matching. Cannot be combined with `graph_filter` or `date_since`. Graph API only.
 - `imap_folder` -- Folder to get the emails from. Defaults to `INBOX`. For IMAP: folder path. For Graph API: well-known name (inbox, sentitems, etc.) or display name.
 - `date_since` -- Date in YYYY-MM-DD format or dateparser string (e.g. `5 days ago`). Cannot be combined with `graph_search`.
 - `download_content` -- (boolean) if true, content of the email will be downloaded into the `out/tables/emails.csv` table
 - `mark_seen` -- (boolean) When set to true, emails that have been extracted will be marked as seen in the inbox.
 - `download_attachments` -- (boolean) if true, attachments of the email will be downloaded into `out/files/` folder, prefixed by generated email `pk`.
 - `attachment_pattern` -- (str) Applicable only with `download_attachments:true`. Regex pattern to filter particular attachments. e.g. to retrieve only pdf file types use: .+\.pdf

 
 

### query (IMAP only)

IMAP search query. E.g. `(FROM "email" SUBJECT "the subject" UNSEEN)`

More information on keywords [here](docs/imap-search.md)

### graph_filter (Graph API only)

OData `$filter` expression for exact matching. Can be combined with `date_since`.

| Need | Example |
|---|---|
| Exact sender | `from/emailAddress/address eq 'someone@example.com'` |
| Exact subject | `subject eq 'Exact Subject Line'` |
| Has attachments | `hasAttachments eq true` |
| Combined | `from/emailAddress/address eq 'x@y.com' and subject eq 'text'` |

Note: `contains()` on subject/body is not supported by the messages endpoint and returns HTTP 400.

### graph_search (Graph API only)

KQL search expression for keyword and partial matching. **Cannot be combined with `graph_filter` or `date_since`** — this is a [Microsoft Graph API limitation](https://learn.microsoft.com/en-us/graph/known-issues#some-limitations-apply-to-query-parameters). Returns up to 1,000 results.

| Need | Example | Notes |
|---|---|---|
| Subject keyword | `subject:weekly` | substring match |
| Subject exact phrase | `subject:"exact multi-word phrase"` | use double quotes |
| Sender full or partial | `from:someone@example.com` or `from:MSSecurity` | substring match |
| Date exact | `received:2026-03-17` | single day |
| Date range | `received:2026-01-01..2026-01-31` | inclusive, `..` syntax only |
| All combined | `from:sender subject:keyword received:2026-01-01..2026-03-18` | space-separated = AND |

Note: relative date keywords (`received:this week`, `received:today`) are not supported on the messages endpoint and are treated as free-text.

### Choosing the right filter field

| Use case | Field | Combinable with `date_since`? |
|---|---|---|
| Exact sender / exact subject | `graph_filter` | Yes |
| Keyword / partial matching | `graph_search` | No — use `received:` in KQL instead |
| Keyword + date range | `graph_search` with `received:YYYY-MM-DD..YYYY-MM-DD` | N/A (date is in KQL) |
| Date only | `date_since` | N/A |

## Example:

```
{
    "#password": "xxxxx",
    "user_name": "example@gmail.com",
    "host": "imap.gmail.com",
    "port": 993,
    "query":"(FROM "email" SUBJECT "the subject" UNSEEN)",
    "download_content": true,
    "download_attachments": true,
    "attachment_pattern": ".+\\.pdf"

  }
```

Output
======

Single table named `emails`.

Columns: `['pk', 'uid', 'mail_box', 'date', 'from', 'to', 'body', 'headers', 'number_of_attachments', 'size']`


Attachments in `out/files/` prefixed by the generated message `pk`. e.g. `out/files/bb41793268d4a8710fb5ebd94eaed6bc_some_file.pdf`

Development
-----------

If required, change local data folder (the `CUSTOM_FOLDER` placeholder) path to
your custom path in the docker-compose file:

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    volumes:
      - ./:/code
      - ./CUSTOM_FOLDER:/data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Clone this repository, init the workspace and run the component with following
command:

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
git clone https://bitbucket.org/kds_consulting_team/kds-team.ex-email-content.git
cd kds-team.ex-email-content
docker-compose build
docker-compose run --rm dev
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Run the test suite and lint check using this command:

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
docker-compose run --rm test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integration
===========

For information about deployment and integration with KBC, please refer to the
[deployment section of developers
documentation](https://developers.keboola.com/extend/component/deployment/)
