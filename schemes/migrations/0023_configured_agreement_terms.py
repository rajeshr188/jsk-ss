import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("schemes", "0022_plan_configuration_foundation")]

    operations = [
        migrations.AddField(
            model_name="schemeaccount", name="configuration_snapshot",
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name="agreements", to="schemes.schemeplanconfiguration"),
        ),
        migrations.AddField(
            model_name="schemeaccount", name="contribution_step_snapshot",
            field=models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="schemeenrolmentrequest", name="configuration_snapshot",
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name="enrolment_requests", to="schemes.schemeplanconfiguration"),
        ),
        migrations.AddConstraint(model_name="schemeaccount", constraint=models.CheckConstraint(condition=(
            models.Q(configuration_snapshot__isnull=True, contribution_step_snapshot__isnull=True)
            | (models.Q(configuration_snapshot__isnull=False, plan_revision__isnull=False,
                        savings_mode__in=["GOLD", "SILVER"], cash_bonus_percentage_snapshot=0)
               & (models.Q(contribution_step_snapshot__isnull=True) | models.Q(contribution_step_snapshot__gt=0))
               & (models.Q(amount_rule_snapshot="VARIABLE", fixed_amount_snapshot__isnull=True)
                  | models.Q(amount_rule_snapshot="FIXED", fixed_amount_snapshot__isnull=False,
                             fixed_amount_snapshot__gt=0, minimum_amount_snapshot=models.F("fixed_amount_snapshot"),
                             maximum_amount_snapshot=models.F("fixed_amount_snapshot"), maximum_amount_snapshot__isnull=False,
                             contribution_step_snapshot__isnull=True)))
        ), name="account_configuration_shape")),
    ]
