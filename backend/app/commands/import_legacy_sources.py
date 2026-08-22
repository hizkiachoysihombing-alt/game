"""Idempotently import reviewed legacy manifests into the source catalog."""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.permissions import UserRole
from app.models.models import User
from app.services.source_ingestion import import_legacy_manifest


def main() -> None:
    if not settings.SOURCE_IMPORT_LEGACY:
        print("Legacy source import is disabled.")
        return
    root = Path(settings.SOURCE_MATERIALS_ROOT).resolve()
    manifests = sorted((root / "manifests").glob("*.csv")) if (root / "manifests").is_dir() else []
    if not manifests:
        print(f"No legacy source manifests found below {root}.")
        return

    with SessionLocal() as db:
        owner = (
            db.query(User)
            .filter(User.is_active.is_(True), User.role.in_([UserRole.ADMIN, UserRole.INSTRUCTOR]))
            .order_by(User.id)
            .first()
            or db.query(User).filter(User.is_active.is_(True)).order_by(User.id).first()
        )
        if owner is None:
            print("Legacy source import skipped: create at least one active user first.")
            return
        imported = skipped = deduplicated = 0
        errors: list[str] = []
        for manifest in manifests:
            result = import_legacy_manifest(db, manifest, owner.id)
            imported += result.imported
            skipped += result.skipped
            deduplicated += result.deduplicated
            errors.extend(f"{manifest.name}: {message}" for message in result.errors)
            db.commit()
        print(
            "Legacy source import complete: "
            f"{imported} imported, {deduplicated} deduplicated, "
            f"{skipped} skipped, {len(errors)} errors."
        )
        for message in errors:
            print(f"- {message}")


if __name__ == "__main__":
    main()
