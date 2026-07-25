"""Management command to create default users per role."""
from django.core.management.base import BaseCommand
from apps.accounts.models import CustomUser, Role


class Command(BaseCommand):
    help = "Create default users: admin, analyst, investigator, viewer (password: Admin@1234)"

    def handle(self, *args, **options):
        defaults = [
            ("admin@crime.local", Role.SUPER_ADMIN),
            ("analyst@crime.local", Role.ANALYST),
            ("officer@crime.local", Role.INVESTIGATOR),
            ("viewer@crime.local", Role.READ_ONLY),
        ]
        for email, role in defaults:
            user, created = CustomUser.objects.get_or_create(
                email=email,
                defaults={
                    "name": email.split("@")[0].title(),
                    "badge_number": "DEMO000",
                    "role": role,
                    "is_active": True,
                },
            )
            if created:
                user.set_password("Admin@1234")
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Created {email} ({role})"))
            else:
                self.stdout.write(f"Exists: {email} ({role})")