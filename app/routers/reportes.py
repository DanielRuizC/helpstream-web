from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from .. import models, schemas, crud
from ..database import get_db
from .auth import get_current_admin_user
from .tickets import estructurar_info_creador

router = APIRouter(
    prefix="/api/reportes",
    tags=["Reportes y Dashboards Gerenciales"]
)

dashboard_router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard Gerencial"]
)

# Tiempos SLA en horas según criticidad (HU18)
SLA_LIMITES_HORAS = {
    "Alta": 24,
    "Alto": 24,
    "Crítico": 24,
    "Critico": 24,
    "Media": 72,
    "Medio": 72,
    "Baja": 168,
    "Bajo": 168
}


def calcular_metrica_ticket(ticket: models.Ticket, ahora: datetime) -> Dict[str, Any]:
    """Calcula el estado y tiempo restante del SLA para un ticket individual."""
    criticidad = ticket.criticidad or "Media"
    sla_limite = SLA_LIMITES_HORAS.get(criticidad, 72)
    
    fecha_creacion = ticket.fecha_creacion or ahora
    if fecha_creacion.tzinfo is not None:
        fecha_creacion = fecha_creacion.replace(tzinfo=None)

    tiempo_transcurrido = (ahora - fecha_creacion).total_seconds() / 3600.0
    horas_restantes = max(0.0, sla_limite - tiempo_transcurrido)
    
    if ticket.estado == "Resuelto":
        # Considerado cumplido
        estado_sla = "Cumplido"
        esta_vencido = False
    else:
        if tiempo_transcurrido > sla_limite:
            estado_sla = "Vencido"
            esta_vencido = True
        elif horas_restantes <= (sla_limite * 0.25):
            estado_sla = "En Riesgo"
            esta_vencido = False
        else:
            estado_sla = "Normal"
            esta_vencido = False

    es_autoatencion = False
    if ticket.comentario_tecnico:
        com_lower = ticket.comentario_tecnico.lower()
        if "video" in com_lower or "autoatencion" in com_lower or "microaprendizaje" in com_lower:
            es_autoatencion = True

    return {
        "sla_limite_horas": sla_limite,
        "tiempo_transcurrido_horas": round(tiempo_transcurrido, 1),
        "horas_restantes": round(horas_restantes, 1),
        "estado_sla": estado_sla,
        "esta_vencido": esta_vencido,
        "es_autoatencion": es_autoatencion
    }


def generar_resumen_ejecutivo(db: Session) -> Dict[str, Any]:
    """Genera métricas consolidadas para la Jefatura de TI."""
    tickets = db.query(models.Ticket).all()
    ahora = datetime.utcnow()

    total_tickets = len(tickets)
    abiertos = 0
    en_progreso = 0
    resueltos = 0
    
    por_criticidad = {"Alta": 0, "Media": 0, "Baja": 0}
    por_sede: Dict[str, int] = {}
    vencidos_sla = 0
    en_riesgo_sla = 0
    dentro_sla = 0
    criticos_alta = 0
    autoatencion_count = 0

    lista_tickets_reporte = []

    for t in tickets:
        # Estado
        if t.estado == "Abierto":
            abiertos += 1
        elif t.estado == "En Progreso":
            en_progreso += 1
        elif t.estado == "Resuelto":
            resueltos += 1

        # Criticidad
        crit_normalizada = "Media"
        if t.criticidad in ["Alta", "Alto", "Crítico", "Critico"]:
            crit_normalizada = "Alta"
            por_criticidad["Alta"] += 1
            if t.estado != "Resuelto":
                criticos_alta += 1
        elif t.criticidad in ["Baja", "Bajo"]:
            crit_normalizada = "Baja"
            por_criticidad["Baja"] += 1
        else:
            por_criticidad["Media"] += 1

        # Sede
        sede_nombre = t.sede or "Sin Sede Asignada"
        por_sede[sede_nombre] = por_sede.get(sede_nombre, 0) + 1

        # SLA
        sla_info = calcular_metrica_ticket(t, ahora)
        if sla_info["esta_vencido"]:
            vencidos_sla += 1
        else:
            dentro_sla += 1

        if sla_info["estado_sla"] == "En Riesgo":
            en_riesgo_sla += 1

        if sla_info["es_autoatencion"]:
            autoatencion_count += 1

        creador_info = estructurar_info_creador(db, t)
        lista_tickets_reporte.append({
            "id": t.id,
            "descripcion": t.descripcion,
            "estado": t.estado,
            "criticidad": crit_normalizada,
            "sede": t.sede or "-",
            "piso": t.piso or "-",
            "fecha_creacion": t.fecha_creacion.isoformat() if t.fecha_creacion else None,
            "solicitante": creador_info.nombre or t.correo_solicitante or "Usuario",
            "correo_solicitante": t.correo_solicitante or creador_info.correo or "-",
            "telefono": creador_info.telefono or "-",
            "anexo": creador_info.anexo or "-",
            "estado_sla": sla_info["estado_sla"],
            "horas_restantes": sla_info["horas_restantes"],
            "sla_limite_horas": sla_info["sla_limite_horas"],
            "es_autoatencion": sla_info["es_autoatencion"]
        })

    # Cumplimiento SLA porcentaje
    porcentaje_sla = 100.0
    if total_tickets > 0:
        porcentaje_sla = round(((total_tickets - vencidos_sla) / total_tickets) * 100, 1)

    tasa_resolucion = 0.0
    if total_tickets > 0:
        tasa_resolucion = round((resueltos / total_tickets) * 100, 1)

    return {
        "kpis": {
            "total_tickets": total_tickets,
            "abiertos": abiertos,
            "en_progreso": en_progreso,
            "resueltos": resueltos,
            "criticos_pendientes": criticos_alta,
            "cumplimiento_sla_porcentaje": porcentaje_sla,
            "tasa_resolucion_porcentaje": tasa_resolucion,
            "tickets_vencidos_sla": vencidos_sla,
            "tickets_en_riesgo_sla": en_riesgo_sla,
            "tickets_dentro_sla": dentro_sla,
            "autoatencion_resueltos": autoatencion_count
        },
        "distribucion": {
            "por_criticidad": por_criticidad,
            "por_sede": por_sede,
            "por_estado": {
                "Abierto": abiertos,
                "En Progreso": en_progreso,
                "Resuelto": resueltos
            }
        },
        "tickets": sorted(lista_tickets_reporte, key=lambda x: x["id"], reverse=True)
    }


# =========================================================================
# ENDPOINTS PROTEGIDOS EXCLUSIVOS PARA JEFATURA DE TI (HU20 - 403 FORBIDDEN)
# =========================================================================

@router.get("/dashboard")
def get_reportes_dashboard(
    db: Session = Depends(get_db),
    admin_user: models.Usuario = Depends(get_current_admin_user)
):
    """
    HU20: Endpoint exclusivo para Jefatura de TI.
    Retorna métricas consolidadas, KPIs de SLA y distribución operativa.
    Protegido con validación estricta de rol 403 Forbidden.
    """
    return generar_resumen_ejecutivo(db)


@router.get("/kpis")
def get_reportes_kpis(
    db: Session = Depends(get_db),
    admin_user: models.Usuario = Depends(get_current_admin_user)
):
    """Retorna los indicadores clave de rendimiento (KPIs) ejecutivos."""
    resumen = generar_resumen_ejecutivo(db)
    return resumen["kpis"]


@router.get("/tickets")
def get_reportes_tickets(
    sede: Optional[str] = Query(None),
    criticidad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    admin_user: models.Usuario = Depends(get_current_admin_user)
):
    """Retorna la lista de tickets para auditoría ejecutiva con filtros opcionales."""
    resumen = generar_resumen_ejecutivo(db)
    tickets = resumen["tickets"]

    if sede:
        tickets = [t for t in tickets if (t.get("sede") or "").lower() == sede.lower()]
    if criticidad:
        tickets = [t for t in tickets if (t.get("criticidad") or "").lower() == criticidad.lower()]
    if estado:
        tickets = [t for t in tickets if (t.get("estado") or "").lower() == estado.lower()]

    return tickets


@dashboard_router.get("/gerencial")
def get_dashboard_gerencial(
    db: Session = Depends(get_db),
    admin_user: models.Usuario = Depends(get_current_admin_user)
):
    """
    Alias directo para el Dashboard Gerencial (HU20).
    Protegido por get_current_admin_user (403 Forbidden para usuarios no administradores).
    """
    return generar_resumen_ejecutivo(db)


@dashboard_router.get("/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    admin_user: models.Usuario = Depends(get_current_admin_user)
):
    """Métricas estadísticas agrupadas para el Dashboard Gerencial."""
    return generar_resumen_ejecutivo(db)
