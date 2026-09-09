from datetime import date, timedelta
from io import BytesIO, StringIO

from PIL import Image as PillowImage
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import ValidationError
from django.core.files.images import ImageFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from wagtail.images import get_image_model
from wagtail.models import Collection, Locale, Page, PageLogEntry, Site, WorkflowState
from wagtail.permissions import policy_registry

from .models import BlogIndexPage, BlogPostPage
from .permissions import (
    ADMIN_MODEL_PERMISSIONS,
    BLOG_ADMIN_GROUP,
    BLOG_EDITOR_GROUP,
    BLOG_MEDIA_COLLECTION,
    BLOG_PUBLISHER_GROUP,
    BLOG_ROLES,
    BLOG_WORKFLOW,
    blog_permission_configuration_errors,
)


image_permission_policy = policy_registry.get_by_type(get_image_model())

IN_MEMORY_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
    "renditions": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
}


def configure_test_site():
    if not Locale.objects.exists():
        Locale.objects.create(language_code="en")
    root = Page.get_first_root_node()
    if root is None:
        root = Page.add_root(title="Root", slug="root")
    site_root = root.get_children().first()
    if site_root is None:
        site_root = root.add_child(instance=Page(title="Site root", slug="home"))
    Site.objects.update_or_create(
        is_default_site=True,
        defaults={"hostname": "testserver", "port": 80, "root_page": site_root},
    )
    return site_root


@override_settings(STORAGES=IN_MEMORY_STORAGES)
class BlogDomainTests(TestCase):
    def setUp(self):
        self.site_root = configure_test_site()
        call_command("configure_blog_permissions", verbosity=0)
        self.blog = BlogIndexPage.objects.get()

    def make_post(self, *, title="How to care for gold jewellery"):
        post = BlogPostPage(
            title=title,
            slug=title.lower().replace(" ", "-"),
            publication_date=date(2026, 9, 10),
            summary="Practical care guidance from our Vellore showroom.",
            body="<p>Store jewellery separately and handle it with care.</p>",
        )
        self.blog.add_child(instance=post)
        return post

    def make_image(self):
        data = BytesIO()
        PillowImage.new("RGB", (16, 12), color=(184, 134, 11)).save(
            data, format="PNG"
        )
        data.seek(0)
        return get_image_model().objects.create(
            title="Jewellery care article",
            file=ImageFile(data, name="jewellery-care.png"),
            collection=Collection.get_first_root_node(),
        )

    def test_page_hierarchy_is_bounded_to_one_index_and_its_posts(self):
        self.assertTrue(BlogPostPage.can_create_at(self.blog))
        self.assertFalse(BlogPostPage.can_create_at(self.site_root))
        self.assertFalse(BlogIndexPage.can_create_at(self.blog))
        self.assertFalse(BlogIndexPage.can_create_at(self.site_root))

    def test_featured_image_requires_editorial_alt_text(self):
        post = self.make_post()
        post.featured_image = self.make_image()
        post.featured_image_alt = ""

        with self.assertRaises(ValidationError) as raised:
            post.full_clean()

        self.assertIn("featured_image_alt", raised.exception.message_dict)

    def test_author_and_summary_are_normalized(self):
        post = self.make_post()
        post.author_name = "  Jai Sri Krishna Jewellery  "
        post.summary = "  Practical jewellery guidance.  "
        post.save()
        post.refresh_from_db()

        self.assertEqual(post.author_name, "Jai Sri Krishna Jewellery")
        self.assertEqual(post.summary, "Practical jewellery guidance.")

    @override_settings(PUBLIC_BLOG_ENABLED=False)
    def test_disabled_public_gate_does_not_block_authorized_preview_rendering(self):
        post = self.make_post()
        request = RequestFactory().get("/cms/preview/")
        request.user = AnonymousUser()

        response = post.serve_preview(request, "")
        response.render()

        self.assertEqual(response.status_code, 200)
        self.assertIn(post.title, response.content.decode())


@override_settings(STORAGES=IN_MEMORY_STORAGES, PUBLIC_BLOG_ENABLED=True)
class PublicBlogTests(TestCase):
    def setUp(self):
        configure_test_site()
        call_command("configure_blog_permissions", verbosity=0)
        self.blog = BlogIndexPage.objects.get()
        self.blog.save_revision().publish()
        self.blog.refresh_from_db()

    def make_post(
        self,
        *,
        title,
        publication_date=date(2026, 9, 10),
        featured=False,
        live=True,
    ):
        post = BlogPostPage(
            title=title,
            slug=title.lower().replace(" ", "-"),
            publication_date=publication_date,
            summary=f"A factual summary for {title}.",
            body=f"<p>Reviewed guidance for {title}.</p>",
            featured=featured,
            live=False,
        )
        self.blog.add_child(instance=post)
        revision = post.save_revision()
        if live:
            revision.publish()
        post.refresh_from_db()
        return post

    def test_public_index_exposes_only_live_posts_and_navigation(self):
        published = self.make_post(title="Understanding jewellery hallmarks")
        draft = self.make_post(title="Unreviewed article", live=False)

        response = self.client.get(self.blog.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, published.title)
        self.assertNotContains(response, draft.title)
        self.assertContains(response, f'href="{self.blog.url}">Journal</a>')
        self.assertEqual(self.client.get(published.url).status_code, 200)
        self.assertEqual(self.client.get(draft.url).status_code, 404)

    @override_settings(PUBLIC_BLOG_ENABLED=False)
    def test_disabled_flag_blocks_direct_routes_and_global_discovery(self):
        post = self.make_post(title="Private rollout article")

        self.assertEqual(self.client.get(self.blog.url).status_code, 404)
        self.assertEqual(self.client.get(post.url).status_code, 404)
        homepage = self.client.get(reverse("home"))
        self.assertIsNone(homepage.context["public_blog_page"])
        self.assertNotContains(homepage, ">Journal</a>")
        self.assertNotContains(homepage, ">Jewellery journal</a>")

    def test_featured_then_newest_ordering_and_pagination_are_bounded(self):
        featured = self.make_post(
            title="Featured care guide",
            publication_date=date(2026, 8, 1),
            featured=True,
        )
        newest = self.make_post(
            title="Newest showroom note",
            publication_date=date(2026, 9, 10),
        )
        for number in range(2, 11):
            self.make_post(
                title=f"Jewellery article {number:02d}",
                publication_date=date(2026, 9, 10) - timedelta(days=number),
            )

        first = self.client.get(self.blog.url)
        second = self.client.get(self.blog.url, {"page": 2})

        self.assertEqual(first.context["posts"].paginator.count, 11)
        self.assertEqual(len(first.context["posts"]), 9)
        self.assertEqual(len(second.context["posts"]), 2)
        self.assertEqual(first.context["posts"][0], featured)
        self.assertEqual(first.context["posts"][1], newest)


@override_settings(
    STORAGES=IN_MEMORY_STORAGES,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class BlogPublishingAuthorizationTests(TestCase):
    password = "correct-horse-battery-staple"

    def setUp(self):
        configure_test_site()
        call_command("configure_blog_permissions", verbosity=0)
        self.blog = BlogIndexPage.objects.get()
        self.groups = {role.name: Group.objects.get(name=role.name) for role in BLOG_ROLES}
        user_model = get_user_model()
        self.editor = user_model.objects.create_user(
            username="blog-editor@example.com",
            email="blog-editor@example.com",
            password=self.password,
            role=user_model.Role.STAFF,
            is_staff=True,
        )
        self.publisher = user_model.objects.create_user(
            username="blog-publisher@example.com",
            email="blog-publisher@example.com",
            password=self.password,
            role=user_model.Role.STAFF,
            is_staff=True,
        )
        self.editor.groups.add(self.groups[BLOG_EDITOR_GROUP])
        self.publisher.groups.add(self.groups[BLOG_PUBLISHER_GROUP])

    def make_draft_post(self):
        post = BlogPostPage(
            title="Reviewed jewellery guidance",
            slug="reviewed-jewellery-guidance",
            publication_date=date(2026, 9, 10),
            summary="A draft article awaiting independent publication approval.",
            body="<p>Reviewed educational content.</p>",
            live=False,
            owner=self.editor,
        )
        self.blog.add_child(instance=post)
        post.save_revision(user=self.editor)
        return post

    def test_configuration_is_idempotent_and_detects_permission_drift(self):
        self.assertFalse(self.blog.live)
        self.assertTrue(
            Collection.get_first_root_node()
            .get_children()
            .filter(name=BLOG_MEDIA_COLLECTION)
            .exists()
        )
        self.assertEqual(blog_permission_configuration_errors(), [])

        call_command("configure_blog_permissions", verbosity=0)
        call_command("configure_blog_permissions", "--check", verbosity=0)
        self.assertEqual(BlogIndexPage.objects.count(), 1)

        self.groups[BLOG_EDITOR_GROUP].permissions.clear()
        with self.assertRaises(CommandError):
            call_command(
                "configure_blog_permissions", "--check", stdout=StringIO()
            )

    def test_roles_are_scoped_to_blog_pages_and_media(self):
        editor_permissions = self.blog.permissions_for_user(self.editor)
        publisher_permissions = self.blog.permissions_for_user(self.publisher)
        self.assertTrue(editor_permissions.can_edit())
        self.assertTrue(editor_permissions.can_add_subpage())
        self.assertFalse(editor_permissions.can_publish())
        self.assertTrue(publisher_permissions.can_publish())
        self.assertFalse(
            Site.objects.get(is_default_site=True)
            .root_page.permissions_for_user(self.editor)
            .can_edit()
        )

        media = Collection.get_first_root_node().get_children().get(
            name=BLOG_MEDIA_COLLECTION
        )
        editable = image_permission_policy.collections_user_has_any_permission_for(
            self.editor, ["add", "change"]
        )
        self.assertTrue(editable.filter(pk=media.pk).exists())
        self.assertFalse(
            editable.filter(pk=Collection.get_first_root_node().pk).exists()
        )

        administrator = self.groups[BLOG_ADMIN_GROUP]
        self.assertEqual(
            set(
                administrator.permissions.values_list(
                    "content_type__app_label", "codename"
                )
            ),
            ADMIN_MODEL_PERMISSIONS,
        )
        self.assertFalse(
            administrator.permissions.filter(
                content_type__app_label__in=["accounts", "schemes", "catalog", "pages"]
            ).exists()
        )

    def test_editor_submission_requires_publisher_and_keeps_audit_history(self):
        post = self.make_draft_post()
        workflow = post.get_workflow()
        self.assertEqual(workflow.name, BLOG_WORKFLOW)
        state = workflow.start(post, user=self.editor)

        self.assertEqual(state.status, WorkflowState.STATUS_IN_PROGRESS)
        self.assertEqual(
            state.current_task_state.task.specific.get_actions(post, self.editor), []
        )
        self.assertIn(
            "approve",
            {
                action[0]
                for action in state.current_task_state.task.specific.get_actions(
                    post, self.publisher
                )
            },
        )

        state.current_task_state.specific.approve(
            user=self.publisher,
            comment="Approved educational jewellery article.",
        )
        state.refresh_from_db()
        post.refresh_from_db()
        self.assertEqual(state.status, WorkflowState.STATUS_APPROVED)
        self.assertTrue(post.live)
        self.assertTrue(
            PageLogEntry.objects.filter(
                page=post, action="wagtail.workflow.start", user=self.editor
            ).exists()
        )
        self.assertTrue(
            PageLogEntry.objects.filter(
                page=post, action="wagtail.workflow.approve", user=self.publisher
            ).exists()
        )

    def test_non_staff_group_membership_fails_closed(self):
        user_model = get_user_model()
        customer = user_model.objects.create_user(
            username="blog-customer@example.com",
            email="blog-customer@example.com",
            password=self.password,
            role=user_model.Role.CUSTOMER,
            is_staff=False,
        )
        customer.groups.add(self.groups[BLOG_EDITOR_GROUP])

        with self.assertRaises(CommandError):
            call_command(
                "configure_blog_permissions", "--check", stdout=StringIO()
            )
