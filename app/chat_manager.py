#!/usr/bin/env python3
"""
Zarządzanie konwersacjami czatu „Porozmawiajmy”.
"""
from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

CHAT_PERSISTENCE_FILE = Path(__file__).parent.parent / ".chat_state.json"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ChatAttachment:
    id: str
    filename: str
    stored_path: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "stored_path": self.stored_path,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "uploaded_at": self.uploaded_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ChatAttachment":
        uploaded_at = datetime.fromisoformat(data["uploaded_at"]) if data.get("uploaded_at") else _utcnow()
        return cls(
            id=data["id"],
            filename=data["filename"],
            stored_path=data["stored_path"],
            content_type=data.get("content_type", "application/octet-stream"),
            size_bytes=data.get("size_bytes", 0),
            uploaded_at=uploaded_at,
        )


@dataclass
class ChatMessage:
    id: str
    role: str  # "user" | "assistant" | "system"
    content: str
    created_at: datetime = field(default_factory=_utcnow)
    attachments: List[ChatAttachment] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "attachments": [attachment.to_dict() for attachment in self.attachments],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ChatMessage":
        created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else _utcnow()
        attachments = [ChatAttachment.from_dict(item) for item in data.get("attachments", [])]
        return cls(
            id=data["id"],
            role=data["role"],
            content=data["content"],
            created_at=created_at,
            attachments=attachments,
        )


@dataclass
class ChatConversation:
    id: str
    queue_id: str
    filename: str
    transcription_file: Optional[str]
    analysis_file: Optional[str]
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    messages: List[ChatMessage] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "queue_id": self.queue_id,
            "filename": self.filename,
            "transcription_file": self.transcription_file,
            "analysis_file": self.analysis_file,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "messages": [msg.to_dict() for msg in self.messages],
        }

    def to_summary(self) -> Dict:
        last_message = self.messages[-1].to_dict() if self.messages else None
        return {
            "id": self.id,
            "queue_id": self.queue_id,
            "filename": self.filename,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_message": last_message,
            "message_count": len(self.messages),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ChatConversation":
        created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else _utcnow()
        updated_at = datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else created_at
        messages = [ChatMessage.from_dict(item) for item in data.get("messages", [])]
        conversation = cls(
            id=data["id"],
            queue_id=data["queue_id"],
            filename=data.get("filename", ""),
            transcription_file=data.get("transcription_file"),
            analysis_file=data.get("analysis_file"),
            created_at=created_at,
            updated_at=updated_at,
            messages=messages,
        )
        return conversation


class ChatManager:
    """Zarządza konwersacjami w panelu „Porozmawiajmy”."""

    def __init__(self, persistence_file: Optional[Path] = None) -> None:
        self._conversations: Dict[str, ChatConversation] = {}
        self._lock = threading.Lock()
        self._persistence_file = persistence_file or CHAT_PERSISTENCE_FILE
        self._load_state()

    def _load_state(self) -> None:
        if not self._persistence_file.exists():
            return
        try:
            with open(self._persistence_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            for convo_data in data.get("conversations", []):
                try:
                    convo = ChatConversation.from_dict(convo_data)
                    self._conversations[convo.id] = convo
                except Exception:
                    continue
        except Exception:
            pass

    def _save_state(self) -> None:
        try:
            data = {
                "conversations": [convo.to_dict() for convo in self._conversations.values()],
                "saved_at": _utcnow().isoformat(),
            }
            with open(self._persistence_file, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def list_conversations(self) -> List[Dict]:
        with self._lock:
            items = sorted(self._conversations.values(), key=lambda c: c.updated_at, reverse=True)
            return [item.to_summary() for item in items]

    def get_conversation(self, conversation_id: str) -> Optional[ChatConversation]:
        with self._lock:
            return self._conversations.get(conversation_id)

    def start_conversation(
        self,
        queue_id: str,
        filename: str,
        transcription_file: Optional[str],
        analysis_file: Optional[str],
    ) -> ChatConversation:
        with self._lock:
            convo_id = str(uuid.uuid4())
            conversation = ChatConversation(
                id=convo_id,
                queue_id=queue_id,
                filename=filename,
                transcription_file=transcription_file,
                analysis_file=analysis_file,
                messages=[],
            )
            self._conversations[convo_id] = conversation
            self._save_state()
            return conversation

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        attachments: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[ChatMessage]:
        with self._lock:
            conversation = self._conversations.get(conversation_id)
            if not conversation:
                return None
            attachment_objs: List[ChatAttachment] = []
            for attachment in attachments or []:
                attachment_objs.append(
                    ChatAttachment(
                        id=attachment["id"],
                        filename=attachment["filename"],
                        stored_path=attachment["stored_path"],
                        content_type=attachment.get("content_type", "application/octet-stream"),
                        size_bytes=attachment.get("size_bytes", 0),
                    )
                )
            message = ChatMessage(
                id=str(uuid.uuid4()),
                role=role,
                content=content,
                attachments=attachment_objs,
            )
            conversation.messages.append(message)
            conversation.updated_at = _utcnow()
            self._save_state()
            return message

    def find_attachment(self, conversation_id: str, attachment_id: str) -> Optional[ChatAttachment]:
        with self._lock:
            conversation = self._conversations.get(conversation_id)
            if not conversation:
                return None
            for message in conversation.messages:
                for attachment in message.attachments:
                    if attachment.id == attachment_id:
                        return attachment
            return None
