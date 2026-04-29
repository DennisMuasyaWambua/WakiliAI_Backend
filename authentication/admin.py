from django.contrib import admin

from authentication.models import Firm, FirmInvite, User

admin.site.register(User)
admin.site.register(FirmInvite)
admin.site.register(Firm)
