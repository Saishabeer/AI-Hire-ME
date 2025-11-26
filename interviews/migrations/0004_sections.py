import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('interviews', '0003_alter_question_question_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='Section',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('order', models.IntegerField(default=0)),
                ('interview', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sections', to='interviews.interview')),
            ],
            options={'ordering': ['order', 'id']},
        ),
        migrations.AddField(
            model_name='question',
            name='section',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='questions', to='interviews.section'),
        ),
    ]