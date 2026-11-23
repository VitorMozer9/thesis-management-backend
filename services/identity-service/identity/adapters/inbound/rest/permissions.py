from rest_framework.permissions import BasePermission

from config import dependencies


class IsActiveAdministrator(BasePermission):

    def has_permission(self, request, view) -> bool:
        if request.user is None:
            return False

        dependencies.build_authorize_administrator_use_case().execute(request.user.account_id)

        return True
