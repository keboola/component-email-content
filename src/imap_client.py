import csv
import hashlib
import imaplib
import json
import logging
import re
import socket
from typing import List, TYPE_CHECKING

from imap_tools import MailBox, MailMessage, MailboxLoginError, MailboxFolderSelectError  # type: ignore[attr-defined]
from keboola.component.dao import FileDefinition
from keboola.component.exceptions import UserException
from keboola.utils import header_normalizer
from keboola.utils.date import parse_datetime_interval
from keboola.utils.header_normalizer import NormalizerStrategy

if TYPE_CHECKING:
    from configuration import Configuration

# Microsoft OAuth scope for IMAP
MS_IMAP_SCOPE = ["https://outlook.office.com/IMAP.AccessAsUser.All"]


class ImapEmailFetcher:
    """Handles IMAP email fetching with OAuth or username/password authentication."""

    def __init__(self, component, config: "Configuration"):
        """
        Initialize IMAP email fetcher.

        Args:
            component: Component instance (for access to create_out_file_definition, OAuth methods, etc.)
            config: Configuration object with all parameters
        """
        self.component = component
        self.config = config
        self._imap_client = None

    def fetch(self, output_table, download_content, download_attachments, mark_seen):
        """
        Fetch emails via IMAP and write to output table.

        Args:
            output_table: Output table definition for emails
            download_content: Whether to download email content
            download_attachments: Whether to download attachments
            mark_seen: Whether to mark emails as read

        Returns:
            List of FileDefinition objects (output_table + attachments)
        """
        from component import RESULT_COLUMNS

        logging.info("Logging in via IMAP..")
        self._init_imap_client()

        query = self.config.query
        date_since_str = self.config.date_since or "2000-01-01"
        date_to = "now"
        since, to = parse_datetime_interval(date_since_str, date_to, strformat="%d-%b-%Y")
        since_search = f"(SINCE {since})"

        if self.config.date_since:
            query = f"{query} {since_search}"

        logging.info(f"Getting messages with query {query} from folder {self._imap_client.folder.get()}")
        msgs = self._imap_client.fetch(criteria=query, mark_seen=mark_seen)

        count = 0
        results = [output_table]
        try:
            with open(output_table.full_path, "w+", encoding="utf-8") as output:
                writer = csv.DictWriter(output, fieldnames=RESULT_COLUMNS, dialect="kbc")
                writer.writeheader()

                for count, msg in enumerate(msgs):
                    if download_content:
                        self._write_message_content(writer, msg)

                    if download_attachments:
                        results.extend(self._write_message_attachments(msg))

                    if count % 10 == 0:
                        logging.info(f"Processing messages {count} - {count + 10}")
                        logging.info(f"Processed {len(results) - 1} attachments matching the pattern so far.")
        except imaplib.IMAP4.error as e:
            if "SEARCH command error" in str(e):
                raise UserException(f'Invalid search query, please check the syntax: "{query}"')
        except UnicodeError as e:
            raise UserException(
                "UnicodeError Encountered\n\n"
                "An issue commonly associated with the use of diacritics or special "
                "characters in queries has been detected.\n\n"
                "To resolve this:\n"
                "- Remove special characters from your query.\n"
                "- Filter by 'SENDER' or 'KEYWORD'.\n\n"
                "For detailed guidance on IMAP query options, visit:\n"
                "https://help.keboola.com/components/extractors/communication/email-imap/query-syntax/"
            ) from e

        logging.info(f"Processed {count} messages in total.")
        logging.info(f"Processed {len(results) - 1} attachments matching the pattern in total.")
        if count == 0:
            logging.warning("No messages matched the specified filter")

        return results

    def _init_imap_client(self):
        """Initialize the IMAP client - dispatches to OAuth or username/password."""
        if self.component.use_oauth_login:
            self._init_client_from_oauth()
        else:
            self._init_client_from_username_and_pass()

    def _init_client_from_oauth(self):
        """Initialize IMAP client using OAuth authentication."""
        refresh_token = self.component.get_refresh_token()
        access_token = self.component.get_access_token(refresh_token=refresh_token, scopes=MS_IMAP_SCOPE)
        try:
            self._imap_client = MailBox(self.config.host, self.config.port).xoauth2(self.config.user_name, access_token)
        except imaplib.IMAP4.error as e:
            raise e
        except socket.gaierror as e:
            raise e

        imap_folder = self.config.imap_folder or "INBOX"
        self._set_client_inbox(imap_folder)

    def _init_client_from_username_and_pass(self):
        """Initialize IMAP client using username and password authentication."""
        # Validate required fields (host, user, port, password)
        if not self.config.host:
            raise UserException("host is required for IMAP username/password authentication")
        if not self.config.user_name:
            raise UserException("user_name is required")
        if not self.config.password:
            raise UserException("#password is required for IMAP username/password authentication")

        try:
            self._imap_client = MailBox(self.config.host, self.config.port)
        except Exception as e:
            raise UserException(
                f"Failed to login, please check your credentials and connection settings. Details: {e}"
            ) from e

        imap_folder = self.config.imap_folder or "INBOX"
        try:
            self._imap_client.login(
                username=self.config.user_name,
                password=self.config.password,
                initial_folder=imap_folder,
            )
        except MailboxLoginError as e:
            raise UserException(
                f"Failed to login, please check your credentials and connection settings. \nDetails: {e}"
            ) from e
        except (MailboxLoginError, imaplib.IMAP4.error) as e:
            raise UserException("Failed to login, please check your credentials and connection settings.") from e

    def _set_client_inbox(self, imap_folder):
        """Set the IMAP folder to read from."""
        try:
            self._imap_client.folder.set(imap_folder)
        except MailboxFolderSelectError as e:
            raise UserException(f"Failed to login to inbox {imap_folder}. Make sure it exists") from e

    def _filter_attachments_by_pattern(self, msg: MailMessage):
        """Filter message attachments by regex pattern."""
        pattern = self.config.attachment_pattern
        attachments = msg.attachments
        if pattern:
            attachments = [a for a in attachments if re.fullmatch(pattern, a.filename)]

        return attachments

    def _write_message_attachments(self, msg: MailMessage) -> List[FileDefinition]:
        """Write IMAP message attachments to files."""
        attachments = self._filter_attachments_by_pattern(msg)

        results = []
        for a in attachments:
            email_pk = self._build_email_pk(msg)
            normalizer = header_normalizer.get_normalizer(
                NormalizerStrategy.DEFAULT,
                permitted_chars=header_normalizer.PERMITTED_CHARS + ".",
            )
            file_path = normalizer.normalize_header([f"{email_pk}_{a.filename}"])[0]
            file_def = self.component.create_out_file_definition(
                file_path, tags=[f"email_pk: {email_pk}", f"email_date: {msg.date}"]
            )
            with open(file_def.full_path, "wb") as out_file:
                out_file.write(a.payload)
            results.append(file_def)
        return results

    def _write_message_content(self, writer, msg: MailMessage):
        """Write single email message content to CSV."""
        row = self._build_email_row(msg)
        writer.writerow(row)

    def _build_email_row(self, msg: MailMessage):
        """Build email row dict from IMAP MailMessage."""
        row = {
            "pk": self._build_email_pk(msg),
            "uid": msg.uid,
            "mail_box": self.config.user_name,
            "date": msg.date,
            "from": msg.from_,
            "to": ";".join(msg.to),
            "subject": msg.subject,
            "body": msg.text,
            "body_html": msg.html,
            "headers": json.dumps(msg.headers),
            "number_of_attachments": len(msg.attachments),
            "attachment_names": [a.filename for a in msg.attachments],
            "size": msg.size,
        }

        return row

    def _build_email_pk(self, msg: MailMessage):
        """Build primary key hash from IMAP MailMessage."""
        uid = msg.uid
        mail_box = self.config.user_name
        date = str(msg.date)
        from_addr = msg.from_
        to = ";".join(msg.to)
        size = str(msg.size)

        key = "|".join([uid, mail_box, date, from_addr, to, size])
        return hashlib.md5(key.encode()).hexdigest()

    def close(self):
        """Close the IMAP connection."""
        if self._imap_client is not None:
            self._imap_client.logout()
