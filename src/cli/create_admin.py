import asyncio
import uuid
from getpass import getpass

from sqlalchemy import select

from src.bootstrap.database import (
    dispose_engine,
    get_session_factory,
    init_db,
)
from src.infrastructure.auth.password import get_password_hash
from src.infrastructure.database.models.tenant import Tenant
from src.infrastructure.database.models.user import User


async def create_admin(name: str, slug: str, email: str, password: str):
    await init_db()
    session_factory = get_session_factory()

    async with session_factory() as session:
        result = await session.execute(select(Tenant).where(Tenant.slug == slug))
        existing_tenant = result.scalar_one_or_none()

        if existing_tenant:
            print(f"Tenant '{slug}' already exists with id={existing_tenant.id}")
            tenant = existing_tenant
        else:
            tenant = Tenant(
                id=uuid.uuid4(),
                name=name,
                slug=slug,
                plan="enterprise",
                license_status="active",
                max_assessments=9999,
            )
            session.add(tenant)
            await session.flush()
            print(f"Created tenant '{name}' (slug={slug}) with id={tenant.id}")

        result = await session.execute(select(User).where(User.email == email))
        existing_user = result.scalar_one_or_none()

        if existing_user:
            print(f"User '{email}' already exists with id={existing_user.id}")
        else:
            user = User(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                email=email,
                hashed_password=get_password_hash(password),
                full_name=name,
                role="admin",
                is_active=True,
            )
            session.add(user)
            await session.flush()
            print(f"Created admin user '{email}' with id={user.id}")
            print(f"Tenant: {tenant.name} ({tenant.slug})")
            print("Role: admin")
            print(f"License: {tenant.license_status}")

        await session.commit()

    await dispose_engine()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Create initial admin user and tenant")
    parser.add_argument("--name", required=True, help="Tenant and user name")
    parser.add_argument("--slug", required=True, help="Tenant slug (unique identifier)")
    parser.add_argument("--email", required=True, help="Admin user email")
    parser.add_argument("--password", default=None, help="Admin password (will prompt if not provided)")

    args = parser.parse_args()

    password = args.password or getpass("Enter admin password: ")

    asyncio.run(
        create_admin(
            name=args.name,
            slug=args.slug,
            email=args.email,
            password=password,
        )
    )


if __name__ == "__main__":
    main()
