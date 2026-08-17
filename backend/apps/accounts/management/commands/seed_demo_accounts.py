"""Create (or reset) the three fixed demo accounts the frontend's login
screen is hard-mapped to, so credentials work identically in every
environment — local dev, a fresh deployment, or a deployment whose
database doesn't happen to already have these rows.

    python manage.py seed_demo_accounts

The frontend (``app/page.tsx``'s ``USERNAME_TO_EMAIL``) maps three fixed
usernames to these exact email addresses and expects these exact
passwords:

    qualifylearncrm         -> admin@qualifylearn.test        (SUPER_ADMIN)
    qualifylearnmanagercrm  -> manager@qualifylearn.test       (MANAGER)
    qualifylearnemployeecrm -> employee@qualifylearn.test      (EMPLOYEE)

"Credentials not working in deployment" almost always means this
command was never run against THAT deployment's database — creating a
user locally never touches a separately-hosted database, and every
deployment in this project (see config/settings/production.py) is
expected to point at its own Postgres instance via its own environment
variables. Run this command in whatever shell/console your hosting
platform gives you against the deployed backend (e.g. `railway run`,
`heroku run`, a Kubernetes exec, an SSH session) to make the demo
credentials work there too.

Idempotent and safe to re-run: existing rows are updated in place
(password reset, role/active-state corrected) rather than duplicated,
matching this project's ``get_or_create``-based seeding pattern used
elsewhere. Never prints a password to the terminal beyond the ones
already public in this file/the frontend source — there is nothing
secret about a demo account by definition.

Production safety: refuses to run under production settings unless
``--force`` is passed, the same "the safe path is the default" posture
this project's other admin-affecting commands already follow (see
``backup_database``) — resetting well-known passwords on three accounts
is a deliberate demo convenience, not something that should ever fire
by accident against a database that might one day hold real users.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User

DEMO_ACCOUNTS = [
    {
        "email": "admin@qualifylearn.test",
        "password": "crmworkingphase",
        "role": User.Role.SUPER_ADMIN,
        "first_name": "Super",
        "last_name": "Admin",
        "access_code": "654321",
    },
    {
        "email": "manager@qualifylearn.test",
        "password": "crmworkingphasemanager",
        "role": User.Role.MANAGER,
        "first_name": "Demo",
        "last_name": "Manager",
        "access_code": None,
    },
    {
        "email": "employee@qualifylearn.test",
        "password": "crmworkingphaseemployee",
        "role": User.Role.EMPLOYEE,
        "first_name": "Demo",
        "last_name": "Employee",
        "access_code": None,
    },
]


class Command(BaseCommand):
    help = "Create or reset the three fixed demo accounts (Super Admin/Manager/Employee) the frontend's login screen expects."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Required to run this command when DEBUG is False (production/staging settings).",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "Refusing to seed demo accounts under production settings (DEBUG=False) without --force. "
                "If this really is a demo/staging deployment, re-run with --force."
            )

        for account in DEMO_ACCOUNTS:
            user, created = User.objects.get_or_create(
                email=account["email"],
                defaults={
                    "first_name": account["first_name"],
                    "last_name": account["last_name"],
                    "role": account["role"],
                    "is_active": True,
                },
            )
            user.first_name = account["first_name"]
            user.last_name = account["last_name"]
            user.role = account["role"]
            user.is_active = True
            user.set_password(account["password"])
            if account["access_code"]:
                user.set_access_code(account["access_code"])
            user.save()

            verb = "Created" if created else "Reset"
            self.stdout.write(self.style.SUCCESS(f"{verb} {account['role']}: {account['email']}"))

        self.stdout.write(self.style.SUCCESS("Demo accounts ready."))
