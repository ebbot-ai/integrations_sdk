from pydantic.dataclasses import dataclass
import typing


@dataclass
class TextMessageData:
    type: typing.Literal["text"]
    text: str


@dataclass
class ToolResponseMessageData:
    type: typing.Literal["tool_response"]
    content: str
    callId: str


@dataclass
class ToolCall:
    name: str
    callId: str
    arguments: str


@dataclass
class ToolCallsMessageData:
    type: typing.Literal["tool_calls"]
    toolCalls: list[ToolCall]
    text: typing.Optional[str] = None


MessageData = typing.Union[
    TextMessageData, ToolResponseMessageData, ToolCallsMessageData
]

MessageAuthor = typing.Literal["bot", "visitor", "system"]


@dataclass
class Message:
    id: str
    # Will be fixed later.
    # createdAt: typing.Optional[str]
    chatId: str
    author: MessageAuthor
    data: MessageData


@dataclass
class User:
    id: str
    email: typing.Optional[str] = None
    firstName: typing.Optional[str] = None
    lastName: typing.Optional[str] = None


@dataclass
class Bot:
    id: str
    companyId: str
    name: str
    config: dict[str, typing.Any]


class ChatMetadata(typing.TypedDict):
    ticketCreated: typing.Optional[bool]


@dataclass
class ChatData:
    componentStore: dict[str, typing.Any]
    metadata: ChatMetadata


@dataclass
class Chat:
    id: str
    userId: str
    botId: str
    data: ChatData


@dataclass
class Company:
    id: str
    name: str
