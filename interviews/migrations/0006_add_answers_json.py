# Generated manually to add answers_json snapshot to InterviewResponse
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('interviews', '0005_candidate_answer_interviews__respons_cab15e_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='interviewresponse',
            name='answers_json',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]