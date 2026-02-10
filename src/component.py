import logging
import warnings

import msal
from keboola.component.base import ComponentBase
from keboola.component.exceptions import UserException

from configuration import CONNECTION_METHOD_GRAPH, CONNECTION_METHOD_IMAP, Configuration
from graph_client import GraphEmailFetcher
from imap_client import ImapEmailFetcher

# Result columns for email output
RESULT_COLUMNS = [
    "pk",
    "uid",
    "mail_box",
    "date",
    "from",
    "to",
    "subject",
    "body",
    "body_html",
    "headers",
    "number_of_attachments",
    "size",
    "attachment_names",
]

# State keys (not config parameters)
KEY_STATE_REFRESH_TOKEN = "#refresh_token"

# Microsoft OAuth scopes
MS_IMAP_SCOPE = ["https://outlook.office.com/IMAP.AccessAsUser.All"]

REQUIRED_IMAGE_PARS = []


class Component(ComponentBase):
    def __init__(self):
        super().__init__()
        # temp suppress pytz warning
        warnings.filterwarnings(
            "ignore",
            message="The localize method is no longer necessary, as this time zone supports the fold attribute",
        )

    @property
    def use_oauth_login(self):
        return self.environment_variables.component_id == "kds-team.ex-ms-outlook-email-content"

    @property
    def connection_method(self):
        # Access the raw parameters for this property check
        return self.configuration.parameters.get("connection_method", CONNECTION_METHOD_IMAP)

    @property
    def _use_graph_api(self):
        return self.use_oauth_login and self.connection_method == CONNECTION_METHOD_GRAPH

    def run(self):
        """
        Main execution code
        """
        # Parse and validate configuration
        config = Configuration(**self.configuration.parameters)

        output_table = self.create_out_table_definition("emails.csv", primary_key=["pk"], incremental=True)

        if self._use_graph_api:
            fetcher = GraphEmailFetcher(self, config)
            results = fetcher.fetch(
                output_table, config.download_content, config.download_attachments, config.mark_seen
            )
            fetcher.close()
        else:
            fetcher = ImapEmailFetcher(self, config)
            results = fetcher.fetch(
                output_table, config.download_content, config.download_attachments, config.mark_seen
            )
            fetcher.close()

        self.write_manifests(results)
        logging.info("Extraction finished.")

    def get_access_token(self, refresh_token, scopes=None):
        """
        Acquire an OAuth access token using MSAL.

        Args:
            refresh_token: OAuth refresh token
            scopes: List of OAuth scopes (defaults to MS_IMAP_SCOPE)

        Returns:
            Access token string
        """
        scopes = scopes or MS_IMAP_SCOPE
        authority = self.configuration.image_parameters.get("authority") or "https://login.microsoftonline.com/common"
        app = msal.ConfidentialClientApplication(
            self.configuration.oauth_credentials.appKey,
            authority=authority,
            client_credential=self.configuration.oauth_credentials.appSecret,
        )

        result = app.acquire_token_by_refresh_token(refresh_token, scopes)

        if "access_token" not in result:
            raise UserException(
                f"Failed to login with oAuth. "
                f"Try to clear state and reauthorize the application.\n"
                f"Got error {result.get('error')}. "
                f"Error description : {result.get('error_description')}. "
                f"Correlation ID : {result.get('correlation_id')}"
            )

        self.write_state_file({KEY_STATE_REFRESH_TOKEN: result["refresh_token"]})
        return result["access_token"]

    def get_refresh_token(self):
        """
        Get OAuth refresh token from state or OAuth credentials.

        Returns:
            Refresh token string
        """
        state = self.get_state_file()
        return state.get(KEY_STATE_REFRESH_TOKEN) or self.configuration.oauth_credentials.data.get("refresh_token")


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
