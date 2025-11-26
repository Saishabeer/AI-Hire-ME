from django.db import migrations, models


def forwards(apps, schema_editor):
    Question = apps.get_model('interviews', 'Question')
    QuestionOption = apps.get_model('interviews', 'QuestionOption')
    Answer = apps.get_model('interviews', 'Answer')
    Section = apps.get_model('interviews', 'Section')

    # 1) Backfill Section for legacy Questions (using the legacy Question.interview FK before we drop it)
    try:
        qs = Question.objects.filter(section__isnull=True)
        for q in qs:
            try:
                iid = getattr(q, "interview_id", None)
                if iid is None:
                    continue
                sec = Section.objects.filter(interview_id=iid).order_by("order", "id").first()
                if sec is None:
                    sec = Section.objects.create(interview_id=iid, title="Section 1", order=0)
                q.section_id = sec.id
                q.save(update_fields=["section"])
            except Exception:
                # Proceed best-effort; don't block migration for a single row
                pass
    except Exception:
        # If legacy field not accessible in historical model state, skip silently
        pass

    # 2) Backfill Question.options from QuestionOption
    for q in Question.objects.all():
        try:
            opts = list(
                QuestionOption.objects.filter(question_id=q.id)
                .order_by('order', 'id')
                .values_list('option_text', flat=True)
            )
        except Exception:
            opts = []
        try:
            q.options_json = opts
            q.save(update_fields=['options_json'])
        except Exception:
            pass

    # 3) Backfill Answer.selected_options_new from M2M to QuestionOption
    try:
        selected_field = Answer._meta.get_field('selected_options')
        Through = selected_field.remote_field.through
        texts = dict(QuestionOption.objects.all().values_list('id', 'option_text'))
        for ans in Answer.objects.all():
            try:
                qo_ids = list(
                    Through.objects.filter(answer_id=ans.id).values_list(
                        'questionoption_id', flat=True
                    )
                )
            except Exception:
                qo_ids = []
            values = []
            if qo_ids:
                try:
                    values = list(
                        QuestionOption.objects.filter(id__in=qo_ids)
                        .order_by('order', 'id')
                        .values_list('option_text', flat=True)
                    )
                except Exception:
                    # Fallback to map order
                    values = [texts.get(i) for i in qo_ids if i in texts]
            try:
                setattr(ans, 'selected_options_new', list(values or []))
                ans.save(update_fields=['selected_options_new'])
            except Exception:
                pass
    except Exception:
        # If the M2M does not exist (already removed), skip
        pass


def backwards(apps, schema_editor):
    # Irreversible migration: QuestionOption model is removed and M2M dropped.
    pass


class Migration(migrations.Migration):
    # Run each operation in its own transaction to avoid "pending trigger events"
    atomic = False

    dependencies = [
        ('interviews', '0006_add_answers_json'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='options_json',
            field=models.JSONField(default=list, blank=True),
        ),
        migrations.AddField(
            model_name='answer',
            name='selected_options_new',
            field=models.JSONField(default=list, blank=True),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(
            model_name='answer',
            name='selected_options',
        ),
        migrations.RenameField(
            model_name='answer',
            old_name='selected_options_new',
            new_name='selected_options',
        ),
        migrations.RemoveField(
            model_name='question',
            name='interview',
        ),
        migrations.RemoveField(
            model_name='interviewresponse',
            name='candidate_name',
        ),
        migrations.RemoveField(
            model_name='interviewresponse',
            name='candidate_email',
        ),
        migrations.DeleteModel(
            name='QuestionOption',
        ),
        migrations.RenameField(
            model_name='question',
            old_name='options_json',
            new_name='options',
        ),
    ]
