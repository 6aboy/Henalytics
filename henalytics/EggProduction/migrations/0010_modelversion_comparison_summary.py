from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('EggProduction', '0009_alter_userprofile_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='modelversion',
            name='comparison_summary',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='modelversion',
            name='feature_set',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
        migrations.AddField(
            model_name='modelversion',
            name='selection_metric',
            field=models.CharField(blank=True, default='rolling_mae_mape', max_length=30),
        ),
    ]
