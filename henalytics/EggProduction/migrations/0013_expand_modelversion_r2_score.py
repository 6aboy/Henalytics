from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('EggProduction', '0012_make_sales_flock_optional'),
    ]

    operations = [
        migrations.AlterField(
            model_name='modelversion',
            name='r2_score',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=20, null=True),
        ),
    ]
