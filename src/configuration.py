"""
Configuration schema for Email Content Extractor.
"""

from typing import Any

from keboola.component.exceptions import UserException
from pydantic import BaseModel, Field, ValidationError, model_validator

CONNECTION_METHOD_IMAP = "imap"
CONNECTION_METHOD_GRAPH = "graph_api"


class Configuration(BaseModel):
    """Configuration for Email Content Extractor."""

    user_name: str
    password: str = Field(default="", alias="#password")
    host: str = Field(default="")
    port: int = Field(default=993)
    connection_method: str = Field(default=CONNECTION_METHOD_IMAP)

    query: str = Field(default="(ALL)")
    graph_filter: str = Field(default="")
    imap_folder: str = Field(default="")
    date_since: str = Field(default="")
    download_content: bool = Field(default=True)
    download_attachments: bool = Field(default=False)
    mark_seen: bool = Field(default=True)
    attachment_pattern: str = Field(default="")

    def __init__(self, **data: Any) -> None:
        try:
            super().__init__(**data)
        except ValidationError as e:
            error_messages = []
            for err in e.errors():
                if err["loc"]:
                    error_messages.append(f"{err['loc'][0]}: {err['msg']}")
                else:
                    error_messages.append(err["msg"])
            raise UserException(f"Configuration validation error: {', '.join(error_messages)}")

    @model_validator(mode="after")
    def validate_connection_requirements(self) -> "Configuration":
        if self.connection_method == CONNECTION_METHOD_IMAP and not self.host:
            raise ValueError("host is required when using IMAP connection method")

        if not self.download_content and not self.download_attachments:
            raise ValueError(
                "Nothing selected for download, please select at least one of the options Attachments or Content!"
            )
        return self

    class Config:
        populate_by_name = True
