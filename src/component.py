import csv
import json
import logging

from imap_tools import MailBox, MailMessage
from keboola.component.base import ComponentBase, UserException

# configuration variables
RESULT_COLUMNS = ['uid', 'mail_box', 'date', 'from', 'to', 'body', 'headers', 'number_of_attachments', 'size']
KEY_PASSWORD = '#password'
KEY_USER = 'user_name'
KEY_HOST = 'host'
KEY_PORT = 'port'
KEY_QUERY = 'query'

# list of mandatory parameters => if some is missing,
# component will fail with readable message on initialization.
REQUIRED_PARAMETERS = [KEY_PASSWORD, KEY_USER, KEY_HOST]
REQUIRED_IMAGE_PARS = []


class Component(ComponentBase):

    def __init__(self):
        super().__init__(required_parameters=REQUIRED_PARAMETERS)
        self._imap_client = self.init_client()

    def run(self):
        '''
        Main execution code
        '''

        params = self.configuration.parameters
        logging.info("Logging in..")
        self.client_login()

        # output table
        output_table = self.create_out_table_definition('emails.csv', primary_key=['uid'], incremental=True)

        query = params.get(KEY_QUERY, '(ALL)')
        logging.info(f"Getting messages with query {query}")
        msgs = self._imap_client.fetch(charset='UTF-8', criteria=query)

        count = 0
        with open(output_table.full_path, 'w+', encoding='utf-8') as output:
            writer = csv.DictWriter(output, fieldnames=RESULT_COLUMNS, dialect='kbc')
            writer.writeheader()
            for msg in msgs:
                count = + 1
                row = self.build_email_row(msg)
                writer.writerow(row)

        logging.info(f"Processed {count} messages")
        self.write_tabledef_manifest(output_table)

        self.close_client()
        logging.info("Extraction finished.")

    def client_login(self):
        params = self.configuration.parameters
        self._imap_client.login(username=params[KEY_USER], password=params[KEY_PASSWORD])

    def init_client(self):
        params = self.configuration.parameters
        return MailBox(params[KEY_HOST], params.get(KEY_PORT, 993))

    def build_email_row(self, msg: MailMessage):
        row = {'uid': msg.uid,
               'mail_box': self.configuration.parameters[KEY_USER],
               'date': msg.date,
               'from': msg.from_,
               'to': ';'.join(msg.to),
               'body': msg.text,
               'headers': json.dumps(msg.headers),
               'number_of_attachments': len(msg.attachments),
               'size': len(msg.attachments)}

        return row

    def close_client(self):
        self._imap_client.logout()


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
