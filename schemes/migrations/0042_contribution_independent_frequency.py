from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("schemes", "0041_inr_system_receipts")]
    operations = [migrations.AlterField(
        model_name="contribution", name="frequency_rule_snapshot",
        field=models.CharField(max_length=20, choices=[
            ("ONCE_PER_MONTH", "Once per month"), ("FLEXIBLE", "Flexible"),
            ("ONCE_PER_PERIOD", "Once per agreed period")]),
    )]
