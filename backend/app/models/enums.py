"""Enumerations shared across models. Stored as varchar (native_enum=False)."""
from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    AGENT = "agent"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class ChannelType(str, enum.Enum):
    TELEGRAM = "telegram"
    MESSENGER = "messenger"
    INSTAGRAM = "instagram"


class ChannelStatus(str, enum.Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class ConversationState(str, enum.Enum):
    OPEN = "open"
    NEEDS_HUMAN = "needs_human"
    PENDING = "pending"
    RESOLVED = "resolved"


class AIMode(str, enum.Enum):
    """Per-conversation AI behaviour."""
    ACTIVE = "active"      # AI replies automatically
    SUGGEST = "suggest"    # AI drafts, human sends
    OFF = "off"            # AI silent on this conversation


class MessageDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class SenderType(str, enum.Enum):
    CUSTOMER = "customer"
    AGENT = "agent"
    AI = "ai"
    SYSTEM = "system"


class MessageType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    FILE = "file"
    SYSTEM = "system"


class SendStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class AttachmentType(str, enum.Enum):
    IMAGE = "image"
    AUDIO = "audio"
    FILE = "file"


class EscalationReason(str, enum.Enum):
    REQUESTED_HUMAN = "requested_human"      # customer asked for a human
    NEGATIVE_SENTIMENT = "negative_sentiment"
    LOW_CONFIDENCE = "low_confidence"
    NO_KB_ANSWER = "no_kb_answer"
    SENSITIVE_TOPIC = "sensitive_topic"      # payment, refund, legal, complaint
    REPEATED_FAILURE = "repeated_failure"
    UNREADABLE_MEDIA = "unreadable_media"
    AI_ERROR = "ai_error"                    # technical failure / timeout


class NotificationType(str, enum.Enum):
    NEW_MESSAGE = "new_message"
    ESCALATION = "escalation"
    ASSIGNMENT = "assignment"
    SLA_BREACH = "sla_breach"
    CHANNEL_DOWN = "channel_down"
    AI_FAILURE = "ai_failure"
