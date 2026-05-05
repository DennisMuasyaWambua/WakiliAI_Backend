from django.core.management.base import BaseCommand
from authentication.models import Permission, Role, RolePermission


PERMISSIONS = [
    ("Private Workspace",           "private_workspace",            "Access to private workspace"),
    ("View Team Workspace",         "view_team_workspace",          "View team workspace"),
    ("View Assigned Cases",         "view_assigned_cases",          "View only assigned cases"),
    ("View All Cases",              "view_all_cases",               "View all firm cases"),
    ("View Closed Cases",           "view_closed_cases",            "View closed cases"),
    ("Manage Cases",                "manage_cases",                 "Create, edit, close cases"),
    ("Own Diary",                   "own_diary",                    "Manage own diary/calendar"),
    ("View Team Diary",             "view_team_diary",              "View team diary"),
    ("Manage All Diaries",          "manage_all_diaries",           "Manage all staff diaries"),
    ("View Client Updates",         "view_client_updates",          "View client updates"),
    ("Send Client Updates",         "send_client_updates",          "Send updates to clients"),
    ("View Repository",             "view_repository",              "View document repository"),
    ("Add to Repository",           "add_to_repository",            "Upload to repository"),
    ("Manage Repository",           "manage_repository",            "Full repository management"),
    ("View Own Billing",            "view_own_billing",             "View own billing records"),
    ("Manage Billing",              "manage_billing",               "Manage firm billing"),
    ("Full Billing Access",         "full_billing_access",          "Full billing access"),
    ("Use AI",                      "use_ai",                       "Use AI component"),
    ("Train AI",                    "train_ai",                     "Upload docs to train AI"),
    ("Admin AI Settings",           "admin_ai",                     "Manage AI settings"),
    ("View Users",                  "view_users",                   "View firm members"),
    ("Manage Users",                "manage_users",                 "Invite and manage users"),
    ("Full User Management",        "full_user_management",         "Full user management"),
    ("View Digital Repository",     "view_digital_repository",      "View digital repository"),
    ("Manage Digital Repository",   "manage_digital_repository",    "Manage digital repository"),
]


ROLES = [
    # Big Law
    ("Managing Partner",        "managing_partner",     "big_law",  10),
    ("Senior Partner",          "senior_partner",       "big_law",  9),
    ("Junior Partner",          "junior_partner",       "big_law",  8),
    ("Senior Associate",        "senior_associate",     "big_law",  7),
    ("Associate",               "associate",            "big_law",  6),
    ("Junior Associate",        "junior_associate",     "big_law",  5),
    ("Trainee Advocate",        "trainee",              "big_law",  4),
    # Mid-Size
    ("Founding Partner",        "founding_partner",     "mid_size", 10),
    ("Partner",                 "partner",              "mid_size", 9),
    ("Junior Advocate",         "junior_advocate",      "mid_size", 6),
    ("Pupil / Trainee",         "pupil",                "mid_size", 4),
    # System
    ("System Admin",            "admin",                "system",   99),
]


# Map role short_name → list of permission short_names
ROLE_PERMISSIONS = {
    "managing_partner": [
        "private_workspace", "view_team_workspace",
        "view_assigned_cases", "view_all_cases", "view_closed_cases", "manage_cases",
        "own_diary", "view_team_diary", "manage_all_diaries",
        "view_client_updates", "send_client_updates",
        "view_repository", "add_to_repository", "manage_repository",
        "view_own_billing", "manage_billing", "full_billing_access",
        "use_ai", "train_ai", "admin_ai",
        "view_users", "manage_users", "full_user_management",
        "view_digital_repository", "manage_digital_repository",
    ],
    "senior_partner": [
        "private_workspace", "view_team_workspace",
        "view_assigned_cases", "view_all_cases", "view_closed_cases", "manage_cases",
        "own_diary", "view_team_diary",
        "view_client_updates", "send_client_updates",
        "view_repository", "add_to_repository", "manage_repository",
        "view_own_billing", "manage_billing",
        "use_ai", "train_ai",
        "view_users", "manage_users",
        "view_digital_repository", "manage_digital_repository",
    ],
    "junior_partner": [
        "private_workspace", "view_team_workspace",
        "view_assigned_cases", "view_all_cases", "manage_cases",
        "own_diary", "view_team_diary",
        "view_client_updates", "send_client_updates",
        "view_repository", "add_to_repository",
        "view_own_billing",
        "use_ai", "train_ai",
        "view_users",
        "view_digital_repository",
    ],
    "senior_associate": [
        "private_workspace", "view_team_workspace",
        "view_assigned_cases", "view_all_cases", "manage_cases",
        "own_diary", "view_team_diary",
        "view_client_updates", "send_client_updates",
        "view_repository", "add_to_repository",
        "view_own_billing",
        "use_ai",
        "view_users",
        "view_digital_repository",
    ],
    "associate": [
        "private_workspace", "view_team_workspace",
        "view_assigned_cases", "manage_cases",
        "own_diary",
        "view_client_updates", "send_client_updates",
        "view_repository", "add_to_repository",
        "view_own_billing",
        "use_ai",
        "view_digital_repository",
    ],
    "junior_associate": [
        "private_workspace",
        "view_assigned_cases",
        "own_diary",
        "view_client_updates",
        "view_repository",
        "view_own_billing",
        "use_ai",
        "view_digital_repository",
    ],
    "trainee": [
        "private_workspace",
        "view_assigned_cases",
        "own_diary",
        "view_repository",
        "use_ai",
    ],
    "founding_partner": [
        "private_workspace", "view_team_workspace",
        "view_assigned_cases", "view_all_cases", "view_closed_cases", "manage_cases",
        "own_diary", "view_team_diary", "manage_all_diaries",
        "view_client_updates", "send_client_updates",
        "view_repository", "add_to_repository", "manage_repository",
        "view_own_billing", "manage_billing", "full_billing_access",
        "use_ai", "train_ai", "admin_ai",
        "view_users", "manage_users", "full_user_management",
        "view_digital_repository", "manage_digital_repository",
    ],
    "partner": [
        "private_workspace", "view_team_workspace",
        "view_assigned_cases", "view_all_cases", "manage_cases",
        "own_diary", "view_team_diary",
        "view_client_updates", "send_client_updates",
        "view_repository", "add_to_repository",
        "view_own_billing", "manage_billing",
        "use_ai", "train_ai",
        "view_users", "manage_users",
        "view_digital_repository",
    ],
    "junior_advocate": [
        "private_workspace",
        "view_assigned_cases",
        "own_diary",
        "view_client_updates",
        "view_repository",
        "view_own_billing",
        "use_ai",
        "view_digital_repository",
    ],
    "pupil": [
        "private_workspace",
        "view_assigned_cases",
        "own_diary",
        "view_repository",
        "use_ai",
    ],
    "admin": [
        "view_users", "manage_users", "full_user_management",
        "view_repository", "manage_repository",
        "manage_billing", "full_billing_access",
        "admin_ai",
        "manage_digital_repository",
    ],
}


class Command(BaseCommand):
    help = "Seed roles and permissions into the database"

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding permissions...")
        perm_map = {}
        for name, short_name, description in PERMISSIONS:
            perm, created = Permission.objects.get_or_create(
                short_name=short_name,
                defaults={"name": name, "description": description}
            )
            perm_map[short_name] = perm
            self.stdout.write(f"  {'created' if created else 'exists'}: {short_name}")

        self.stdout.write("Seeding roles...")
        role_map = {}
        for name, short_name, firm_type, access_level in ROLES:
            role, created = Role.objects.get_or_create(
                short_name=short_name,
                firm=None,  # system-level default roles
                defaults={
                    "name": name,
                    "description": f"{name} role",
                    "firm_type": firm_type,
                    "access_level": access_level,
                }
            )
            role_map[short_name] = role
            self.stdout.write(f"  {'created' if created else 'exists'}: {short_name}")

        self.stdout.write("Seeding role permissions...")
        for role_short_name, perm_list in ROLE_PERMISSIONS.items():
            role = role_map.get(role_short_name)
            if not role:
                continue
            for perm_short_name in perm_list:
                perm = perm_map.get(perm_short_name)
                if not perm:
                    continue
                rp, created = RolePermission.objects.get_or_create(
                    role=role, permission=perm,
                    defaults={"is_active": True}
                )
                if created:
                    self.stdout.write(f"  linked: {role_short_name} → {perm_short_name}")

        self.stdout.write(self.style.SUCCESS("Done! Roles and permissions seeded successfully."))