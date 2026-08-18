from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="role",
            field=models.CharField(
                choices=[("OWNER", "Owner"), ("STAFF", "Staff"), ("CUSTOMER", "Customer")],
                default="CUSTOMER",
                max_length=10,
            ),
        ),
    ]
