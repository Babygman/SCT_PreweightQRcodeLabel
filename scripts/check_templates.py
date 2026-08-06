from app import create_app

application = create_app("testing")
with application.app_context():
    templates = application.jinja_env.list_templates()
    for template_name in templates:
        application.jinja_env.get_template(template_name)

print(f"Compiled {len(templates)} templates successfully")
