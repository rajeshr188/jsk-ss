from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("schemes", "0029_instalment_order_recovery")]

    operations = [
        migrations.RemoveConstraint(model_name="schemereminder", name="scheme_reminder_kind_valid"),
        migrations.RemoveConstraint(model_name="schemereminder", name="scheme_reminder_target_shape_valid"),
        migrations.AlterField(
            model_name="schemereminder", name="kind",
            field=models.CharField(max_length=32, choices=[
                ("UPCOMING_ELIGIBILITY", "Upcoming eligibility"),
                ("UPCOMING_MONTHLY_COMPLETION", "Upcoming monthly completion"),
                ("ALLOCATION_EXCEPTION", "Allocation exception"),
                ("COMPLETED_REDEMPTION", "Completed redemption"),
            ]),
        ),
        migrations.AddConstraint(model_name="schemereminder", constraint=models.CheckConstraint(
            condition=models.Q(kind__in=["UPCOMING_ELIGIBILITY", "UPCOMING_MONTHLY_COMPLETION",
                "ALLOCATION_EXCEPTION", "COMPLETED_REDEMPTION"]), name="scheme_reminder_kind_valid")),
        migrations.AddConstraint(model_name="schemereminder", constraint=models.CheckConstraint(
            condition=(models.Q(kind__in=["UPCOMING_ELIGIBILITY", "UPCOMING_MONTHLY_COMPLETION"],
                contribution__isnull=True, redemption__isnull=True, eligibility_lead_days__isnull=False)
                | models.Q(kind="ALLOCATION_EXCEPTION", contribution__isnull=False,
                    redemption__isnull=True, eligibility_lead_days__isnull=True)
                | models.Q(kind="COMPLETED_REDEMPTION", contribution__isnull=True,
                    redemption__isnull=False, eligibility_lead_days__isnull=True)),
            name="scheme_reminder_target_shape_valid")),
    ]
