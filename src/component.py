import csv
import hashlib
import imaplib
import json
import logging
import re
import warnings
from typing import List

from imap_tools import MailBox, MailMessage, MailboxLoginError
from keboola.component.base import ComponentBase
from keboola.component.dao import FileDefinition
from keboola.component.exceptions import UserException
from keboola.utils import header_normalizer
from keboola.utils.date import parse_datetime_interval
# configuration variables
from keboola.utils.header_normalizer import NormalizerStrategy

KEY_IMAP_FOLDER = 'imap_folder'
RESULT_COLUMNS = ['pk', 'uid', 'mail_box', 'date', 'from', 'to', 'subject', 'body', 'body_html', 'headers',
                  'number_of_attachments', 'size', 'attachment_names']

KEY_PASSWORD = '#password'
KEY_USER = 'user_name'
KEY_HOST = 'host'
KEY_PORT = 'port'
KEY_QUERY = 'query'
KEY_MARK_SEEN = 'mark_seen'

KEY_CONTENT = 'download_content'
KEY_ATTACHMENTS = 'download_attachments'
KEY_ATTACHMENT_PATTERN = 'attachment_pattern'

# list of mandatory parameters => if some is missing,
# component will fail with readable message on initialization.
REQUIRED_PARAMETERS = [KEY_PASSWORD, KEY_USER, KEY_HOST]
REQUIRED_IMAGE_PARS = []


class Component(ComponentBase):

    def __init__(self):
        super().__init__()
        self._imap_client: MailBox = self._init_client()
        # temp suppress pytz warning
        warnings.filterwarnings(
            "ignore",
            message="The localize method is no longer necessary, as this time zone supports the fold attribute",
        )

    def run(self):
        """
        Main execution code
        """

        self._validate_configuration()
        params = self.configuration.parameters

        logging.info("Logging in..")
        self.client_login()

        # output table
        output_table = self.create_out_table_definition('emails.csv', primary_key=['pk'], incremental=True)

        download_content = params.get(KEY_CONTENT, True)
        download_attachments = params.get(KEY_ATTACHMENTS, False)

        mark_seen = params.get(KEY_MARK_SEEN, True)

        query = params.get(KEY_QUERY, '(ALL)')
        date_since_str = self.configuration.parameters.get('date_since') or '2000-01-01'
        date_to = 'now'
        since, to = parse_datetime_interval(date_since_str, date_to, strformat='%d-%b-%Y')
        since_search = f'(SINCE {since})'

        if self.configuration.parameters.get('date_since'):
            query = f"{query} {since_search}"

        logging.info(f"Getting messages with query {query} "
                     f"from folder {self._imap_client.folder.get()}")
        msgs = self._imap_client.fetch(criteria=query, mark_seen=mark_seen)

        count = 0
        results = [output_table]
        try:
            with open(output_table.full_path, 'w+', encoding='utf-8') as output:
                writer = csv.DictWriter(output, fieldnames=RESULT_COLUMNS, dialect='kbc')
                writer.writeheader()

                for count, msg in enumerate(msgs):
                    if download_content:
                        self._write_message_content(writer, msg)

                    if download_attachments:
                        results.extend(self._write_message_attachments(msg))

                    if count % 10 == 0:
                        logging.info(f'Processing messages {count} - {count + 10}')
                        logging.info(f'Processed {len(results) - 1} attachments matching the pattern so far.')
        except imaplib.IMAP4.error as e:
            if 'SEARCH command error' in str(e):
                raise UserException(f'Invalid search query, please check the syntax: "{query}"')

        logging.info(f"Processed {count + 1} messages in total.")
        logging.info(f"Processed {len(results)} attachments matching the pattern in total.")
        self.write_manifests(results)

        self.close_client()
        logging.info("Extraction finished.")

    def client_login(self):
        params = self.configuration.parameters
        imap_folder = params.get(KEY_IMAP_FOLDER, 'INBOX') or 'INBOX'
        try:
            self._imap_client.login(username=params[KEY_USER], password=params[KEY_PASSWORD],
                                    initial_folder=imap_folder)
        except MailboxLoginError as e:
            raise UserException(
                "Failed to login, please check your credentials and connection settings. \nDetails: "
                f"{e}") from e
        except (MailboxLoginError, imaplib.IMAP4.error) as e:
            raise UserException(
                "Failed to login, please check your credentials and connection settings.") from e

    def _init_client(self):
        self.validate_configuration_parameters([KEY_HOST, KEY_USER, KEY_PORT, KEY_PASSWORD])
        params = self.configuration.parameters
        try:
            return MailBox(params[KEY_HOST], params.get(KEY_PORT, 993))
        except Exception as e:
            raise UserException(
                f"Failed to login, please check your credentials and connection settings. Details: {e}") from e

    def close_client(self):
        self._imap_client.logout()

    def _filter_attachments_by_pattern(self, msg: MailMessage):
        pattern = self.configuration.parameters.get(KEY_ATTACHMENT_PATTERN, '')
        attachments = msg.attachments
        if pattern:
            attachments = [a for a in attachments if re.fullmatch(pattern, a.filename)]

        return attachments

    def _write_message_attachments(self, msg: MailMessage) -> List[FileDefinition]:
        attachments = self._filter_attachments_by_pattern(msg)

        results = []
        for a in attachments:
            email_pk = self._build_email_pk(msg)
            normalizer = header_normalizer.get_normalizer(NormalizerStrategy.DEFAULT,
                                                          permitted_chars=header_normalizer.PERMITTED_CHARS + '.')
            file_path = normalizer.normalize_header([f"{email_pk}_{a.filename}"])[0]
            file_def = self.create_out_file_definition(file_path, tags=[f'email_pk: {email_pk}',
                                                                        f'email_date: {msg.date}'])
            with open(file_def.full_path, 'wb') as out_file:
                out_file.write(a.payload)
            results.append(file_def)
        return results

    def _write_message_content(self, writer, msg: MailMessage):
        row = self._build_email_row(msg)
        writer.writerow(row)

    def _build_email_row(self, msg: MailMessage):
        row = {'pk': self._build_email_pk(msg),
               'uid': msg.uid,
               'mail_box': self.configuration.parameters[KEY_USER],
               'date': msg.date,
               'from': msg.from_,
               'to': ';'.join(msg.to),
               'subject': msg.subject,
               'body': msg.text,
               'body_html': msg.html,
               'headers': json.dumps(msg.headers),
               'number_of_attachments': len(msg.attachments),
               'attachment_names': [a.filename for a in msg.attachments],
               'size': msg.size}

        return row

    def _build_email_pk(self, msg: MailMessage):
        compound_key = [str(msg.uid),
                        self.configuration.parameters[KEY_USER],
                        str(msg.date),
                        str(msg.from_),
                        ';'.join(msg.to),
                        str(msg.size)
                        ]
        key_str = '|'.join([str(k) for k in compound_key])
        return hashlib.md5(key_str.encode()).hexdigest()

    def _validate_configuration(self):
        self.validate_configuration_parameters(REQUIRED_PARAMETERS)
        if not self.configuration.parameters.get(KEY_CONTENT, True) and not self.configuration.parameters.get(
                KEY_ATTACHMENTS):
            raise UserException("Nothing selected for download, "
                                "please select at least one of the options Attachments or Content!")


"""
        Main entrypoint
"""
if __name__ == "__main__":
    try:
        comp = Component()
        comp.run()
    except UserException as exc:
        logging.exception(exc)
        exit(1)
    except Exception as exc:
        logging.exception(exc)
        exit(2)
