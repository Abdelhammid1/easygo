"""Model registry — import every model so Flask-Migrate can discover them."""
from app.models.ai import (  # noqa: F401
    AIRun,
    AISettings,
    KBChunk,
    KBItem,
    Order,
    PromptVersion,
)
from app.models.core import (  # noqa: F401
    Attachment,
    Channel,
    Contact,
    ContactIdentity,
    Conversation,
    Message,
    User,
)
from app.models.org import OrgSettings  # noqa: F401
from app.models.support import (  # noqa: F401
    AuditLog,
    CannedResponse,
    InternalNote,
    Notification,
    PushSubscription,
    Tag,
    conversation_tags,
)

__all__ = [
    "User", "Channel", "Contact", "ContactIdentity", "Conversation",
    "Message", "Attachment", "Tag", "conversation_tags", "InternalNote",
    "CannedResponse", "Notification", "AuditLog", "KBItem", "KBChunk",
    "AISettings", "PromptVersion", "AIRun", "Order", "OrgSettings", "PushSubscription",
]
