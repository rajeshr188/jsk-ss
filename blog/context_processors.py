from django.conf import settings

from .selectors import public_blog_root


def public_blog_navigation(request):
    if not settings.PUBLIC_BLOG_ENABLED:
        return {
            "public_blog_page": None,
            "public_blog_url": "",
            "public_blog_is_current": False,
        }
    blog = public_blog_root()
    blog_url = blog.get_url(request=request) if blog else ""
    return {
        "public_blog_page": blog,
        "public_blog_url": blog_url,
        "public_blog_is_current": bool(
            blog_url and request.path.startswith(blog_url)
        ),
    }
