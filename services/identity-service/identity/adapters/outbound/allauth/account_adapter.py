from allauth.account.adapter import DefaultAccountAdapter


class ClosedSignupAccountAdapter(DefaultAccountAdapter):

    def is_open_for_signup(self, request) -> bool:
        return False
