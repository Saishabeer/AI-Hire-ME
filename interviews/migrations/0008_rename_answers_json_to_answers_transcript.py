from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('interviews', '0007_refactor_schema'),
    ]

    operations = [
        migrations.RenameField(
            model_name='interviewresponse',
            old_name='answers_json',
            new_name='answers_transcript',
        ),
    ]
