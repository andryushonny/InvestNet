from __future__ import annotations

import email.utils
import hashlib
import json
import mailbox
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from loguru import logger
from sqlmodel import Session, select

from ..core.state import state
from ..db.models import Interaction, Person
from ..db.session import get_session
from .cleaner import clean_email_body, html_to_text

EMAIL_RE = re.compile(r"<?([\w\.\-+%]+@[\w\.\-]+\.[A-Za-z]{2,})>?")


def _parse_address(raw: str) -> tuple[Optional[str], Optional[str]]:
    if not raw:
        return None, None
    name, addr = email.utils.parseaddr(raw)
    return (name.strip() or None), (addr.lower().strip() or None)


def _parse_addresses(raw: str | None) -> list[tuple[Optional[str], str]]:
    if not raw:
        return []
    out = []
    for entry in email.utils.getaddresses([raw]):
        name, addr = entry
        if addr and "@" in addr:
            out.append((name.strip() or None, addr.lower().strip()))
    return out


def _parse_date(raw: str | None) -> Optional[datetime]:
    if not raw:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(raw)
        if dt.tzinfo:
            dt = dt.astimezone(tz=None).replace(tzinfo=None)
        return dt
    except Exception:
        return None


def _extract_body(msg) -> str:
    if msg.is_multipart():
        plain_parts, html_parts = [], []
        for part in msg.walk():
            ct = part.get_content_type()
            disp = (part.get("Content-Disposition") or "").lower()
            if "attachment" in disp:
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                text = payload.decode(charset, errors="replace")
            except LookupError:
                text = payload.decode("utf-8", errors="replace")
            if ct == "text/plain":
                plain_parts.append(text)
            elif ct == "text/html":
                html_parts.append(text)
        if plain_parts:
            return "\n".join(plain_parts)
        if html_parts:
            return html_to_text("\n".join(html_parts))
        return ""
    payload = msg.get_payload(decode=True)
    if not payload:
        return ""
    charset = msg.get_content_charset() or "utf-8"
    try:
        text = payload.decode(charset, errors="replace")
    except LookupError:
        text = payload.decode("utf-8", errors="replace")
    if msg.get_content_type() == "text/html":
        return html_to_text(text)
    return text


def _self_addresses(session: Session) -> set[str]:
    self_emails = set()
    s = state.settings
    if s and s.data_dir:
        marker = Path(s.data_dir) / "self_emails.json"
        if marker.exists():
            try:
                self_emails.update(json.loads(marker.read_text(encoding="utf-8")))
            except Exception:
                pass
    return {e.lower() for e in self_emails}


def _should_skip(from_addr: str, subject: str, recipient_count: int, occurred_at: datetime | None) -> bool:
    s = state.settings
    f = s.filters if s else None
    if not f:
        return False
    if recipient_count > f.max_recipients:
        return True
    if f.min_date and occurred_at and occurred_at.date().isoformat() < f.min_date:
        return True
    fl = (from_addr or "").lower()
    for pat in f.skip_sender_patterns:
        if re.search(pat, fl):
            return True
    sl = (subject or "").lower()
    for pat in f.skip_subject_patterns:
        if re.search(pat, sl):
            return True
    return False


def _get_or_create_person(session: Session, name: Optional[str], email_addr: str) -> Person:
    p = session.exec(select(Person).where(Person.primary_email == email_addr)).first()
    if p:
        if name and (not p.full_name or p.full_name == p.primary_email):
            p.full_name = name
            session.add(p)
        return p
    p = Person(full_name=name or email_addr, primary_email=email_addr, source="gmail")
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def import_mbox(
    mbox_path: Path,
    progress_cb=None,
    self_emails: Iterable[str] | None = None,
) -> dict:
    """Streaming mbox importer. Returns summary stats."""
    stats = {"total": 0, "imported": 0, "skipped": 0, "errors": 0}
    self_set = {e.lower() for e in (self_emails or [])}

    box = mailbox.mbox(str(mbox_path))
    total_size = mbox_path.stat().st_size

    with get_session() as session:
        if not self_set:
            self_set = _self_addresses(session)

        for i, msg in enumerate(box):
            stats["total"] += 1
            try:
                msg_id = msg.get("Message-ID") or msg.get("Message-Id") or ""
                subject = msg.get("Subject", "") or ""
                from_raw = msg.get("From", "") or ""
                to_raw = msg.get("To", "") or ""
                cc_raw = msg.get("Cc", "") or ""
                date_raw = msg.get("Date", "")

                from_name, from_addr = _parse_address(from_raw)
                tos = _parse_addresses(to_raw)
                ccs = _parse_addresses(cc_raw)
                occurred_at = _parse_date(date_raw)
                recipient_count = len(tos) + len(ccs)

                if not from_addr or _should_skip(from_addr, subject, recipient_count, occurred_at):
                    stats["skipped"] += 1
                    continue

                body_raw = _extract_body(msg)
                body = clean_email_body(body_raw)
                if not body and not subject:
                    stats["skipped"] += 1
                    continue

                outgoing = from_addr in self_set
                if outgoing:
                    counterparts = [(n, a) for n, a in (tos + ccs) if a not in self_set]
                    if not counterparts:
                        stats["skipped"] += 1
                        continue
                    direction = "outgoing"
                else:
                    counterparts = [(from_name, from_addr)]
                    direction = "incoming"

                content_for_hash = (msg_id + "|" + body[:2000]).encode("utf-8")
                body_hash = hashlib.sha1(content_for_hash).hexdigest()

                exists = session.exec(select(Interaction).where(Interaction.body_hash == body_hash)).first()
                if exists:
                    stats["skipped"] += 1
                    continue

                for name, addr in counterparts:
                    person = _get_or_create_person(session, name, addr)
                    ia = Interaction(
                        person_id=person.id,
                        channel="email",
                        direction=direction,
                        occurred_at=occurred_at or datetime.utcnow(),
                        subject=subject[:500],
                        body_cleaned=body[:10_000],
                        body_hash=body_hash if len(counterparts) == 1 else hashlib.sha1((body_hash + addr).encode()).hexdigest(),
                        raw_message_id=msg_id[:255] or None,
                        extra=json.dumps({"cc": [a for _, a in ccs], "to": [a for _, a in tos]}),
                    )
                    session.add(ia)
                session.commit()
                stats["imported"] += 1
            except Exception as e:
                stats["errors"] += 1
                logger.exception(f"mbox row {i} error: {e}")

            if progress_cb and i % 100 == 0:
                offset = 0
                try:
                    toc = getattr(box, "_toc", None)
                    if toc and (i + 1) in toc:
                        offset = toc[i + 1][0]
                except Exception:
                    pass
                frac = offset / max(total_size, 1) if offset else min(0.99, i / 100000)
                progress_cb(min(0.99, frac), stats)

    if progress_cb:
        progress_cb(1.0, stats)
    return stats
