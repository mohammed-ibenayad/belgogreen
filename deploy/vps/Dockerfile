# Odoo 19 Community + the Python libraries our modules need
# (requirements.txt): PV simulation charts and reports (matplotlib, numpy,
# WeasyPrint), Solar API images (rasterio), OCA resource_booking (cssselect).
# From the distribution's packages: no pip in the system Python.
FROM odoo:19.0

USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        python3-matplotlib python3-numpy weasyprint python3-rasterio python3-cssselect \
 && rm -rf /var/lib/apt/lists/*
USER odoo
