# Email Content Extractor


Extract email body and other metadata using IMAP protocol.

**Table of contents:**

[TOC]

# Functionality notes


# Prerequisites


Have IMAP service enabled on your Email account. Please refer to your email provider for more information.

Note that for GMAIL you will need to enable access for the ["less secure" apps](https://support.google.com/accounts/answer/6010255?hl=en). 
 

# KBC Features


| **Feature**             | **Note**                                      |
|-------------------------|-----------------------------------------------|
| Generic UI form         | Dynamic UI form |             
| Row based configuration         | Dynamic UI form |             
| Incremental loading     | Allows fetching data in new increments.       |


# Configuration

## Supported parameters:

 - `#password` --  login
 - `user_name` -- login
 - `host` -- IMAP HOST
 - `query` -- Query string to filter emails. E.g. `(FROM "email" SUBJECT "the subject" UNSEEN)`, More information on keywords [here](docs/imap-search.md)
 - `download_content` -- (boolean) if true, content of the email will be downloaded into the `out/tables/emails.csv` table
 - `download_attachments` -- (boolean) if true, attachments of the email will be downloaded into `out/files/` folder, prefixed by generated email `pk`.
 - `attachment_pattern` -- (str) Applicable only with `download_attachments:true`. Regex pattern to filter particular attachments. e.g. to retrieve only pdf file types use: .+\.pdf

 
 

### query

Query string to filter emails. E.g. `(FROM "email" SUBJECT "the subject" UNSEEN)`

More information on keywords [here](docs/imap-search.md)

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
git clone repo_path my-new-component
cd my-new-component
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
