"""Dataset CRUD service — create, list, detail, update, archive datasets and sources.

Datasets are versioned collections of document sources for fine-tuning.
No hard deletion allowed — only soft-archive per PID constraint.
Version auto-increments when sources are added.
"""

import hashlib
import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset import Dataset
from app.models.dataset_source import DatasetSource
from app.models.dataset_version_history import DatasetVersionHistory

logger = logging.getLogger(__name__)


# ── Dataset CRUD ──────────────────────────────────────────────────


async def create_dataset(
    db: AsyncSession,
    *,
    user_id: str,
    name: str,
    description: str | None = None,
    domain_tags: list[str] | None = None,
) -> Dataset:
    """Create a new dataset with initial version 1."""
    dataset = Dataset(
        id=str(uuid.uuid4()),
        user_id=user_id,
        name=name,
        description=description,
        version=1,
        status="active",
        domain_tags=domain_tags,
    )
    db.add(dataset)

    # Create initial version history entry
    version_entry = DatasetVersionHistory(
        id=str(uuid.uuid4()),
        dataset_id=dataset.id,
        version=1,
        change_description="Dataset created",
        source_count=0,
        sources_added=0,
    )
    db.add(version_entry)

    await db.flush()
    logger.info("Dataset created: %s (%s) for user %s", dataset.id, name, user_id)
    return dataset


async def list_datasets(
    db: AsyncSession,
    user_id: str,
    *,
    status_filter: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Dataset], int]:
    """List datasets for a user with optional status filter and pagination."""
    base = select(Dataset).where(Dataset.user_id == user_id)
    if status_filter:
        base = base.where(Dataset.status == status_filter)
    base = base.order_by(Dataset.updated_at.desc())

    # Total count
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # Paginated results
    stmt = base.offset(offset).limit(limit)
    result = await db.execute(stmt)
    datasets = list(result.scalars().all())
    return datasets, total


async def get_dataset(
    db: AsyncSession,
    dataset_id: str,
    user_id: str,
) -> Dataset | None:
    """Get a single dataset by ID, scoped to user."""
    result = await db.execute(
        select(Dataset).where(
            Dataset.id == dataset_id,
            Dataset.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def update_dataset(
    db: AsyncSession,
    dataset: Dataset,
    *,
    name: str | None = None,
    description: str | None = None,
    domain_tags: list[str] | None = None,
) -> Dataset:
    """Update dataset metadata."""
    if name is not None:
        dataset.name = name
    if description is not None:
        dataset.description = description
    if domain_tags is not None:
        dataset.domain_tags = domain_tags

    await db.flush()
    logger.info("Dataset updated: %s", dataset.id)
    return dataset


async def archive_dataset(
    db: AsyncSession,
    dataset: Dataset,
) -> Dataset:
    """Soft-archive a dataset (no hard delete per PID constraint)."""
    dataset.status = "archived"
    await db.flush()
    logger.info("Dataset archived: %s", dataset.id)
    return dataset


# ── Dataset Sources ──────────────────────────────────────────────


async def add_source(
    db: AsyncSession,
    dataset: Dataset,
    *,
    source_type: str,
    source_path: str,
    file_name: str | None = None,
    file_size: int | None = None,
    mime_type: str | None = None,
    content_hash: str | None = None,
) -> DatasetSource:
    """Add a source to a dataset, auto-incrementing version if needed."""
    # Check for duplicate by content hash
    if content_hash:
        existing = await db.execute(
            select(DatasetSource).where(
                DatasetSource.dataset_id == dataset.id,
                DatasetSource.content_hash == content_hash,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(
                f"Source already exists in dataset (hash: {content_hash[:12]}...)"
            )

    source = DatasetSource(
        id=str(uuid.uuid4()),
        dataset_id=dataset.id,
        dataset_version=dataset.version,
        source_type=source_type,
        source_path=source_path,
        file_name=file_name,
        file_size=file_size,
        mime_type=mime_type,
        content_hash=content_hash,
        processed=False,
    )
    db.add(source)

    # Increment dataset version
    old_version = dataset.version
    dataset.version += 1

    # Create version history entry
    version_entry = DatasetVersionHistory(
        id=str(uuid.uuid4()),
        dataset_id=dataset.id,
        version=dataset.version,
        change_description=(
            f"Added {source_type} source: {file_name or source_path}"
        ),
        source_count=old_version + 1,
        sources_added=1,
    )
    db.add(version_entry)

    await db.flush()
    logger.info(
        "Source added to dataset %s (v%d→v%d): %s",
        dataset.id, old_version, dataset.version, source_type,
    )
    return source


async def list_sources(
    db: AsyncSession,
    dataset_id: str,
    *,
    offset: int = 0,
    limit: int = 50,
) -> list[DatasetSource]:
    """List sources for a dataset."""
    result = await db.execute(
        select(DatasetSource)
        .where(DatasetSource.dataset_id == dataset_id)
        .order_by(DatasetSource.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def delete_source(
    db: AsyncSession,
    dataset: Dataset,
    source_id: str,
) -> None:
    """Remove a source from a dataset. Increments version."""
    source = await db.execute(
        select(DatasetSource).where(
            DatasetSource.id == source_id,
            DatasetSource.dataset_id == dataset.id,
        )
    )
    source_obj = source.scalar_one_or_none()
    if not source_obj:
        raise ValueError(f"Source '{source_id}' not found in dataset '{dataset.id}'")

    await db.delete(source_obj)

    # Increment version
    dataset.version += 1
    version_entry = DatasetVersionHistory(
        id=str(uuid.uuid4()),
        dataset_id=dataset.id,
        version=dataset.version,
        change_description=f"Removed source: {source_obj.file_name or source_obj.source_path}",
    )
    db.add(version_entry)

    await db.flush()
    logger.info("Source removed from dataset %s: %s", dataset.id, source_id)


def compute_content_hash(data: bytes) -> str:
    """Compute SHA-256 hash for deduplication."""
    return hashlib.sha256(data).hexdigest()
