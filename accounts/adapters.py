from allauth.account.adapter import DefaultAccountAdapter


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        # Customer credentials are created through the owner workflow.
        return False

    def render_mail(self, template_prefix, email, context, headers=None):
        # Authentication links must remain direct, untracked owned-domain URLs.
        headers = {
            **(headers or {}),
            "X-PM-TrackLinks": "None",
            "X-PM-TrackOpens": "false",
        }
        return super().render_mail(
            template_prefix,
            email,
            context,
            headers=headers,
        )
