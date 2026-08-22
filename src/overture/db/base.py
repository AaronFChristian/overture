from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base. All ORM models inherit from this.

    Alembic's env.py imports this module's `Base.metadata` as the
    autogenerate target — every model needs to actually be imported
    somewhere Python executes before a migration runs, or Alembic
    won't see it. `db/models.py` is imported explicitly in env.py for
    exactly this reason.
    """

    pass
