from sqlalchemy import select, true

from app.extensions import db
from app.models import Material, Station


def station_classifications(station):
    return {
        value.strip().upper()
        for value in (station.material_classifications or "GENERAL").split(",")
        if value.strip()
    }


def station_can_weigh_material(station_id, material: Material):
    station = db.session.scalar(
        select(Station).where(Station.id == station_id, Station.is_active == true())
    )
    if station is None or not material.is_active:
        return False
    material_classification = (material.classification or "GENERAL").strip().upper()
    return material_classification in station_classifications(station)
