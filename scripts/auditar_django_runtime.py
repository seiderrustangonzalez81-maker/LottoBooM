#!/usr/bin/env python3
"""Safe Django runtime smoke audit: imports/checks/templates/URL patterns; no DB queries."""
from __future__ import annotations
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "LottoBooM.settings")
# CI must use isolated settings and never inherit production connection variables.
os.environ.pop("DATABASE_URL", None)
os.environ.pop("RENDER", None)
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SECRET_KEY", "ci-only-not-a-production-secret")

import django
django.setup()

from django.core.checks import run_checks
from django.template import engines
from django.urls import get_resolver
from django.conf import settings

errors = run_checks()
if errors:
    print("Django system checks:")
    for error in errors:
        print(f"[{error.level_tag}] {error}")
    sys.exit(1)
print("Django system checks: OK")

# Import all installed project app modules that are conventional entry points.
for app in settings.INSTALLED_APPS:
    if not app.startswith(("django.", "rest_framework", "corsheaders")):
        package = app.split(".")[0]
        for suffix in ("models", "forms", "views", "urls"):
            try:
                __import__(f"{package}.{suffix}")
            except ModuleNotFoundError as exc:
                # Ignore a missing optional module itself, but surface dependencies
                # missing from an existing app module.
                if exc.name == f"{package}.{suffix}":
                    continue
                raise
print("App imports (models/forms/views/urls): OK")

# Compile every template discovered in project template directories. This does not render
# requests or execute template context processors, and does not access application data.
template_dirs = [Path(d) for d in settings.TEMPLATES[0]["DIRS"]]
for app in settings.INSTALLED_APPS:
    try:
        from django.apps import apps
        config = apps.get_app_config(app.split(".")[0])
        template_dirs.append(Path(config.path) / "templates")
    except Exception:
        continue
template_files = []
for directory in template_dirs:
    if directory.exists():
        template_files.extend(directory.rglob("*.html"))
engine = engines["django"]
failed = []
for path in sorted(set(template_files)):
    # Convert to template-relative path for configured dirs/app dirs.
    candidates = []
    for directory in template_dirs:
        try:
            candidates.append(path.relative_to(directory).as_posix())
        except ValueError:
            pass
    loaded = False
    for name in candidates:
        try:
            engine.get_template(name)
            loaded = True
            break
        except Exception:
            continue
    if not loaded:
        failed.append(str(path))
if failed:
    print("Template loading failures (template names could not be resolved):")
    for item in failed[:30]:
        print(" -", item)
    sys.exit(1)
print(f"Template syntax/load: OK ({len(set(template_files))} files discovered)")

# Force URL resolver construction, without reverse() requiring parameters or invoking views.
resolver = get_resolver()
list(resolver.url_patterns)
print("Root URL resolver: OK")
