import django.core.validators
from django.db import migrations, models


def reject_unversioned_independent_accounts(apps, schema_editor):
    account = apps.get_model('schemes', 'SchemeAccount')
    if account.objects.using(schema_editor.connection.alias).filter(configuration_snapshot__policy_schema_version=2).exists():
        raise RuntimeError('Cannot apply 0040 with pre-existing schema-2 agreements; reconcile their frozen terms explicitly first.')


def preserve_independent_agreements(apps, schema_editor):
    account = apps.get_model('schemes', 'SchemeAccount')
    if account.objects.using(schema_editor.connection.alias).filter(
            models.Q(agreement_schema_version=2) | models.Q(configuration_snapshot__policy_schema_version=2)).exists():
        raise RuntimeError('Cannot reverse 0040 with retained independent agreements; use compatible forward recovery.')


class Migration(migrations.Migration):
    dependencies = [('schemes', '0039_inr_settlement_corrections')]

    operations = [
        migrations.RunPython(reject_unversioned_independent_accounts, migrations.RunPython.noop),
        migrations.RemoveConstraint(model_name='schemeaccount', name='account_agreed_months_gte_12'),
        migrations.AddField(model_name='schemeaccount', name='agreement_schema_version',
            field=models.PositiveSmallIntegerField(default=1, editable=False)),
        migrations.AddField(model_name='schemeaccount', name='eligibility_policy_snapshot',
            field=models.CharField(blank=True, default='', editable=False, max_length=24)),
        migrations.AddField(model_name='schemeaccount', name='required_count_snapshot',
            field=models.PositiveSmallIntegerField(blank=True, editable=False, null=True)),
        migrations.AlterField(model_name='schemeaccount', name='agreed_months',
            field=models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1)])),
        migrations.AlterField(model_name='schemeaccount', name='eligible_from',
            field=models.DateField(blank=True, null=True)),
        migrations.AlterField(model_name='schemeaccount', name='frequency_rule_snapshot',
            field=models.CharField(choices=[('ONCE_PER_MONTH', 'Once per month'), ('FLEXIBLE', 'Flexible'),
                ('ONCE_PER_PERIOD', 'Once per agreed period')], max_length=20)),
        migrations.AddConstraint(model_name='schemeaccount', constraint=models.CheckConstraint(condition=(
            models.Q(agreement_schema_version=1, agreed_months__isnull=False, agreed_months__gte=12,
                eligible_from__isnull=False, eligibility_policy_snapshot='', required_count_snapshot__isnull=True)
            | (models.Q(agreement_schema_version=2, configuration_snapshot__isnull=False, plan_revision__isnull=False)
               & (models.Q(eligibility_policy_snapshot='DURATION', agreed_months__isnull=False,
                           agreed_months__gte=1, eligible_from__isnull=False)
                  | models.Q(eligibility_policy_snapshot='DURATION_AND_COUNT', agreed_months__isnull=False,
                             agreed_months__gte=1, eligible_from__isnull=False, required_count_snapshot__isnull=False)
                  | models.Q(eligibility_policy_snapshot='COUNT', agreed_months__isnull=True,
                             eligible_from__isnull=True, required_count_snapshot__isnull=False)
                  | models.Q(eligibility_policy_snapshot='ANYTIME', agreed_months__isnull=True,
                             eligible_from__isnull=True, required_count_snapshot__isnull=True)))
        ), name='account_eligibility_shape')),
        migrations.AddConstraint(model_name='schemeaccount', constraint=models.CheckConstraint(condition=(
            models.Q(required_count_snapshot__isnull=True) | models.Q(required_count_snapshot__gte=1)
        ), name='account_required_count_positive')),
        migrations.AddConstraint(model_name='schemeaccount', constraint=models.CheckConstraint(condition=(
            models.Q(agreement_schema_version=2, frequency_rule_snapshot__in=['FLEXIBLE', 'ONCE_PER_PERIOD'])
            | models.Q(agreement_schema_version=1, frequency_rule_snapshot__in=['FLEXIBLE', 'ONCE_PER_MONTH'])
        ), name='account_frequency_shape')),
        migrations.RunPython(migrations.RunPython.noop, preserve_independent_agreements),
    ]
