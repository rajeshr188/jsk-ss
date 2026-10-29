import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("schemes", "0033_configured_full_settlement")]

    operations = [
        migrations.AddField(
            model_name="schemeplan", name="publication_revision",
            field=models.ForeignKey(blank=True, editable=False, null=True,
                on_delete=django.db.models.deletion.PROTECT, related_name="published_plans",
                to="schemes.schemeplanrevision"),
        ),
        migrations.RemoveConstraint(model_name="schemeplan", name="configured_plan_preparation_only"),
        migrations.AddConstraint(
            model_name="schemeplan",
            constraint=models.CheckConstraint(
                condition=(models.Q(configuration__isnull=True)
                           | models.Q(active=False, publicly_listed=False)
                           | models.Q(active=True, publication_revision__isnull=False)),
                name="configured_plan_publication_required",
            ),
        ),
    ]
