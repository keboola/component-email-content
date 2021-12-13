import csv
import hashlib
import imaplib
import json
import logging
import re
from typing import List

from imap_tools import MailBox, MailMessage, MailboxLoginError
from keboola.component.base import ComponentBase
from keboola.component.dao import FileDefinition
from keboola.component.exceptions import UserException

# configuration variables
RESULT_COLUMNS = ['pk', 'uid', 'mail_box', 'date', 'from', 'to', 'body', 'headers', 'number_of_attachments', 'size']
KEY_PASSWORD = '#password'
KEY_USER = 'user_name'
KEY_HOST = 'host'
KEY_PORT = 'port'
KEY_QUERY = 'query'

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
        self._imap_client = self.init_client()

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

        query = params.get(KEY_QUERY, '(ALL)')
        logging.info(f"Getting messages with query {query}")
        msgs = self._imap_client.fetch(charset='UTF-8', criteria=query)

        count = 0
        results = [output_table]
        with open(output_table.full_path, 'w+', encoding='utf-8') as output:
            writer = csv.DictWriter(output, fieldnames=RESULT_COLUMNS, dialect='kbc')
            writer.writeheader()

            for msg in msgs:
                count = + 1
                if download_content:
                    self._write_message_content(writer, msg)

                if download_attachments:
                    results.extend(self._write_message_attachments(msg))

        logging.info(f"Processed {count} messages")
        self.write_manifests(results)

        self.close_client()
        logging.info("Extraction finished.")

    def client_login(self):
        params = self.configuration.parameters
        try:
            self._imap_client.login(username=params[KEY_USER], password=params[KEY_PASSWORD])
        except MailboxLoginError as e:
            raise UserException(
                f"Failed to login, please check your credentials and connection settings. \nDetails: "
                f"{e}") from e
        except imaplib.IMAP4.error as e:
            raise UserException(
                f"Failed to login, please check your credentials and connection settings. \nDetails: "
                f"{e}") from e

    def init_client(self):
        params = self.configuration.parameters
        return MailBox(params[KEY_HOST], params.get(KEY_PORT, 993))

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

        logging.info(f"{len(attachments)} attachments matching the pattern found.")
        results = []
        for a in attachments:
            email_pk = self._build_email_pk(msg)
            file_def = self.create_out_file_definition(f"{email_pk}_{a.filename}", tags=[f'email_pk: {email_pk}',
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
               'body': msg.text,
               'headers': json.dumps(msg.headers),
               'number_of_attachments': len(msg.attachments),
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
