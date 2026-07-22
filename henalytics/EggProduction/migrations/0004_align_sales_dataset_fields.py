# Generated for aligning Sales CRUD with the sales dataset ledger format.

from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('EggProduction', '0003_alter_harvestforecast_grade_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='salestransaction',
            name='or_number',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='OR number'),
        ),
        migrations.RenameField(
            model_name='salesitem',
            old_name='quantity_trays',
            new_name='quantity_pieces',
        ),
        migrations.RenameField(
            model_name='salesitem',
            old_name='price_per_tray',
            new_name='unit_price',
        ),
        migrations.RenameField(
            model_name='salesitem',
            old_name='total_amount',
            new_name='amount',
        ),
        migrations.AlterField(
            model_name='salesitem',
            name='grade',
            field=models.CharField(choices=[('jumbo', 'Jumbo'), ('xl', 'XL'), ('large', 'Large'), ('medium', 'Medium'), ('small', 'Small'), ('pullets', 'Pullets'), ('pewee', 'Pewee'), ('broken', 'Broken'), ('cull', 'Cull'), ('sack', 'Sack')], max_length=20, verbose_name='sales category'),
        ),
        migrations.AlterField(
            model_name='salesitem',
            name='quantity_pieces',
            field=models.IntegerField(validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name='salesitem',
            name='unit_price',
            field=models.DecimalField(decimal_places=2, default=0, editable=False, max_digits=10),
        ),
        migrations.AlterField(
            model_name='salesitem',
            name='amount',
            field=models.DecimalField(decimal_places=2, max_digits=15),
        ),
    ]
