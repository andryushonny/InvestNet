from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from loguru import logger
from sqlmodel import Session, select

from ..db.models import Interaction, Person
from ..db.session import get_session


def _read_csv(zf: zipfile.ZipFile, name: str) -> Optional[pd.DataFrame]:
    for info in zf.infolist():
        if info.filename.lower().endswith(name.lower()):
            with zf.open(info) as fh:
                data = fh.read()
            for skip in (0, 1, 2, 3):
                try:
                    return pd.read_csv(io.BytesIO(data), skiprows=skip)
                except Exception:
                    continue
    return None


def _get_or_create_person(session: Session, full_name: str, email: Optional[str], linkedin_url: Optional[str], company: Optional[str], title: Optional[str]) -> Person:
    if email:
        p = session.exec(select(Person).where(Person.primary_email == email.lower())).first()
        if p:
            updated = False
            if linkedin_url and not p.linkedin_url:
                p.linkedin_url = linkedin_url; updated = True
            if company and not p.company:
                p.company = company; updated = True
            if title and not p.title:
                p.title = title; updated = True
            if updated:
                session.add(p)
            return p
    if linkedin_url:
        p = session.exec(select(Person).where(Person.linkedin_url == linkedin_url)).first()
        if p:
            return p
    p = Person(
        full_name=full_name or (email or linkedin_url or "Unknown"),
        primary_email=email.lower() if email else None,
        linkedin_url=linkedin_url,
        company=company,
        title=title,
        source="linkedin",
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def import_linkedin_zip(zip_path: Path, progress_cb=None) -> dict:
    stats = {"connections": 0, "messages": 0, "skipped": 0}
    with zipfile.ZipFile(zip_path) as zf, get_session() as session:
        conn_df = _read_csv(zf, "Connections.csv")
        if conn_df is not None:
            conn_df.columns = [c.strip() for c in conn_df.columns]
            total = len(conn_df)
            for i, row in conn_df.iterrows():
                try:
                    first = str(row.get("First Name", "") or "").strip()
                    last = str(row.get("Last Name", "") or "").strip()
                    name = f"{first} {last}".strip() or "Unknown"
                    em = row.get("Email Address")
                    em = str(em).strip().lower() if em and str(em).strip().lower() != "nan" else None
                    url = row.get("URL")
                    url = str(url).strip() if url and str(url).strip().lower() != "nan" else None
                    company = row.get("Company")
                    company = str(company).strip() if company and str(company).strip().lower() != "nan" else None
                    title = row.get("Position")
                    title = str(title).strip() if title and str(title).strip().lower() != "nan" else None
                    _get_or_create_person(session, name, em, url, company, title)
                    stats["connections"] += 1
                except Exception as e:
                    logger.warning(f"linkedin connection row {i}: {e}")
                    stats["skipped"] += 1
                if progress_cb and i % 50 == 0:
                    progress_cb(0.5 * i / max(total, 1), stats)

        msgs_df = _read_csv(zf, "messages.csv")
        if msgs_df is not None:
            msgs_df.columns = [c.strip().upper() for c in msgs_df.columns]
            total = len(msgs_df)
            for i, row in msgs_df.iterrows():
                try:
                    content = str(row.get("CONTENT", "") or "").strip()
                    if not content:
                        stats["skipped"] += 1
                        continue
                    from_p = str(row.get("FROM", "") or "").strip()
                    to_p = str(row.get("TO", "") or "").strip()
                    date_raw = str(row.get("DATE", "") or "").strip()
                    subject = str(row.get("SUBJECT", "") or "").strip()
                    conv_id = str(row.get("CONVERSATION ID", "") or "").strip()
                    direction = "outgoing" if "you" in from_p.lower() else "incoming"
                    counterpart = to_p if direction == "outgoing" else from_p
                    if not counterpart:
                        stats["skipped"] += 1
                        continue
                    try:
                        dt = datetime.fromisoformat(date_raw.replace("Z", ""))
                    except Exception:
                        dt = datetime.utcnow()
                    person = _get_or_create_person(session, counterpart, None, None, None, None)
                    h = hashlib.sha1((conv_id + content[:500] + str(dt)).encode("utf-8")).hexdigest()
                    if session.exec(select(Interaction).where(Interaction.body_hash == h)).first():
                        continue
                    ia = Interaction(
                        person_id=person.id,
                        channel="linkedin_msg",
                        direction=direction,
                        occurred_at=dt,
                        subject=subject[:500] or None,
                        body_cleaned=content[:10_000],
                        body_hash=h,
                        raw_message_id=conv_id or None,
                        extra=json.dumps({"from": from_p, "to": to_p}),
                    )
                    session.add(ia)
                    stats["messages"] += 1
                    if i % 200 == 0:
                        session.commit()
                except Exception as e:
                    logger.warning(f"linkedin msg row {i}: {e}")
                    stats["skipped"] += 1
                if progress_cb and i % 50 == 0:
                    progress_cb(0.5 + 0.5 * i / max(total, 1), stats)
            session.commit()

    if progress_cb:
        progress_cb(1.0, stats)
    return stats
