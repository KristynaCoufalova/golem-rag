#!/bin/bash
# Azure App Service (and similar) startup: run the web app bound to 0.0.0.0
# so that OIDC callbacks (e.g. HiStruct / FemCAD sign-in) can reach the app from the internet.
# If the app only binds to 127.0.0.1, sign-in redirects will fail.
python run_web.py
