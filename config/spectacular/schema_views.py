from django.http import HttpResponse
from drf_spectacular.generators import SchemaGenerator
import logging
import traceback

logger = logging.getLogger(__name__)


def custom_schema_view(request):
    """Custom schema view with detailed error logging"""
    try:
        generator = SchemaGenerator()
        schema = generator.get_schema(request=None, public=True)
        
        # Convert to YAML
        import yaml
        schema_yaml = yaml.dump(schema, allow_unicode=True, sort_keys=False)
        
        return HttpResponse(schema_yaml, content_type='application/vnd.oai.openapi')
    except Exception as e:
        logger.error(f"Schema generation error: {e}")
        logger.error(traceback.format_exc())
        return HttpResponse(f"Error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}", 
                          content_type='text/plain', 
                          status=500)
