import base64
import csv
import hashlib
import json
import logging
import re
from typing import TYPE_CHECKING

import requests
from keboola.component.dao import FileDefinition
from keboola.component.exceptions import UserException
from keboola.utils import header_normalizer
from keboola.utils.date import parse_datetime_interval
from keboola.utils.header_normalizer import NormalizerStrategy

if TYPE_CHECKING:
    from configuration import Configuration

# Graph API constants
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_PAGE_SIZE = 100
MS_GRAPH_SCOPE = ["https://graph.microsoft.com/Mail.ReadWrite.Shared"]

# Graph API well-known folder name mapping
GRAPH_WELL_KNOWN_FOLDERS = {
    "inbox": "inbox",
    "sentitems": "sentitems",
    "sent items": "sentitems",
    "drafts": "drafts",
    "deleteditems": "deleteditems",
    "deleted items": "deleteditems",
    "junkemail": "junkemail",
    "junk email": "junkemail",
    "archive": "archive",
    "outbox": "outbox",
}


class GraphEmailFetcher:
    """Handles Microsoft Graph API email fetching with OAuth authentication."""

    def __init__(self, component, config: "Configuration"):
        """
        Initialize Graph API email fetcher.

        Args:
            component: Component instance (for access to create_out_file_definition, OAuth methods, etc.)
            config: Configuration object with all parameters
        """
        self.component = component
        self.config = config
        self._graph_session: requests.Session | None = None

    def fetch(self, output_table, download_content, download_attachments, mark_seen):
        """
        Fetch emails via Microsoft Graph API and write to output table.

        Args:
            output_table: Output table definition for emails
            download_content: Whether to download email content
            download_attachments: Whether to download attachments
            mark_seen: Whether to mark emails as read

        Returns:
            List of FileDefinition objects (output_table + attachments)
        """
        from component import RESULT_COLUMNS

        logging.info("Logging in via Microsoft Graph API..")
        self._init_graph_session()

        folder = self.config.imap_folder or "inbox"
        graph_folder = self._resolve_graph_folder(folder)

        # Build the messages URL with folder
        messages_url = f"{GRAPH_API_BASE}/me/mailFolders/{graph_folder}/messages"

        # Build query parameters
        query_params = self._build_graph_query_params()

        count = 0
        results = [output_table]

        with open(output_table.full_path, "w+", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=RESULT_COLUMNS, dialect="kbc")
            writer.writeheader()

            url = messages_url
            first_request = True

            while url:
                if first_request:
                    response = self._graph_request("GET", url, params=query_params)
                    first_request = False
                else:
                    # Pagination: @odata.nextLink already contains all query params
                    response = self._graph_request("GET", url)

                data = response.json()
                messages = data.get("value", [])

                for msg_data in messages:
                    # Fetch full message with headers and body (both text and html)
                    msg_detail = self._fetch_graph_message_detail(msg_data["id"])

                    # Fetch attachments metadata
                    attachments = []
                    if msg_detail.get("hasAttachments", False) or download_attachments:
                        attachments = self._fetch_graph_attachments_metadata(msg_data["id"])

                    if download_content:
                        row = self._build_email_row_from_graph(msg_detail, attachments)
                        writer.writerow(row)

                    if download_attachments:
                        results.extend(self._write_graph_attachments(msg_data["id"], msg_detail, attachments))

                    if mark_seen and not msg_detail.get("isRead", False):
                        self._graph_mark_as_read(msg_data["id"])

                    count += 1
                    if count % 10 == 0:
                        logging.info(f"Processing messages {count - 10} - {count}")
                        logging.info(f"Processed {len(results) - 1} attachments matching the pattern so far.")

                # Follow pagination
                url = data.get("@odata.nextLink")

        logging.info(f"Processed {count} messages in total.")
        logging.info(f"Processed {len(results) - 1} attachments matching the pattern in total.")
        if count == 0:
            logging.warning("No messages matched the specified filter")

        return results

    def _build_graph_query_params(self):
        """Build OData query parameters for the Graph API messages endpoint."""
        query_params = {
            "$top": str(GRAPH_PAGE_SIZE),
            "$select": "id,subject,from,toRecipients,receivedDateTime,hasAttachments,isRead",
        }

        if self.config.graph_search:
            # $search uses KQL syntax; $orderby and $filter are incompatible with $search
            # on the messages endpoint. See: https://learn.microsoft.com/en-us/graph/
            # search-query-parameter#use-search-on-message-collections
            search_value = self.config.graph_search.replace('"', "'")
            query_params["$search"] = f'"{search_value}"'
        else:
            # Build $filter from graph_filter parameter and date_since
            filters = []

            graph_filter = self.config.graph_filter
            if graph_filter:
                filters.append(graph_filter)

            date_since_str = self.config.date_since
            if date_since_str:
                since, _ = parse_datetime_interval(date_since_str, "now", strformat="%Y-%m-%dT00:00:00Z")
                filters.append(f"receivedDateTime ge {since}")

            if filters:
                query_params["$filter"] = " and ".join(filters)

            # $orderby is only safe when $filter uses receivedDateTime alone.
            # Filtering by other properties (e.g. from/emailAddress/address)
            # combined with $orderby triggers HTTP 400: "The restriction or sort
            # order is too complex for this operation."
            # See: https://learn.microsoft.com/en-us/graph/api/user-list-messages
            # #using-filter-and-orderby-in-the-same-query
            if not graph_filter:
                query_params["$orderby"] = "receivedDateTime desc"

        return query_params

    def _fetch_graph_message_detail(self, message_id):
        """Fetch a single message with full body (both text and html) and headers."""
        url = f"{GRAPH_API_BASE}/me/messages/{message_id}"
        params = {
            "$select": (
                "id,subject,from,toRecipients,receivedDateTime,body,hasAttachments,internetMessageHeaders,isRead"
            ),
        }

        # First fetch HTML body (default)
        response_html = self._graph_request("GET", url, params=params)
        msg_html = response_html.json()

        # Then fetch text body
        response_text = self._graph_request(
            "GET",
            url,
            params=params,
            extra_headers={"Prefer": 'outlook.body-content-type="text"'},
        )
        msg_text = response_text.json()

        # Merge: keep the HTML response as base, add text body separately
        msg_html["_body_text"] = msg_text.get("body", {}).get("content", "")
        return msg_html

    def _fetch_graph_attachments_metadata(self, message_id):
        """Fetch attachment metadata for a message."""
        url = f"{GRAPH_API_BASE}/me/messages/{message_id}/attachments"
        params = {"$select": "id,name,contentType,size,isInline"}
        response = self._graph_request("GET", url, params=params)
        return response.json().get("value", [])

    def _write_graph_attachments(self, message_id, msg_detail, attachments) -> list[FileDefinition]:
        """Download and write Graph API attachments, filtered by pattern."""
        from_addr, to_addrs, _, _, size = self._extract_message_fields(msg_detail)
        pattern = self.config.attachment_pattern
        email_pk = self._build_email_pk_from_graph(msg_detail, from_addr, to_addrs, size)

        results = []
        for att in attachments:
            att_name = att.get("name", "")
            if not att_name:
                continue
            # Skip inline attachments
            if att.get("isInline", False):
                continue
            # Apply pattern filter
            if pattern and not re.fullmatch(pattern, att_name):
                continue

            # Fetch full attachment content
            att_url = f"{GRAPH_API_BASE}/me/messages/{message_id}/attachments/{att['id']}"
            att_response = self._graph_request("GET", att_url)
            att_data = att_response.json()

            content_bytes = base64.b64decode(att_data.get("contentBytes", ""))

            normalizer = header_normalizer.get_normalizer(
                NormalizerStrategy.DEFAULT,
                permitted_chars=header_normalizer.PERMITTED_CHARS + ".",
            )
            file_path = normalizer.normalize_header([f"{email_pk}_{att_name}"])[0]
            file_def = self.component.create_out_file_definition(
                file_path,
                tags=[
                    f"email_pk: {email_pk}",
                    f"email_date: {msg_detail.get('receivedDateTime', '')}",
                ],
            )
            with open(file_def.full_path, "wb") as out_file:
                out_file.write(content_bytes)
            results.append(file_def)

        return results

    def _graph_mark_as_read(self, message_id):
        """Mark a message as read via Graph API."""
        url = f"{GRAPH_API_BASE}/me/messages/{message_id}"
        self._graph_request("PATCH", url, json_body={"isRead": True})

    def _resolve_graph_folder(self, folder_name):
        """Resolve a folder name to a Graph API well-known folder name or folder ID."""
        normalized = folder_name.strip().lower()

        # Check well-known folder names
        if normalized in GRAPH_WELL_KNOWN_FOLDERS:
            return GRAPH_WELL_KNOWN_FOLDERS[normalized]

        # Try to find the folder by display name
        url = f"{GRAPH_API_BASE}/me/mailFolders"
        params = {"$filter": f"displayName eq '{folder_name}'"}
        try:
            response = self._graph_request("GET", url, params=params)
            folders = response.json().get("value", [])
            if folders:
                return folders[0]["id"]
        except UserException:
            pass

        raise UserException(
            f"Mail folder '{folder_name}' not found. Use a well-known folder name "
            f"(inbox, sentitems, drafts, deleteditems, junkemail, archive, outbox) "
            f"or the exact display name of the folder."
        )

    def _init_graph_session(self):
        """Initialize an authenticated requests.Session for Graph API calls."""
        refresh_token = self.component.get_refresh_token()
        access_token = self.component.get_access_token(refresh_token=refresh_token, scopes=MS_GRAPH_SCOPE)

        self._graph_session = requests.Session()
        self._graph_session.headers.update(
            {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
        )

    def _graph_request(self, method, url, params=None, json_body=None, extra_headers=None):
        """Make an authenticated Graph API request with error handling."""
        headers = {}
        if extra_headers:
            headers.update(extra_headers)

        try:
            response = self._graph_session.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
                headers=headers,
            )
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else "unknown"
            error_body = ""
            if e.response is not None:
                try:
                    error_data = e.response.json()
                    error_body = error_data.get("error", {}).get("message", e.response.text)
                except (ValueError, KeyError):
                    error_body = e.response.text

            if status_code == 401:
                raise UserException(
                    "Authentication failed with Microsoft Graph API. Please re-authorize the application."
                ) from e
            elif status_code == 403:
                raise UserException(
                    "Access denied by Microsoft Graph API. "
                    "Ensure the application has Mail.ReadWrite permissions. "
                    f"Details: {error_body}"
                ) from e
            elif status_code == 404:
                raise UserException(f"Resource not found in Microsoft Graph API. Details: {error_body}") from e
            else:
                raise UserException(
                    f"Microsoft Graph API request failed (HTTP {status_code}). Details: {error_body}"
                ) from e
        except requests.exceptions.ConnectionError as e:
            raise UserException(
                "Failed to connect to Microsoft Graph API. Please check your network connection."
            ) from e

    def _extract_message_fields(self, msg):
        """Extract common fields from a Graph API message dict."""
        from_data = msg.get("from", {})
        from_addr = from_data.get("emailAddress", {}).get("address", "") if from_data else ""

        to_addrs = [r.get("emailAddress", {}).get("address", "") for r in msg.get("toRecipients", [])]

        body_html = msg.get("body", {}).get("content", "") if msg.get("body", {}).get("contentType") == "html" else ""
        body_text = msg.get("_body_text", "")
        size = len(body_html.encode("utf-8")) if body_html else len(body_text.encode("utf-8"))

        return from_addr, to_addrs, body_html, body_text, size

    def _build_email_row_from_graph(self, msg, attachments):
        """Build an email row dict from a Graph API message response, matching IMAP output format."""
        from_addr, to_addrs, body_html, body_text, size = self._extract_message_fields(msg)

        headers_list = msg.get("internetMessageHeaders", [])
        headers_dict = {}
        if headers_list:
            for h in headers_list:
                name = h.get("name", "")
                value = h.get("value", "")
                if name in headers_dict:
                    if isinstance(headers_dict[name], list):
                        headers_dict[name].append(value)
                    else:
                        headers_dict[name] = [headers_dict[name], value]
                else:
                    headers_dict[name] = value

        att_names = [a.get("name", "") for a in attachments if not a.get("isInline", False)]

        return {
            "pk": self._build_email_pk_from_graph(msg, from_addr, to_addrs, size),
            "uid": msg.get("id", ""),
            "mail_box": self.config.user_name,
            "date": msg.get("receivedDateTime", ""),
            "from": from_addr,
            "to": ";".join(to_addrs),
            "subject": msg.get("subject", ""),
            "body": body_text,
            "body_html": body_html,
            "headers": json.dumps(headers_dict),
            "number_of_attachments": len(att_names),
            "attachment_names": att_names,
            "size": size,
        }

    def _build_email_pk_from_graph(self, msg, from_addr, to_addrs, size):
        """Build a primary key hash from a Graph API message, matching IMAP PK logic."""
        uid = msg.get("id", "")
        mail_box = self.config.user_name
        date = msg.get("receivedDateTime", "")
        to = ";".join(to_addrs)
        size_str = str(size)

        key = "|".join([uid, mail_box, date, from_addr, to, size_str])
        return hashlib.md5(key.encode()).hexdigest()

    def close(self):
        """Close the Graph API session."""
        if self._graph_session is not None:
            self._graph_session.close()
