import json
import os
import unittest
from unittest import mock
from unittest.mock import MagicMock, patch, PropertyMock

from freezegun import freeze_time
from keboola.component.exceptions import UserException

from component import (
    Component,
    RESULT_COLUMNS,
)
from configuration import CONNECTION_METHOD_GRAPH, CONNECTION_METHOD_IMAP, Configuration
from graph_client import GraphEmailFetcher


class TestComponent(unittest.TestCase):
    # set global time to 2010-10-10 - affects functions like datetime.now()
    @freeze_time("2010-10-10")
    # set KBC_DATADIR env to non-existing dir
    @mock.patch.dict(os.environ, {"KBC_DATADIR": "./non-existing-dir"})
    def test_run_no_cfg_fails(self):
        with self.assertRaises(ValueError):
            comp = Component()
            comp.run()


# Sample Graph API responses for mocking
SAMPLE_GRAPH_MESSAGE = {
    "id": "AAMkAGU_test_message_id",
    "subject": "Test Subject",
    "from": {"emailAddress": {"name": "Sender Name", "address": "sender@example.com"}},
    "toRecipients": [
        {
            "emailAddress": {
                "name": "Recipient One",
                "address": "recipient1@example.com",
            }
        },
        {
            "emailAddress": {
                "name": "Recipient Two",
                "address": "recipient2@example.com",
            }
        },
    ],
    "receivedDateTime": "2024-01-15T10:30:00Z",
    "hasAttachments": True,
    "isRead": False,
    "body": {"contentType": "html", "content": "<p>Hello World</p>"},
    "internetMessageHeaders": [
        {"name": "From", "value": "sender@example.com"},
        {"name": "To", "value": "recipient1@example.com"},
        {"name": "Subject", "value": "Test Subject"},
    ],
    "_body_text": "Hello World",
}

SAMPLE_GRAPH_ATTACHMENT = {
    "id": "att_123",
    "name": "report.csv",
    "contentType": "text/csv",
    "size": 1024,
    "isInline": False,
    "contentBytes": "Y29sX2EsY29sX2IKMSwyIAo=",
}

SAMPLE_GRAPH_INLINE_ATTACHMENT = {
    "id": "att_inline_456",
    "name": "image.png",
    "contentType": "image/png",
    "size": 512,
    "isInline": True,
}


class _GraphTestBase(unittest.TestCase):
    """Base class that sets up a GraphEmailFetcher with mocked configuration for Graph API tests."""

    def setUp(self):
        # Create a mock component
        self.mock_component = MagicMock()
        self.mock_component.environment_variables = MagicMock()
        self.mock_component.environment_variables.component_id = "kds-team.ex-ms-outlook-email-content"

    def _create_config(self, overrides=None):
        """Create a Configuration object with default Graph API test params."""
        params = {
            "user_name": "test@example.com",
            "connection_method": CONNECTION_METHOD_GRAPH,
            "download_content": True,
            "download_attachments": False,
            "mark_seen": True,
            "date_since": "",
            "imap_folder": "inbox",
            "graph_filter": "",
            "attachment_pattern": "",
        }
        if overrides:
            params.update(overrides)
        return Configuration(**params)

    def _create_fetcher(self, config_overrides=None):
        """Create a GraphEmailFetcher with a Configuration object."""
        config = self._create_config(config_overrides)
        fetcher = GraphEmailFetcher.__new__(GraphEmailFetcher)
        fetcher.component = self.mock_component
        fetcher.config = config
        fetcher._graph_session = None
        return fetcher


class TestGraphApiRowBuilder(_GraphTestBase):
    """Test that Graph API produces rows with the same columns as IMAP."""

    def test_build_email_row_from_graph_has_correct_columns(self):
        fetcher = self._create_fetcher()
        row = fetcher._build_email_row_from_graph(SAMPLE_GRAPH_MESSAGE, [SAMPLE_GRAPH_ATTACHMENT])

        for col in RESULT_COLUMNS:
            self.assertIn(col, row, f"Missing column: {col}")
        self.assertEqual(set(row.keys()), set(RESULT_COLUMNS))

    def test_build_email_row_from_graph_values(self):
        fetcher = self._create_fetcher()
        row = fetcher._build_email_row_from_graph(SAMPLE_GRAPH_MESSAGE, [SAMPLE_GRAPH_ATTACHMENT])

        self.assertEqual(row["uid"], "AAMkAGU_test_message_id")
        self.assertEqual(row["mail_box"], "test@example.com")
        self.assertEqual(row["date"], "2024-01-15T10:30:00Z")
        self.assertEqual(row["from"], "sender@example.com")
        self.assertEqual(row["to"], "recipient1@example.com;recipient2@example.com")
        self.assertEqual(row["subject"], "Test Subject")
        self.assertEqual(row["body"], "Hello World")
        self.assertIn("<p>Hello World</p>", row["body_html"])
        self.assertEqual(row["number_of_attachments"], 1)
        self.assertEqual(row["attachment_names"], ["report.csv"])
        self.assertIsInstance(row["pk"], str)
        self.assertEqual(len(row["pk"]), 32)  # MD5 hex digest

    def test_build_email_row_from_graph_inline_attachments_excluded(self):
        fetcher = self._create_fetcher()
        row = fetcher._build_email_row_from_graph(
            SAMPLE_GRAPH_MESSAGE,
            [SAMPLE_GRAPH_ATTACHMENT, SAMPLE_GRAPH_INLINE_ATTACHMENT],
        )
        self.assertEqual(row["number_of_attachments"], 1)
        self.assertEqual(row["attachment_names"], ["report.csv"])

    def test_build_email_row_from_graph_empty_message(self):
        fetcher = self._create_fetcher()
        empty_msg = {
            "id": "empty_msg_id",
            "subject": "",
            "from": {},
            "toRecipients": [],
            "receivedDateTime": "2024-01-01T00:00:00Z",
            "hasAttachments": False,
            "isRead": True,
            "body": {"contentType": "html", "content": ""},
            "internetMessageHeaders": [],
            "_body_text": "",
        }
        row = fetcher._build_email_row_from_graph(empty_msg, [])

        self.assertEqual(row["from"], "")
        self.assertEqual(row["to"], "")
        self.assertEqual(row["subject"], "")
        self.assertEqual(row["body"], "")
        self.assertEqual(row["number_of_attachments"], 0)
        self.assertEqual(row["attachment_names"], [])

    def test_build_email_row_from_graph_headers_json(self):
        fetcher = self._create_fetcher()
        row = fetcher._build_email_row_from_graph(SAMPLE_GRAPH_MESSAGE, [])

        headers = json.loads(row["headers"])
        self.assertEqual(headers["From"], "sender@example.com")
        self.assertEqual(headers["Subject"], "Test Subject")


class TestGraphApiPkBuilder(_GraphTestBase):
    """Test primary key generation for Graph API messages."""

    def test_pk_is_deterministic(self):
        fetcher = self._create_fetcher()
        from_addr, to_addrs, _, _, size = fetcher._extract_message_fields(SAMPLE_GRAPH_MESSAGE)
        pk1 = fetcher._build_email_pk_from_graph(SAMPLE_GRAPH_MESSAGE, from_addr, to_addrs, size)
        pk2 = fetcher._build_email_pk_from_graph(SAMPLE_GRAPH_MESSAGE, from_addr, to_addrs, size)
        self.assertEqual(pk1, pk2)

    def test_pk_is_md5_hex(self):
        fetcher = self._create_fetcher()
        from_addr, to_addrs, _, _, size = fetcher._extract_message_fields(SAMPLE_GRAPH_MESSAGE)
        pk = fetcher._build_email_pk_from_graph(SAMPLE_GRAPH_MESSAGE, from_addr, to_addrs, size)
        self.assertEqual(len(pk), 32)
        int(pk, 16)

    def test_different_messages_have_different_pks(self):
        fetcher = self._create_fetcher()
        msg2 = dict(SAMPLE_GRAPH_MESSAGE)
        msg2["id"] = "different_id"

        from_addr1, to_addrs1, _, _, size1 = fetcher._extract_message_fields(SAMPLE_GRAPH_MESSAGE)
        from_addr2, to_addrs2, _, _, size2 = fetcher._extract_message_fields(msg2)
        pk1 = fetcher._build_email_pk_from_graph(SAMPLE_GRAPH_MESSAGE, from_addr1, to_addrs1, size1)
        pk2 = fetcher._build_email_pk_from_graph(msg2, from_addr2, to_addrs2, size2)
        self.assertNotEqual(pk1, pk2)


class TestGraphApiQueryParams(_GraphTestBase):
    """Test Graph API query parameter building."""

    def test_build_params_no_filter(self):
        fetcher = self._create_fetcher({"graph_filter": "", "date_since": ""})
        params = fetcher._build_graph_query_params()

        self.assertEqual(params["$top"], "100")
        self.assertIn("$orderby", params)
        self.assertNotIn("$filter", params)

    def test_build_params_with_graph_filter(self):
        fetcher = self._create_fetcher(
            {
                "graph_filter": "from/emailAddress/address eq 'test@example.com'",
                "date_since": "",
            }
        )
        params = fetcher._build_graph_query_params()

        self.assertIn("$filter", params)
        self.assertIn("from/emailAddress/address eq 'test@example.com'", params["$filter"])

    @freeze_time("2024-06-15")
    def test_build_params_with_date_since(self):
        fetcher = self._create_fetcher({"graph_filter": "", "date_since": "2024-01-01"})
        params = fetcher._build_graph_query_params()

        self.assertIn("$filter", params)
        self.assertIn("receivedDateTime ge", params["$filter"])

    @freeze_time("2024-06-15")
    def test_build_params_with_both_filters(self):
        fetcher = self._create_fetcher(
            {
                "graph_filter": "hasAttachments eq true",
                "date_since": "2024-01-01",
            }
        )
        params = fetcher._build_graph_query_params()

        self.assertIn("$filter", params)
        self.assertIn("hasAttachments eq true", params["$filter"])
        self.assertIn("receivedDateTime ge", params["$filter"])
        self.assertIn(" and ", params["$filter"])


class TestGraphApiFolderResolve(_GraphTestBase):
    """Test Graph API folder name resolution."""

    def test_well_known_folder_inbox(self):
        fetcher = self._create_fetcher()
        fetcher._graph_session = MagicMock()
        self.assertEqual(fetcher._resolve_graph_folder("INBOX"), "inbox")

    def test_well_known_folder_sent_items(self):
        fetcher = self._create_fetcher()
        fetcher._graph_session = MagicMock()
        self.assertEqual(fetcher._resolve_graph_folder("Sent Items"), "sentitems")

    def test_well_known_folder_drafts(self):
        fetcher = self._create_fetcher()
        fetcher._graph_session = MagicMock()
        self.assertEqual(fetcher._resolve_graph_folder("drafts"), "drafts")

    def test_well_known_folder_case_insensitive(self):
        fetcher = self._create_fetcher()
        fetcher._graph_session = MagicMock()
        self.assertEqual(fetcher._resolve_graph_folder("DRAFTS"), "drafts")
        self.assertEqual(fetcher._resolve_graph_folder("Inbox"), "inbox")


class TestConnectionMethodProperty(unittest.TestCase):
    """Test connection method detection properties."""

    def setUp(self):
        self.comp = Component.__new__(Component)

    def _patch_config(self, params=None):
        """Patch the configuration property and environment_variables on the component."""
        default_params = {
            "user_name": "test@example.com",
            "connection_method": params.get("connection_method", CONNECTION_METHOD_GRAPH)
            if params
            else CONNECTION_METHOD_GRAPH,
        }
        if params:
            default_params.update(params)

        cfg = MagicMock()
        cfg.parameters = default_params
        cfg.image_parameters = {}

        config_patcher = patch.object(
            type(self.comp),
            "configuration",
            new_callable=PropertyMock,
            return_value=cfg,
        )
        self.mock_config = config_patcher.start()
        self.addCleanup(config_patcher.stop)

        self.comp.environment_variables = MagicMock()
        self.comp.environment_variables.component_id = "kds-team.ex-ms-outlook-email-content"
        return cfg

    def test_use_graph_api_true(self):
        self._patch_config(params={"connection_method": CONNECTION_METHOD_GRAPH})
        self.assertTrue(self.comp._use_graph_api)

    def test_use_graph_api_false_imap(self):
        self._patch_config(params={"connection_method": CONNECTION_METHOD_IMAP})
        self.assertFalse(self.comp._use_graph_api)

    def test_use_graph_api_false_generic_component(self):
        self._patch_config(params={"connection_method": CONNECTION_METHOD_GRAPH})
        self.comp.environment_variables.component_id = "kds-team.ex-email-content"
        self.assertFalse(self.comp._use_graph_api)

    def test_default_connection_method_is_imap(self):
        self._patch_config(params={})
        # Remove connection_method to test default
        self.comp.configuration.parameters = {"user_name": "test@example.com"}
        self.assertEqual(self.comp.connection_method, CONNECTION_METHOD_IMAP)


class TestValidation(unittest.TestCase):
    """Test configuration validation."""

    def test_graph_api_does_not_require_host(self):
        """Graph API connection should work without host parameter."""
        config = Configuration(
            connection_method=CONNECTION_METHOD_GRAPH,
            user_name="test@example.com",
            download_content=True,
        )
        # Should not raise - host is not required for Graph API
        self.assertEqual(config.connection_method, CONNECTION_METHOD_GRAPH)
        self.assertEqual(config.host, "")  # Default empty string is OK

    def test_imap_requires_host(self):
        """IMAP connection requires host parameter."""
        with self.assertRaises(UserException) as cm:
            Configuration(
                connection_method=CONNECTION_METHOD_IMAP,
                user_name="test@example.com",
                download_content=True,
                # Missing host - should fail validation
            )
        self.assertIn("host is required", str(cm.exception))

    def test_requires_download_option(self):
        """Must enable at least one of download_content or download_attachments."""
        with self.assertRaises(UserException) as cm:
            Configuration(
                user_name="test@example.com",
                host="outlook.office365.com",
                download_content=False,
                download_attachments=False,
            )
        self.assertIn("Nothing selected for download", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
