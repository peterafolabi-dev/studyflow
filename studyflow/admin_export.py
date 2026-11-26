import csv

from django.http import HttpResponse


def export_as_csv(modeladmin, request, queryset):
    """Admin action: download the selected rows as a CSV file."""
    meta = modeladmin.model._meta
    fields = [f.name for f in meta.fields]
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename={meta.model_name}.csv'
    writer = csv.writer(response)
    writer.writerow(fields)
    for obj in queryset:
        writer.writerow([str(getattr(obj, f)) for f in fields])
    return response


export_as_csv.short_description = 'Download selected as CSV'
