from .models import BlogIndexPage, BlogPostPage


BLOG_PAGE_SIZE = 9


def public_blog_root():
    return BlogIndexPage.objects.live().public().first()


def published_blog_posts(blog_index):
    return (
        BlogPostPage.objects.child_of(blog_index)
        .live()
        .public()
        .select_related("featured_image")
        .order_by("-featured", "-publication_date", "-first_published_at", "-pk")
    )
